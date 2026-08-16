//! Deterministic harness assessment. No model, no network, no heuristics that
//! need judgment: every finding is a rule that reads the scanned graph plus a
//! few files on disk and reports what it saw, with the file or node that proves
//! it.
//!
//! The rules are NOT invented here. They are the quality gate that
//! `harness-bootstrap/SKILL.md` already asserts, restated as code so a harness
//! can be checked after it drifts rather than only at the moment it is built.
//! Where a rule below has no counterpart in that gate it is marked `info` and
//! carries no score, because scoring something the project never promised would
//! be inventing a standard and then grading against it.

use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

/// Rules that load in every session by design. SKILL.md names exactly these six;
/// any OTHER rule without `paths:` is a permanent context tax on every agent.
const ALWAYS_ON_RULES: &[&str] = &[
    "00-overview",
    "agent-guardrails",
    "ai-governance",
    "conventional-commits",
    "model-policy",
    "task-tracking",
];

/// Seats the gate requires to be read-only. "Reviewers have no Edit or Write.
/// Not usually - none."
const REVIEW_SEATS: &[&str] = &[
    "code-reviewer",
    "merge-manager",
    "reviewer",
    "security-reviewer",
    "spec-guardian",
];

/// Destructive operations the gate expects `permissions.deny` to cover. Matched
/// as substrings against the deny list, because the real command is
/// project-specific (the DB reset of a Prisma repo is not that of a Django one).
const DENY_EXPECT: &[(&str, &str)] = &[
    ("force push", "push --force"),
    ("recursive delete", "rm -rf"),
    ("secret read", ".env"),
];

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Sev {
    Info,
    Low,
    Medium,
    High,
}

impl Sev {
    fn as_str(self) -> &'static str {
        match self {
            Sev::High => "high",
            Sev::Medium => "medium",
            Sev::Low => "low",
            Sev::Info => "info",
        }
    }
    /// Rank for worst-first ordering.
    fn rank(self) -> u8 {
        match self {
            Sev::High => 0,
            Sev::Medium => 1,
            Sev::Low => 2,
            Sev::Info => 3,
        }
    }
}

/// One thing that is true about this harness, with the evidence for it.
pub struct Finding {
    pub check: &'static str,
    pub category: &'static str,
    pub sev: Sev,
    /// What is wrong, in one line.
    pub title: String,
    /// Why it matters. One sentence, no hedging.
    pub why: &'static str,
    /// The node this is about, so the UI can select it in the graph.
    pub node: Option<String>,
    /// The file that proves it.
    pub file: Option<String>,
}

impl Finding {
    fn to_json(&self) -> Value {
        json!({
            "check": self.check,
            "category": self.category,
            "severity": self.sev.as_str(),
            "title": self.title,
            "why": self.why,
            "node": self.node,
            "file": self.file,
        })
    }
}

struct Ctx<'a> {
    root: &'a Path,
    nodes: Vec<&'a Value>,
    edges: &'a [Value],
}

impl<'a> Ctx<'a> {
    fn of_type(&self, t: &str) -> Vec<&'a Value> {
        self.nodes
            .iter()
            .copied()
            .filter(|n| n.get("type").and_then(|x| x.as_str()) == Some(t))
            .collect()
    }
    fn disabled(n: &Value) -> bool {
        n.get("disabled").and_then(|x| x.as_bool()).unwrap_or(false)
    }
    fn name(n: &Value) -> &str {
        n.get("id")
            .and_then(|x| x.as_str())
            .and_then(|s| s.split_once(':').map(|(_, b)| b))
            .unwrap_or("")
    }
    fn meta<'b>(n: &'b Value, k: &str) -> Option<&'b Value> {
        n.get("meta").and_then(|m| m.get(k))
    }
    fn file(n: &Value) -> Option<String> {
        n.get("file").and_then(|x| x.as_str()).map(String::from)
    }
}

// --------------------------------------------------------------------- checks

/// Cost control: an unset `model:` inherits the caller's tier, so mechanical
/// work silently bills at the most expensive model in the roster.
fn check_agent_model(c: &Ctx, out: &mut Vec<Finding>) {
    for n in c.of_type("agent") {
        if Ctx::disabled(n) {
            continue;
        }
        let name = Ctx::name(n);
        let model = Ctx::meta(n, "model").and_then(|v| v.as_str()).unwrap_or("");
        if model.is_empty() || model == "inherit" {
            out.push(Finding {
                check: "agent-model",
                category: "Cost control",
                sev: Sev::Medium,
                title: format!("agent `{name}` does not pin a model"),
                why: "An unset model inherits the caller's tier, so mechanical work bills at the \
                      most expensive model in the roster.",
                node: Some(format!("agent:{name}")),
                file: Ctx::file(n),
            });
        }
        if Ctx::meta(n, "effort").and_then(|v| v.as_str()).unwrap_or("").is_empty() {
            out.push(Finding {
                check: "agent-effort",
                category: "Cost control",
                sev: Sev::Low,
                title: format!("agent `{name}` does not pin an effort level"),
                why: "Effort is the second half of the cost decision; unset means the caller's \
                      level applies to work that may not need it.",
                node: Some(format!("agent:{name}")),
                file: Ctx::file(n),
            });
        }
    }
}

/// Cost control and safety: omitting `tools:` grants every tool, including every
/// MCP server, at full schema cost on every request.
fn check_agent_tools(c: &Ctx, out: &mut Vec<Finding>) {
    for n in c.of_type("agent") {
        if Ctx::disabled(n) {
            continue;
        }
        let name = Ctx::name(n);
        let empty = match Ctx::meta(n, "tools") {
            Some(Value::Array(a)) => a.is_empty(),
            _ => true,
        };
        if empty {
            out.push(Finding {
                check: "agent-tools",
                category: "Cost control",
                sev: Sev::High,
                title: format!("agent `{name}` grants no explicit tool list"),
                why: "Omitting tools inherits every tool including every MCP server, at full \
                      schema cost on every request and with no scope limit.",
                node: Some(format!("agent:{name}")),
                file: Ctx::file(n),
            });
        }
    }
}

/// Safety: a reviewer that can write is not a gate, it is another author.
fn check_reviewer_readonly(c: &Ctx, out: &mut Vec<Finding>) {
    for n in c.of_type("agent") {
        let name = Ctx::name(n);
        if !REVIEW_SEATS.contains(&name) || Ctx::disabled(n) {
            continue;
        }
        let tools: Vec<String> = match Ctx::meta(n, "tools") {
            Some(Value::Array(a)) => a
                .iter()
                .filter_map(|x| x.as_str())
                .map(|s| s.to_string())
                .collect(),
            _ => vec![],
        };
        for bad in ["Edit", "Write", "NotebookEdit"] {
            if tools.iter().any(|t| t == bad || t.starts_with(&format!("{bad}("))) {
                out.push(Finding {
                    check: "reviewer-readonly",
                    category: "Safety",
                    sev: Sev::High,
                    title: format!("review seat `{name}` holds `{bad}`"),
                    why: "A reviewer that can write is not a gate; it can fix what it was \
                          supposed to report and the review becomes self-approval.",
                    node: Some(format!("agent:{name}")),
                    file: Ctx::file(n),
                });
            }
        }
    }
}

/// Safety: only the orchestrator may hold `Agent`, or any seat can fan out and
/// the spawn boundary stops meaning anything.
fn check_spawn_boundary(c: &Ctx, out: &mut Vec<Finding>) {
    for n in c.of_type("agent") {
        let name = Ctx::name(n);
        if name == "orchestrator" || Ctx::disabled(n) {
            continue;
        }
        let holds = match Ctx::meta(n, "tools") {
            Some(Value::Array(a)) => a
                .iter()
                .filter_map(|x| x.as_str())
                .any(|t| t == "Agent" || t == "Task"),
            _ => false,
        };
        if holds {
            out.push(Finding {
                check: "spawn-boundary",
                category: "Safety",
                sev: Sev::High,
                title: format!("agent `{name}` can spawn subagents"),
                why: "Only the orchestrator should hold Agent; otherwise any seat can fan out \
                      and the spawn allowlist no longer bounds what runs.",
                node: Some(format!("agent:{name}")),
                file: Ctx::file(n),
            });
        }
    }
}

/// Cost control: a rule with no `paths:` loads in every session of every agent
/// forever. SKILL.md names the six that are allowed to.
fn check_rule_scoping(c: &Ctx, out: &mut Vec<Finding>) {
    for n in c.of_type("rule") {
        if Ctx::disabled(n) {
            continue;
        }
        let name = Ctx::name(n);
        let scoped = Ctx::meta(n, "scoped").and_then(|v| v.as_bool()).unwrap_or(false);
        if !scoped && !ALWAYS_ON_RULES.contains(&name) {
            out.push(Finding {
                check: "rule-scoping",
                category: "Cost control",
                sev: Sev::Medium,
                title: format!("rule `{name}` loads in every session"),
                why: "A rule without paths frontmatter is a permanent context tax on every agent \
                      in every session, whether or not the work touches it.",
                node: Some(format!("rule:{name}")),
                file: Ctx::file(n),
            });
        }
    }
}

/// Safety: a registration pointing at a hook file that does not exist is a
/// guardrail that silently never fires. This is the exact failure a mistyped
/// OS flag used to produce.
fn check_hook_wiring(c: &Ctx, out: &mut Vec<Finding>) {
    let hooks_dir = c.root.join(".claude/hooks");

    // Read the registrations from settings.json rather than from the graph: a
    // registration whose script is missing produces NO node (the scanner builds
    // hook nodes from files on disk), which is exactly the case that matters
    // most. Trusting the node list here would make this check unable to see the
    // failure it exists to catch.
    let text = fs::read_to_string(c.root.join(".claude/settings.json")).unwrap_or_default();
    let mut registered_names: BTreeSet<String> = BTreeSet::new();
    if let Ok(v) = serde_json::from_str::<Value>(&text) {
        if let Some(events) = v.get("hooks").and_then(|h| h.as_object()) {
            for (_event, groups) in events {
                for g in groups.as_array().into_iter().flatten() {
                    for h in g.get("hooks").and_then(|x| x.as_array()).into_iter().flatten() {
                        let cmd = h.get("command").and_then(|x| x.as_str()).unwrap_or("");
                        let norm = cmd.replace('\\', "/");
                        if let Some(i) = norm.rfind("hooks/") {
                            let tail = &norm[i + "hooks/".len()..];
                            let name: String = tail
                                .chars()
                                .take_while(|ch| ch.is_ascii_alphanumeric() || *ch == '-' || *ch == '_')
                                .collect();
                            if !name.is_empty() {
                                registered_names.insert(name);
                            }
                        }
                    }
                }
            }
        }
    }
    for name in &registered_names {
        let on_disk = ["sh", "ps1"]
            .iter()
            .any(|e| hooks_dir.join(format!("{name}.{e}")).is_file());
        if !on_disk {
            out.push(Finding {
                check: "hook-missing-file",
                category: "Safety",
                sev: Sev::High,
                title: format!("hook `{name}` is registered but has no file on disk"),
                why: "settings.json runs a script that is not there, so the guardrail never \
                      fires and nothing reports it.",
                node: None,
                file: Some(".claude/settings.json".into()),
            });
        }
    }

    for n in c.of_type("hook") {
        let name = Ctx::name(n);
        let registered = registered_names.contains(name);
        let on_disk = ["sh", "ps1"]
            .iter()
            .any(|e| hooks_dir.join(format!("{name}.{e}")).is_file());
        if !registered && on_disk && !Ctx::disabled(n) {
            out.push(Finding {
                check: "hook-unregistered",
                category: "Safety",
                sev: Sev::Medium,
                title: format!("hook `{name}` exists but is not registered"),
                why: "A hook file that settings.json never invokes is inert; it looks like a \
                      control and enforces nothing.",
                node: Some(format!("hook:{name}")),
                file: Ctx::file(n),
            });
        }
    }
}

/// Safety: the four layers the gate requires. Missing any one is reported
/// individually so the fix is obvious.
fn check_guardrail_layers(c: &Ctx, out: &mut Vec<Finding>) {
    let settings = c.root.join(".claude/settings.json");
    let text = fs::read_to_string(&settings).unwrap_or_default();
    let deny: Vec<String> = serde_json::from_str::<Value>(&text)
        .ok()
        .and_then(|v| {
            v.get("permissions")
                .and_then(|p| p.get("deny"))
                .and_then(|d| d.as_array())
                .map(|a| {
                    a.iter()
                        .filter_map(|x| x.as_str())
                        .map(|s| s.to_string())
                        .collect()
                })
        })
        .unwrap_or_default();

    if deny.is_empty() {
        out.push(Finding {
            check: "deny-list",
            category: "Safety",
            sev: Sev::High,
            title: "settings.json has no permissions.deny entries".into(),
            why: "The deny list is the first of the four guardrail layers; without it every \
                  destructive command reaches the hook layer or nothing at all.",
            node: Some("settings".into()),
            file: Some(".claude/settings.json".into()),
        });
    } else {
        for (label, needle) in DENY_EXPECT {
            if !deny.iter().any(|d| d.contains(needle)) {
                out.push(Finding {
                    check: "deny-coverage",
                    category: "Safety",
                    sev: Sev::Low,
                    title: format!("deny list does not mention {label}"),
                    why: "Deny rules are prefix matches and only a speed bump, but an absent one \
                          is not even that.",
                    node: Some("settings".into()),
                    file: Some(".claude/settings.json".into()),
                });
            }
        }
    }

    let blocking = c
        .of_type("hook")
        .iter()
        .filter(|n| {
            Ctx::meta(n, "blocking").and_then(|v| v.as_bool()).unwrap_or(false)
                && !Ctx::disabled(n)
        })
        .count();
    if blocking == 0 {
        out.push(Finding {
            check: "no-blocking-hook",
            category: "Safety",
            sev: Sev::High,
            title: "no blocking (PreToolUse) hook is active".into(),
            why: "Hooks are the layer that actually stops a tool call; with none active the \
                  guardrails are advice.",
            node: None,
            file: Some(".claude/settings.json".into()),
        });
    }

    if !c.root.join(".claude/rules/agent-guardrails.md").is_file() {
        out.push(Finding {
            check: "no-guardrail-rule",
            category: "Safety",
            sev: Sev::Medium,
            title: "agent-guardrails.md is not installed".into(),
            why: "It is the always-loaded rule that states the boundaries the hooks enforce; \
                  without it agents get the enforcement but never the reasoning.",
            node: None,
            file: Some(".claude/rules/agent-guardrails.md".into()),
        });
    }

    // Match the ROLE, not one project's spelling of it. The scaffolder ships
    // `/review-changes`, but a real harness may call the same gate `/review-pr`
    // or `/review-mr`; asserting the literal name reported a missing review gate
    // on a repo that plainly had one.
    let has_review_cmd = c.of_type("command").iter().any(|n| {
        let name = Ctx::name(n);
        !Ctx::disabled(n) && (name.starts_with("review") || name.ends_with("-review"))
    });
    let has_reviewer_seat = c
        .of_type("agent")
        .iter()
        .any(|n| REVIEW_SEATS.contains(&Ctx::name(n)) && !Ctx::disabled(n));
    if !has_review_cmd && !has_reviewer_seat {
        out.push(Finding {
            check: "no-review-gate",
            category: "Safety",
            sev: Sev::High,
            title: "no review command and no review seat".into(),
            why: "The review gate is the fourth guardrail layer and the only one that reads the \
                  diff as a whole.",
            node: None,
            file: Some(".claude/commands/".into()),
        });
    } else if !has_review_cmd {
        out.push(Finding {
            check: "no-review-command",
            category: "Safety",
            sev: Sev::Low,
            title: "a review seat exists but no command invokes it".into(),
            why: "A reviewer nobody routes work to is only enforced by whoever remembers to \
                  dispatch it by hand.",
            node: None,
            file: Some(".claude/commands/".into()),
        });
    }
}

/// Traceability: a task owned by a seat that was never fielded has nobody to do
/// it, and the board will not say so.
fn check_task_owners(c: &Ctx, out: &mut Vec<Finding>) {
    let agents: BTreeSet<String> = c
        .of_type("agent")
        .iter()
        .map(|n| Ctx::name(n).to_string())
        .collect();
    for n in c.of_type("task") {
        let owner = Ctx::meta(n, "owner").and_then(|v| v.as_str()).unwrap_or("");
        if owner.is_empty() || owner == "-" {
            continue;
        }
        for seat in owner.split('+').map(str::trim).filter(|s| !s.is_empty()) {
            if !agents.contains(seat) {
                out.push(Finding {
                    check: "task-owner-missing",
                    category: "Traceability",
                    sev: Sev::Medium,
                    title: format!("task `{}` is owned by `{seat}`, which is not on the roster", Ctx::name(n)),
                    why: "Work assigned to a seat that does not exist cannot be dispatched and \
                          will sit on the board unnoticed.",
                    node: Some(format!("task:{}", Ctx::name(n))),
                    file: Ctx::file(n),
                });
            }
        }
    }
}

/// Board health: Blocked with no recorded dependency is a task nothing will ever
/// unblock.
fn check_board(c: &Ctx, out: &mut Vec<Finding>) {
    for n in c.of_type("task") {
        let status = Ctx::meta(n, "status").and_then(|v| v.as_str()).unwrap_or("");
        let deps = Ctx::meta(n, "deps").and_then(|v| v.as_str()).unwrap_or("");
        if status.eq_ignore_ascii_case("blocked") && (deps.is_empty() || deps == "-") {
            out.push(Finding {
                check: "blocked-no-unblocker",
                category: "Board health",
                sev: Sev::Medium,
                title: format!("task `{}` is Blocked with no dependency recorded", Ctx::name(n)),
                why: "Nothing names what would unblock it, so it cannot be picked up when the \
                      blocker clears.",
                node: Some(format!("task:{}", Ctx::name(n))),
                file: Ctx::file(n),
            });
        }
        if status.is_empty() {
            out.push(Finding {
                check: "task-no-status",
                category: "Board health",
                sev: Sev::Low,
                title: format!("task `{}` has no status", Ctx::name(n)),
                why: "A task with no status is invisible to every board sweep that filters by it.",
                node: Some(format!("task:{}", Ctx::name(n))),
                file: Ctx::file(n),
            });
        }
    }
}

/// Traceability: a command that runs a script which is not installed fails at
/// the moment someone needs it.
fn check_dangling_scripts(c: &Ctx, out: &mut Vec<Finding>) {
    let ids: BTreeSet<&str> = c
        .nodes
        .iter()
        .filter_map(|n| n.get("id").and_then(|x| x.as_str()))
        .collect();
    for e in c.edges {
        if e.get("type").and_then(|x| x.as_str()) != Some("runs") {
            continue;
        }
        let to = e.get("to").and_then(|x| x.as_str()).unwrap_or("");
        let from = e.get("from").and_then(|x| x.as_str()).unwrap_or("");
        if !ids.contains(to) {
            out.push(Finding {
                check: "dangling-script",
                category: "Traceability",
                sev: Sev::Medium,
                title: format!("`{from}` runs `{to}`, which is not installed"),
                why: "The command names a script that is not in .claude/scripts, so it fails the \
                      first time it is used.",
                node: Some(from.to_string()),
                file: None,
            });
        }
    }
}

/// Docs quality: a blank line inside a GFM table ends it, so the remaining rows
/// render as a paragraph of pipes. Correct per spec, confusing on screen, and
/// nearly always unintended.
/// A skill sitting in `.claude/skills/` that no seat declares is procedural text
/// nobody follows. /skill-wire exists precisely because installing is not wiring.
fn check_skill_wiring(c: &Ctx, out: &mut Vec<Finding>) {
    let wired: BTreeSet<&str> = c
        .edges
        .iter()
        .filter(|e| e.get("type").and_then(|x| x.as_str()) == Some("uses"))
        .filter_map(|e| e.get("to").and_then(|x| x.as_str()))
        .collect();
    let ids: BTreeSet<&str> = c
        .nodes
        .iter()
        .filter_map(|n| n.get("id").and_then(|x| x.as_str()))
        .collect();

    for n in c.nodes.iter() {
        if n.get("type").and_then(|x| x.as_str()) != Some("skill") {
            continue;
        }
        let id = n.get("id").and_then(|x| x.as_str()).unwrap_or("");
        if wired.contains(id) {
            continue;
        }
        let label = n.get("label").and_then(|x| x.as_str()).unwrap_or(id);
        out.push(Finding {
            check: "skill-not-wired",
            category: "Traceability",
            sev: Sev::Low,
            title: format!("skill `{label}` is installed but wired to no seat"),
            why: "An unwired skill still costs review and update attention while changing \
                  nothing about how the harness behaves.",
            node: Some(id.to_string()),
            file: n.get("file").and_then(|x| x.as_str()).map(|f| f.to_string()),
        });
    }

    // A wire to an uninstalled skill produces no edge, by design, so the graph
    // cannot reveal it. Read the seat files directly, as the hook check reads
    // settings.json for the same reason.
    let _ = &ids;
    let agents_dir = c.root.join(".claude/agents");
    let mut seats: Vec<String> = Vec::new();
    if let Ok(rd) = std::fs::read_dir(&agents_dir) {
        for e in rd.flatten() {
            let p = e.path();
            if p.extension().and_then(|x| x.to_str()) == Some("md") {
                if let Some(stem) = p.file_stem().and_then(|x| x.to_str()) {
                    seats.push(stem.to_string());
                }
            }
        }
    }
    seats.sort();
    let installed: BTreeSet<String> = c
        .nodes
        .iter()
        .filter(|n| n.get("type").and_then(|x| x.as_str()) == Some("skill"))
        .filter_map(|n| n.get("label").and_then(|x| x.as_str()).map(|s| s.to_string()))
        .collect();

    for seat in seats {
        let text =
            std::fs::read_to_string(agents_dir.join(format!("{seat}.md"))).unwrap_or_default();
        for line in text.lines() {
            if let Some(val) = crate::scan::skill_decl_value(line) {
                for tok in crate::scan::slug_tokens(val) {
                    if !installed.contains(&tok) {
                        out.push(Finding {
                            check: "skill-wire-missing",
                            category: "Traceability",
                            sev: Sev::Medium,
                            title: format!(
                                "`{seat}` declares skill `{tok}`, which is not installed"
                            ),
                            why: "The seat's instructions promise a capability the repo cannot \
                                  supply, so the model follows a procedure that is not there.",
                            node: Some(format!("agent:{seat}")),
                            file: Some(format!(".claude/agents/{seat}.md")),
                        });
                    }
                }
            }
        }
    }
}

fn check_broken_tables(c: &Ctx, out: &mut Vec<Finding>) {
    let mut checked = 0usize;
    for n in c.of_type("task").into_iter().chain(c.of_type("doc")) {
        if checked > 400 {
            break;
        }
        let Some(rel) = Ctx::file(n) else { continue };
        let Ok(text) = fs::read_to_string(c.root.join(&rel)) else { continue };
        checked += 1;
        if let Some(line) = blank_line_in_table(&text) {
            out.push(Finding {
                check: "table-blank-line",
                category: "Docs quality",
                sev: Sev::Low,
                title: format!("{rel}: blank line inside a table at line {line}"),
                why: "A blank line terminates a table in GitHub-flavoured Markdown, so every row \
                      after it renders as plain text here and on GitHub.",
                node: n.get("id").and_then(|x| x.as_str()).map(String::from),
                file: Some(rel),
            });
        }
    }
    for extra in ["docs/tasks/master-plan.md"] {
        if let Ok(text) = fs::read_to_string(c.root.join(extra)) {
            if let Some(line) = blank_line_in_table(&text) {
                out.push(Finding {
                    check: "table-blank-line",
                    category: "Docs quality",
                    sev: Sev::Low,
                    title: format!("{extra}: blank line inside a table at line {line}"),
                    why: "A blank line terminates a table in GitHub-flavoured Markdown, so every \
                          row after it renders as plain text here and on GitHub.",
                    node: None,
                    file: Some(extra.into()),
                });
            }
        }
    }
}

/// -> 1-based line number of a blank line that sits between two table rows.
pub fn blank_line_in_table(text: &str) -> Option<usize> {
    let lines: Vec<&str> = text.lines().collect();
    let is_row = |s: &str| {
        let t = s.trim();
        t.starts_with('|') && t.len() > 1
    };
    let mut in_table = false;
    let mut i = 0;
    while i < lines.len() {
        let l = lines[i];
        if is_row(l) {
            in_table = true;
        } else if l.trim().is_empty() && in_table {
            // a blank line only matters if a table row follows it
            if lines.get(i + 1).map(|n| is_row(n)).unwrap_or(false) {
                return Some(i + 1);
            }
            in_table = false;
        } else if !l.trim().is_empty() {
            in_table = false;
        }
        i += 1;
    }
    None
}

// ---------------------------------------------------------------- statistics

fn statistics(c: &Ctx) -> Value {
    let mut by_type: BTreeMap<String, usize> = BTreeMap::new();
    for n in &c.nodes {
        if let Some(t) = n.get("type").and_then(|x| x.as_str()) {
            *by_type.entry(t.to_string()).or_insert(0) += 1;
        }
    }
    let mut by_edge: BTreeMap<String, usize> = BTreeMap::new();
    for e in c.edges {
        if let Some(t) = e.get("type").and_then(|x| x.as_str()) {
            *by_edge.entry(t.to_string()).or_insert(0) += 1;
        }
    }
    let mut by_model: BTreeMap<String, usize> = BTreeMap::new();
    for n in c.of_type("agent") {
        let m = Ctx::meta(n, "model")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .unwrap_or("(unset)");
        *by_model.entry(m.to_string()).or_insert(0) += 1;
    }
    let mut by_status: BTreeMap<String, usize> = BTreeMap::new();
    for n in c.of_type("task") {
        let s = Ctx::meta(n, "status")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .unwrap_or("(none)");
        *by_status.entry(s.to_string()).or_insert(0) += 1;
    }

    // The session tax this project cares about: bytes of rule text that load
    // unconditionally, measured from the files rather than estimated.
    let (mut always_bytes, mut scoped_bytes, mut always_n, mut scoped_n) = (0usize, 0usize, 0, 0);
    for n in c.of_type("rule") {
        let scoped = Ctx::meta(n, "scoped").and_then(|v| v.as_bool()).unwrap_or(false);
        let bytes = Ctx::file(n)
            .and_then(|f| fs::metadata(c.root.join(f)).ok())
            .map(|m| m.len() as usize)
            .unwrap_or(0);
        if scoped {
            scoped_n += 1;
            scoped_bytes += bytes;
        } else {
            always_n += 1;
            always_bytes += bytes;
        }
    }
    let total = always_bytes + scoped_bytes;
    let kept_out = if total > 0 { scoped_bytes * 100 / total } else { 0 };

    let hooks = c.of_type("hook");
    let blocking = hooks
        .iter()
        .filter(|n| Ctx::meta(n, "blocking").and_then(|v| v.as_bool()).unwrap_or(false))
        .count();

    json!({
        "nodes_by_type": by_type,
        "edges_by_type": by_edge,
        "agents_by_model": by_model,
        "tasks_by_status": by_status,
        "rules": {
            "always_on": always_n, "always_on_bytes": always_bytes,
            "path_scoped": scoped_n, "path_scoped_bytes": scoped_bytes,
            "percent_kept_out_of_session": kept_out
        },
        "hooks": { "total": hooks.len(), "blocking": blocking, "advisory": hooks.len() - blocking },
    })
}

// --------------------------------------------------------------------- scores

/// Category scores, each the share of its checks that passed, weighted by
/// severity. Deliberately NOT a single headline number by default: one number
/// invites gaming and hides which half is broken. The overall figure is the
/// plain mean of the categories and the UI shows that derivation.
fn scores(findings: &[Finding]) -> Value {
    const CATS: &[&str] = &["Safety", "Cost control", "Traceability", "Board health", "Docs quality"];
    let weight = |s: Sev| match s {
        Sev::High => 12u32,
        Sev::Medium => 5,
        Sev::Low => 2,
        Sev::Info => 0,
    };
    let mut out = Map::new();
    let mut sum = 0u32;
    let mut n = 0u32;
    for cat in CATS {
        let penalty: u32 = findings
            .iter()
            .filter(|f| f.category == *cat)
            .map(|f| weight(f.sev))
            .sum();
        let score = 100u32.saturating_sub(penalty.min(100));
        out.insert(
            cat.to_string(),
            json!({
                "score": score,
                "findings": findings.iter().filter(|f| f.category == *cat).count(),
                "penalty": penalty
            }),
        );
        sum += score;
        n += 1;
    }
    let overall = if n > 0 { sum / n } else { 100 };
    json!({
        "categories": Value::Object(out),
        "overall": overall,
        "method": "Each category starts at 100 and loses 12 per high finding, 5 per medium, \
                   2 per low, floored at 0. Overall is the plain mean of the five categories. \
                   The weights are a stated convention, not a measurement.",
        "not_measured": [
            "whether the rules say anything useful for this codebase",
            "whether the agents' scopes match how the code is really organised",
            "whether a hook that exists actually blocks what it claims to",
            "code quality, test quality, or the depth of any review"
        ]
    })
}

// ----------------------------------------------------------------- entrypoint

/// Assess a scanned graph. `graph` is the value `scan::scan` produced.
pub fn assess(root: &Path, graph: &Value) -> Value {
    let empty = vec![];
    let nodes: Vec<&Value> = graph
        .get("nodes")
        .and_then(|n| n.as_array())
        .unwrap_or(&empty)
        .iter()
        .collect();
    let edges: &[Value] = graph
        .get("edges")
        .and_then(|e| e.as_array())
        .map(|v| v.as_slice())
        .unwrap_or(&[]);
    let c = Ctx { root, nodes, edges };

    let mut f: Vec<Finding> = Vec::new();
    check_agent_model(&c, &mut f);
    check_agent_tools(&c, &mut f);
    check_reviewer_readonly(&c, &mut f);
    check_spawn_boundary(&c, &mut f);
    check_rule_scoping(&c, &mut f);
    check_hook_wiring(&c, &mut f);
    check_guardrail_layers(&c, &mut f);
    check_task_owners(&c, &mut f);
    check_board(&c, &mut f);
    check_dangling_scripts(&c, &mut f);
    check_skill_wiring(&c, &mut f);
    check_broken_tables(&c, &mut f);

    f.sort_by(|a, b| {
        a.sev
            .rank()
            .cmp(&b.sev.rank())
            .then_with(|| a.check.cmp(b.check))
            .then_with(|| a.title.cmp(&b.title))
    });

    let counts = json!({
        "high": f.iter().filter(|x| x.sev == Sev::High).count(),
        "medium": f.iter().filter(|x| x.sev == Sev::Medium).count(),
        "low": f.iter().filter(|x| x.sev == Sev::Low).count(),
        "info": f.iter().filter(|x| x.sev == Sev::Info).count(),
    });

    json!({
        "version": 1,
        "root": root.display().to_string().replace('\\', "/"),
        "counts": counts,
        "scores": scores(&f),
        "statistics": statistics(&c),
        "findings": f.iter().map(|x| x.to_json()).collect::<Vec<_>>(),
    })
}

/// CLI entry: assess a path and print a report or JSON.
pub fn assess_cli(root: &Path, as_json: bool) -> Result<i32, String> {
    let graph = crate::scan::scan(root);
    let a = assess(root, &graph);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&a).unwrap_or_default());
        return Ok(0);
    }
    let counts = &a["counts"];
    println!("harness assessment: {}", a["root"].as_str().unwrap_or(""));
    println!(
        "  overall {}/100   high {}  medium {}  low {}",
        a["scores"]["overall"], counts["high"], counts["medium"], counts["low"]
    );
    if let Some(cats) = a["scores"]["categories"].as_object() {
        for (k, v) in cats {
            println!("    {:<14} {:>3}/100  ({} findings)", k, v["score"], v["findings"]);
        }
    }
    if let Some(list) = a["findings"].as_array() {
        if !list.is_empty() {
            println!("\n  findings, worst first:");
        }
        for x in list.iter().take(40) {
            println!(
                "    [{}] {}",
                x["severity"].as_str().unwrap_or("?"),
                x["title"].as_str().unwrap_or("")
            );
        }
        if list.len() > 40 {
            println!("    ... and {} more", list.len() - 40);
        }
    }
    // exit 1 when anything high is outstanding, so CI can gate on it
    Ok(if counts["high"].as_u64().unwrap_or(0) > 0 { 1 } else { 0 })
}
