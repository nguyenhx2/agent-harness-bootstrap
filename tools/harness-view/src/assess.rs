//! Deterministic harness assessment. No model, no network, no heuristics that
//! need judgment: every finding is a rule that reads the scanned graph plus a
//! few files on disk and reports what it saw, with the file and line that prove
//! it.
//!
//! The rules are NOT invented here. They are the quality gate that
//! `harness-bootstrap/SKILL.md` already asserts, restated as code so a harness
//! can be checked after it drifts rather than only at the moment it is built.
//! Each one is published in `src/rubric.rs` (and RUBRIC.md, generated from it)
//! with its id, weight, effort, the purposes it applies to, and - in English and
//! Japanese - what full marks means, why it matters and how to fix it. Nothing
//! here writes a title or a reason of its own: a finding is a rubric entry plus
//! the evidence.
//!
//! Beyond the findings, an assessment carries:
//!   - `scores` with the derivation per category, so the number can be redone by hand
//!   - `worklist`: the rules to fix first, by weight times count divided by effort
//!   - `purposes`: what the repository is for, which decides the rules that apply
//!   - `action` on a finding the viewer can fix in one click through `POST /agent`

use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

pub use crate::rubric::Sev;
use crate::rubric::{self, Applies};

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

/// Seats the gate requires to be read-only. The role is matched by
/// `scan::is_review_seat`, so a `security-privacy-reviewer` or a `fact-checker`
/// is held to the same rule. An `editor` counts as the review gate of a writing
/// repository but is not held read-only: an editor that corrects copy is doing
/// the job, not self-approving.
fn read_only_seat(name: &str) -> bool {
    crate::scan::is_review_seat(name) && name != "editor"
}

/// Destructive operations the gate expects `permissions.deny` to cover. Matched
/// as substrings against the deny list, because the real command is
/// project-specific. (label, needle, the entry the fix suggests)
const DENY_EXPECT: &[(&str, &str, &str)] = &[
    ("force push", "push --force", "Bash(git push --force *)"),
    ("recursive delete", "rm -rf", "Bash(rm -rf *)"),
    ("secret read", ".env", "Read(./**/.env)"),
];

/// Seats that only exist in a code repository. Used to infer the purpose when
/// `.claude/state/vars.json` does not record it.
const CODE_SEATS: &[&str] = &[
    "qa-test", "code-reviewer", "security-reviewer", "reviewer", "merge-manager",
    "spec-guardian", "devops", "debugger", "data-modeler", "db-engineer", "db-seeder",
];

/// One thing that is true about this harness: a rubric entry, what it is about,
/// and where the proof is.
pub struct Finding {
    pub check: &'static str,
    /// Substituted for `{name}` in the rubric templates.
    pub name: String,
    /// Substituted for `{extra}`.
    pub extra: String,
    /// The node this is about, so the UI can select it in the graph.
    pub node: Option<String>,
    /// The file that proves it, and the line in it.
    pub file: Option<String>,
    pub line: Option<usize>,
    /// A one-click fix the viewer can apply: `{"endpoint", "label", "label_ja", "body"}`.
    pub action: Option<Value>,
}

impl Finding {
    fn new(check: &'static str, name: impl Into<String>, extra: impl Into<String>) -> Self {
        Finding {
            check,
            name: name.into(),
            extra: extra.into(),
            node: None,
            file: None,
            line: None,
            action: None,
        }
    }
    fn node(mut self, n: impl Into<String>) -> Self {
        self.node = Some(n.into());
        self
    }
    fn at(mut self, file: Option<String>, line: Option<usize>) -> Self {
        self.file = file;
        self.line = line;
        self
    }
    fn action(mut self, a: Option<Value>) -> Self {
        self.action = a;
        self
    }
    pub fn rule(&self) -> &'static rubric::Rule {
        rubric::rule(self.check)
    }
    /// Identity across two assessments of the same repository.
    pub fn key(&self) -> String {
        format!("{}|{}|{}|{}", self.check, self.node.as_deref().unwrap_or(""), self.name, self.extra)
    }
    fn to_json(&self) -> Value {
        let r = self.rule();
        let t = |i: usize| rubric::render(r.title[i], &self.name, &self.extra);
        let w = |i: usize| rubric::render(r.why[i], &self.name, &self.extra);
        let fx = |i: usize| rubric::render(r.fix[i], &self.name, &self.extra);
        let evidence = match (&self.file, self.line) {
            (Some(f), Some(l)) => Some(format!("{f}:{l}")),
            (Some(f), None) => Some(f.clone()),
            _ => None,
        };
        let mut o = json!({
            "rubric": r.id,
            "check": r.check,
            "category": r.category,
            "category_ja": rubric::category_ja(r.category),
            "severity": r.sev.as_str(),
            "weight": r.sev.weight(),
            "effort": r.effort,
            "title": t(0), "title_ja": t(1),
            "why": w(0), "why_ja": w(1),
            "fix": fx(0), "fix_ja": fx(1),
            "node": self.node,
            "file": self.file,
            "line": self.line,
            "evidence": evidence,
            "key": self.key(),
        });
        if let Some(a) = &self.action {
            o["action"] = a.clone();
        }
        o
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
    fn list(n: &Value, k: &str) -> Vec<String> {
        match Ctx::meta(n, k) {
            Some(Value::Array(a)) => a.iter().filter_map(|x| x.as_str().map(String::from)).collect(),
            _ => Vec::new(),
        }
    }
    fn text(&self, rel: &str) -> String {
        fs::read_to_string(self.root.join(rel)).unwrap_or_default()
    }
}

// ------------------------------------------------------------------ evidence

/// 1-based line of the first line `pred` accepts.
fn line_where(text: &str, pred: impl Fn(&str) -> bool) -> Option<usize> {
    text.lines().position(pred).map(|i| i + 1)
}

/// Where a frontmatter key is, or - when it is missing - the closing `---`,
/// which is where it would be added. Line 1 for a file with no frontmatter.
fn fm_line(text: &str, key: &str) -> usize {
    let lines: Vec<&str> = text.lines().collect();
    if lines.first().map(|l| l.trim_start_matches('\u{feff}').trim()) != Some("---") {
        return 1;
    }
    for (i, l) in lines.iter().enumerate().skip(1) {
        if l.trim() == "---" {
            return i + 1;
        }
        if l.starts_with(&format!("{key}:")) {
            return i + 1;
        }
    }
    1
}

/// A tool name the agent editor accepts. A one-click fix is only offered when
/// every tool it would write passes, because the server refuses anything else
/// (`Bash(git diff:*)` included) and a button that always fails is worse than
/// none.
fn tool_ok(s: &str) -> bool {
    !s.is_empty()
        && s.len() <= 64
        && s.chars().all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-' || c == '.' || c == ':')
}

fn agent_action(seat: &str, label: [&str; 2], change: Value) -> Value {
    let mut body = json!({ "name": seat });
    if let (Some(b), Some(c)) = (body.as_object_mut(), change.as_object()) {
        for (k, v) in c {
            b.insert(k.clone(), v.clone());
        }
    }
    json!({ "endpoint": "agent", "label": label[0], "label_ja": label[1], "body": body })
}

// --------------------------------------------------------------------- checks

/// Cost control: model, effort, turns and the tool list, one seat at a time.
fn check_agent_budget(c: &Ctx, out: &mut Vec<Finding>) {
    for n in c.of_type("agent") {
        if Ctx::disabled(n) {
            continue;
        }
        let name = Ctx::name(n).to_string();
        let file = Ctx::file(n);
        let text = file.as_deref().map(|f| c.text(f)).unwrap_or_default();
        let id = format!("agent:{name}");
        let model = Ctx::meta(n, "model").and_then(|v| v.as_str()).unwrap_or("");
        if model.is_empty() || model == "inherit" {
            out.push(
                Finding::new("agent-model", &name, "")
                    .node(&id)
                    .at(file.clone(), Some(fm_line(&text, "model")))
                    .action(Some(agent_action(&name, ["Set model: sonnet", "model: sonnet にする"],
                                              json!({"model": "sonnet"})))),
            );
        }
        if Ctx::meta(n, "effort").and_then(|v| v.as_str()).unwrap_or("").is_empty() {
            out.push(
                Finding::new("agent-effort", &name, "")
                    .node(&id)
                    .at(file.clone(), Some(fm_line(&text, "effort")))
                    .action(Some(agent_action(&name, ["Set effort: medium", "effort: medium にする"],
                                              json!({"effort": "medium"})))),
            );
        }
        if Ctx::meta(n, "maxTurns").is_none() {
            out.push(
                Finding::new("agent-maxturns", &name, "")
                    .node(&id)
                    .at(file.clone(), Some(fm_line(&text, "maxTurns"))),
            );
        }
        if Ctx::list(n, "tools").is_empty() {
            out.push(
                Finding::new("agent-tools", &name, "")
                    .node(&id)
                    .at(file.clone(), Some(fm_line(&text, "tools")))
                    .action(Some(agent_action(
                        &name,
                        ["Set tools: Read, Grep, Glob", "tools: Read, Grep, Glob にする"],
                        json!({"tools": ["Read", "Grep", "Glob"]}),
                    ))),
            );
        }
    }
}

/// Safety: a reviewer that can write is not a gate, it is another author.
fn check_review_seats(c: &Ctx, out: &mut Vec<Finding>) {
    for n in c.of_type("agent") {
        let name = Ctx::name(n).to_string();
        if !read_only_seat(&name) || Ctx::disabled(n) {
            continue;
        }
        let file = Ctx::file(n);
        let text = file.as_deref().map(|f| c.text(f)).unwrap_or_default();
        let id = format!("agent:{name}");
        let tools = Ctx::list(n, "tools");
        let writes = |t: &str| {
            ["Edit", "Write", "NotebookEdit"]
                .iter()
                .any(|b| t == *b || t.starts_with(&format!("{b}(")))
        };
        let kept: Vec<String> = tools.iter().filter(|t| !writes(t)).cloned().collect();
        let fixable = !kept.is_empty() && kept.iter().all(|t| tool_ok(t));
        for bad in tools.iter().filter(|t| writes(t)) {
            out.push(
                Finding::new("reviewer-readonly", &name, bad.clone())
                    .node(&id)
                    .at(file.clone(), Some(fm_line(&text, "tools")))
                    .action(fixable.then(|| {
                        agent_action(
                            &name,
                            ["Remove the write tools", "書き込み系ツールを外す"],
                            json!({ "tools": kept }),
                        )
                    })),
            );
        }
        let dis = Ctx::list(n, "disallowedTools");
        if !(dis.iter().any(|t| t == "Edit") && dis.iter().any(|t| t == "Write")) {
            out.push(
                Finding::new("reviewer-disallowed", &name, "")
                    .node(&id)
                    .at(file.clone(), Some(fm_line(&text, "disallowedTools"))),
            );
        }
        if Ctx::meta(n, "memory").is_some() {
            out.push(
                Finding::new("reviewer-memory", &name, "")
                    .node(&id)
                    .at(file.clone(), Some(fm_line(&text, "memory"))),
            );
        }
    }
}

/// Safety: only the orchestrator may hold a bare `Agent`. `Agent(a, b)` is
/// already bounded and is not reported.
fn check_spawn_boundary(c: &Ctx, out: &mut Vec<Finding>) {
    for n in c.of_type("agent") {
        let name = Ctx::name(n).to_string();
        if name == "orchestrator" || Ctx::disabled(n) {
            continue;
        }
        let tools = Ctx::list(n, "tools");
        if tools.iter().any(|t| t == "Agent" || t == "Task") {
            let file = Ctx::file(n);
            let text = file.as_deref().map(|f| c.text(f)).unwrap_or_default();
            let kept: Vec<String> =
                tools.iter().filter(|t| *t != "Agent" && *t != "Task").cloned().collect();
            let fixable = !kept.is_empty() && kept.iter().all(|t| tool_ok(t));
            out.push(
                Finding::new("spawn-boundary", &name, "")
                    .node(format!("agent:{name}"))
                    .at(file, Some(fm_line(&text, "tools")))
                    .action(fixable.then(|| {
                        agent_action(&name, ["Remove Agent", "Agent を外す"], json!({ "tools": kept }))
                    })),
            );
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
            out.push(Finding::new("rule-scoping", name, "").node(format!("rule:{name}")).at(Ctx::file(n), Some(1)));
        }
    }
}

/// Safety: a registration pointing at a hook file that does not exist is a
/// guardrail that silently never fires, and a hook file nothing registers is a
/// control that enforces nothing.
fn check_hook_wiring(c: &Ctx, out: &mut Vec<Finding>) {
    let hooks_dir = c.root.join(".claude/hooks");
    // Registrations are read from settings.json and the seats' frontmatter rather
    // than from the graph: a registration whose script is missing produces NO
    // node, which is exactly the case that matters most.
    let settings_text = c.text(".claude/settings.json");
    let mut regs: Vec<crate::scan::HookReg> = serde_json::from_str::<Value>(&settings_text)
        .ok()
        .and_then(|v| v.get("hooks").map(|h| crate::scan::hook_regs("settings", h)))
        .unwrap_or_default();
    regs.extend(crate::scan::agent_hook_regs(c.root));
    let registered_names: BTreeSet<String> = regs.iter().filter_map(|r| r.hook.clone()).collect();
    // Any flavour on disk satisfies a registration: `.sh`, `.ps1`, or a `.py`
    // hook the graph does not draw as a node.
    let on_disk_stems: BTreeSet<String> = fs::read_dir(&hooks_dir)
        .map(|rd| {
            rd.flatten()
                .filter(|e| e.path().is_file())
                .filter_map(|e| e.path().file_stem().and_then(|x| x.to_str()).map(String::from))
                .collect()
        })
        .unwrap_or_default();
    for name in &registered_names {
        if on_disk_stems.contains(name) {
            continue;
        }
        let src = regs
            .iter()
            .find(|r| r.hook.as_deref() == Some(name.as_str()))
            .map(|r| match r.source.strip_prefix("agent:") {
                Some(a) => format!(".claude/agents/{a}.md"),
                None => ".claude/settings.json".to_string(),
            });
        let line = src.as_deref().and_then(|f| {
            let t = c.text(f).replace('\\', "/");
            line_where(&t, |l| l.contains(&format!("hooks/{name}")))
        });
        out.push(Finding::new("hook-missing-file", name, "").at(src, line));
    }

    for n in c.of_type("hook") {
        let name = Ctx::name(n);
        let registered = registered_names.contains(name);
        let on_disk = ["sh", "ps1"].iter().any(|e| hooks_dir.join(format!("{name}.{e}")).is_file());
        // A helper that registered hooks source (`_lib.sh`) is not meant to be
        // registered; the scan marks it `library`.
        let library = Ctx::meta(n, "library").and_then(|v| v.as_bool()) == Some(true);
        if !registered && on_disk && !library && !Ctx::disabled(n) {
            out.push(Finding::new("hook-unregistered", name, "").node(format!("hook:{name}")).at(Ctx::file(n), Some(1)));
        }
    }
}

/// Safety: the four layers the gate requires. Missing any one is reported
/// individually so the fix is obvious.
fn check_guardrail_layers(c: &Ctx, out: &mut Vec<Finding>, purposes: &[String]) {
    let settings_rel = ".claude/settings.json";
    let text = c.text(settings_rel);
    let deny: Vec<String> = serde_json::from_str::<Value>(&text)
        .ok()
        .and_then(|v| {
            v.get("permissions")
                .and_then(|p| p.get("deny"))
                .and_then(|d| d.as_array())
                .map(|a| a.iter().filter_map(|x| x.as_str()).map(|s| s.to_string()).collect())
        })
        .unwrap_or_default();
    let settings_file = Some(settings_rel.to_string());
    if deny.is_empty() {
        let line = line_where(&text, |l| l.contains("\"permissions\"")).or(Some(1));
        out.push(Finding::new("deny-list", "", "").node("settings").at(settings_file.clone(), line));
    } else {
        let line = line_where(&text, |l| l.contains("\"deny\""));
        for (label, needle, entry) in DENY_EXPECT {
            if !deny.iter().any(|d| d.contains(needle)) {
                out.push(Finding::new("deny-coverage", *label, *entry).node("settings").at(settings_file.clone(), line));
            }
        }
    }

    // A Stop or UserPromptSubmit hook can block too, but not a tool call, and
    // stopping a tool call is the layer this finding is about.
    let gating = c
        .of_type("hook")
        .iter()
        .filter(|n| {
            let ev = Ctx::meta(n, "event").and_then(|v| v.as_str()).unwrap_or("");
            let more = Ctx::list(n, "events");
            let gates = crate::scan::TOOL_GATE_EVENTS.contains(&ev)
                || more.iter().any(|x| {
                    crate::scan::TOOL_GATE_EVENTS
                        .iter()
                        .any(|g| x == g || x.starts_with(&format!("{g} ")))
                });
            gates && !Ctx::disabled(n)
        })
        .count();
    if gating == 0 {
        let line = line_where(&text, |l| l.contains("\"hooks\""));
        out.push(Finding::new("no-blocking-hook", "", "").at(settings_file.clone(), line));
    }

    if !c.root.join(".claude/rules/agent-guardrails.md").is_file() {
        out.push(Finding::new("no-guardrail-rule", "", "").at(Some(".claude/rules/agent-guardrails.md".into()), None));
    }

    // Match the ROLE, not one project's spelling of it: `/review-changes`,
    // `/review-pr` and `/mr-review` are all the same gate.
    let has_review_cmd = c.of_type("command").iter().any(|n| {
        let name = Ctx::name(n);
        !Ctx::disabled(n) && (name.starts_with("review") || name.ends_with("-review"))
    });
    let agents: Vec<&Value> = c.of_type("agent").into_iter().filter(|n| !Ctx::disabled(n)).collect();
    let has_reviewer_seat = agents.iter().any(|n| crate::scan::is_review_seat(Ctx::name(n)));
    if !has_review_cmd && !has_reviewer_seat {
        out.push(Finding::new("no-review-gate", "", "").at(Some(".claude/agents/".into()), None));
    } else if !has_review_cmd {
        out.push(Finding::new("no-review-command", "", "").at(Some(".claude/commands/".into()), None));
    }

    // A deliverable that is not code still needs a seat that only reads it.
    if purposes.iter().any(|p| p != "code") {
        let read_only_checker = agents.iter().any(|n| {
            let tools = Ctx::list(n, "tools");
            crate::scan::is_review_seat(Ctx::name(n))
                && !tools.is_empty()
                && !tools.iter().any(|t| {
                    ["Edit", "Write", "NotebookEdit"]
                        .iter()
                        .any(|b| t == b || t.starts_with(&format!("{b}(")))
                })
        });
        if !read_only_checker {
            out.push(Finding::new("noncode-checker", "", "").at(Some(".claude/agents/".into()), None));
        }
    }
}

/// Traceability: a task owned by a seat that was never fielded has nobody to do
/// it, and the board will not say so.
fn check_task_owners(c: &Ctx, out: &mut Vec<Finding>) {
    let agents: BTreeSet<String> =
        c.of_type("agent").iter().map(|n| Ctx::name(n).to_string()).collect();
    for n in c.of_type("task") {
        let owner = Ctx::meta(n, "owner").and_then(|v| v.as_str()).unwrap_or("");
        if owner.is_empty() || owner == "-" {
            continue;
        }
        let file = Ctx::file(n);
        let text = file.as_deref().map(|f| c.text(f)).unwrap_or_default();
        let line = line_where(&text, |l| l.starts_with("owner:") || l.starts_with("agent:"));
        for seat in owner.split('+').map(str::trim).filter(|s| !s.is_empty()) {
            if !agents.contains(seat) {
                out.push(
                    Finding::new("task-owner-missing", Ctx::name(n), seat)
                        .node(format!("task:{}", Ctx::name(n)))
                        .at(file.clone(), line),
                );
            }
        }
    }
}

/// Board health: blocked with no unblocker, no status at all, and an
/// orchestrator-kit board that disagrees with itself.
fn check_board(c: &Ctx, out: &mut Vec<Finding>) {
    for n in c.of_type("task") {
        let name = Ctx::name(n);
        let status = Ctx::meta(n, "status").and_then(|v| v.as_str()).unwrap_or("");
        let deps = Ctx::meta(n, "deps").and_then(|v| v.as_str()).unwrap_or("");
        let file = Ctx::file(n);
        let text = file.as_deref().map(|f| c.text(f)).unwrap_or_default();
        let id = format!("task:{name}");
        if status.eq_ignore_ascii_case("blocked") && (deps.is_empty() || deps == "-") {
            out.push(
                Finding::new("blocked-no-unblocker", name, "")
                    .node(&id)
                    .at(file.clone(), line_where(&text, |l| l.starts_with("status:"))),
            );
        }
        // orchestrator-kit keeps a task's state in three places - its folder,
        // its `status:` and its TASKS.md row - and `task.sh check` fails when they
        // disagree. The scan records each disagreement.
        let drift = Ctx::list(n, "drift");
        if !drift.is_empty() {
            // a task with no file is a TASKS.md row; point at that row instead
            let (f, l) = match &file {
                Some(_) => (file.clone(), line_where(&text, |l| l.starts_with("status:"))),
                None => {
                    let board = Ctx::meta(n, "board").and_then(|b| b.as_str()).unwrap_or(".agent-base/tasks");
                    let idx = format!("{board}/TASKS.md");
                    let t = c.text(&idx);
                    let l = line_where(&t, |l| l.contains(&format!("| {name} ")));
                    (Some(idx), l)
                }
            };
            for d in drift {
                out.push(Finding::new("board-drift", name, d).node(&id).at(f.clone(), l));
            }
        }
        if status.is_empty() {
            out.push(Finding::new("task-no-status", name, "").node(&id).at(file.clone(), Some(fm_line(&text, "status"))));
        }
    }
}

/// Traceability: a command that runs a script which is not installed fails at
/// the moment someone needs it.
fn check_dangling_scripts(c: &Ctx, out: &mut Vec<Finding>) {
    let ids: BTreeSet<&str> = c.nodes.iter().filter_map(|n| n.get("id").and_then(|x| x.as_str())).collect();
    for e in c.edges {
        if e.get("type").and_then(|x| x.as_str()) != Some("runs") {
            continue;
        }
        let to = e.get("to").and_then(|x| x.as_str()).unwrap_or("");
        let from = e.get("from").and_then(|x| x.as_str()).unwrap_or("");
        if ids.contains(to) {
            continue;
        }
        let script = to.strip_prefix("script:").unwrap_or(to);
        let file = c
            .nodes
            .iter()
            .find(|n| n.get("id").and_then(|x| x.as_str()) == Some(from))
            .and_then(|n| Ctx::file(n));
        let line = file.as_deref().and_then(|f| {
            let t = c.text(f).replace('\\', "/");
            line_where(&t, |l| l.contains(&format!("scripts/{script}")))
        });
        out.push(Finding::new("dangling-script", from, to).node(from).at(file, line));
    }
}

/// Traceability: a skill sitting in `.claude/skills/` that no seat declares is
/// procedural text nobody follows, and a seat declaring a skill that is not
/// installed promises a procedure that is not there.
fn check_skill_wiring(c: &Ctx, out: &mut Vec<Finding>) {
    let wired: BTreeSet<&str> = c
        .edges
        .iter()
        .filter(|e| e.get("type").and_then(|x| x.as_str()) == Some("uses"))
        .filter_map(|e| e.get("to").and_then(|x| x.as_str()))
        .collect();
    for n in c.of_type("skill") {
        let id = n.get("id").and_then(|x| x.as_str()).unwrap_or("");
        if wired.contains(id) {
            continue;
        }
        let label = n.get("label").and_then(|x| x.as_str()).unwrap_or(id);
        out.push(Finding::new("skill-not-wired", label, "").node(id).at(Ctx::file(n), Some(1)));
    }

    // A wire to an uninstalled skill produces no edge, by design, so the graph
    // cannot reveal it. Read the seat files directly.
    let installed: BTreeSet<String> = c
        .of_type("skill")
        .iter()
        .filter_map(|n| n.get("label").and_then(|x| x.as_str()).map(|s| s.to_string()))
        .collect();
    let agents_dir = c.root.join(".claude/agents");
    let mut seats: Vec<String> = fs::read_dir(&agents_dir)
        .map(|rd| {
            rd.flatten()
                .map(|e| e.path())
                .filter(|p| p.extension().and_then(|x| x.to_str()) == Some("md"))
                .filter_map(|p| p.file_stem().and_then(|x| x.to_str()).map(String::from))
                .collect()
        })
        .unwrap_or_default();
    seats.sort();
    for seat in seats {
        let rel = format!(".claude/agents/{seat}.md");
        let text = c.text(&rel);
        for (i, line) in text.lines().enumerate() {
            if let Some(val) = crate::scan::skill_decl_value(line) {
                for tok in crate::scan::slug_tokens(val) {
                    if !installed.contains(&tok) {
                        out.push(
                            Finding::new("skill-wire-missing", &seat, tok)
                                .node(format!("agent:{seat}"))
                                .at(Some(rel.clone()), Some(i + 1)),
                        );
                    }
                }
            }
        }
    }
}

/// Docs quality: a blank line inside a GFM table ends it, so the remaining rows
/// render as a paragraph of pipes.
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
            out.push(
                Finding::new("table-blank-line", &rel, line.to_string())
                    .node(n.get("id").and_then(|x| x.as_str()).unwrap_or(""))
                    .at(Some(rel.clone()), Some(line)),
            );
        }
    }
    let extra = "docs/tasks/master-plan.md";
    if let Ok(text) = fs::read_to_string(c.root.join(extra)) {
        if let Some(line) = blank_line_in_table(&text) {
            out.push(Finding::new("table-blank-line", extra, line.to_string()).at(Some(extra.into()), Some(line)));
        }
    }
}

/// The contract itself, its routing tiers, per-folder stubs and its length.
fn check_instruction_files(c: &Ctx, out: &mut Vec<Finding>) {
    let instr = c.of_type("instruction");
    let has = |key: &str| {
        instr.iter().any(|n| n.get("id").and_then(|x| x.as_str()) == Some(&format!("instr:{key}")))
    };
    if !has("agents") {
        out.push(Finding::new("instruction-contract", "", "").at(Some("AGENTS.md".into()), None));
        return;
    }
    let tiered = instr
        .iter()
        .any(|n| n.get("tiers").and_then(|t| t.as_array()).map(|a| !a.is_empty()).unwrap_or(false));
    if !tiered {
        out.push(Finding::new("instruction-tiers", "", "").node("instr:agents").at(Some("AGENTS.md".into()), Some(1)));
    }
    // Per-folder contracts. A nested CLAUDE.md governs its own subtree, which
    // makes an empty one worse than none.
    for n in &instr {
        let file = n.get("file").and_then(|x| x.as_str()).unwrap_or("");
        // Only a nested CLAUDE.md / AGENTS.md / GEMINI.md governs a subtree. A
        // `.cursor/rules/x.mdc` or `.kiro/steering/x.md` is a rule file of its
        // tool, not a per-folder contract, and short is a fine size for a rule.
        let id = n.get("id").and_then(|x| x.as_str()).unwrap_or("");
        let key = id.strip_prefix("instr:").and_then(|r| r.split('/').next()).unwrap_or("");
        if !file.contains('/') || !matches!(key, "claude" | "agents" | "gemini") {
            continue;
        }
        let bytes = n.get("meta").and_then(|m| m.get("bytes")).and_then(|b| b.as_u64()).unwrap_or(u64::MAX);
        if bytes < 120 {
            out.push(
                Finding::new("instruction-nested-stub", file, "")
                    .node(n.get("id").and_then(|x| x.as_str()).unwrap_or(""))
                    .at(Some(file.to_string()), Some(1)),
            );
        }
    }
    // Both load in every session; the gate puts the pair under ~200 lines.
    let lines = c.text("CLAUDE.md").lines().count() + c.text("AGENTS.md").lines().count();
    if lines >= 200 {
        out.push(
            Finding::new("instruction-length", "", lines.to_string())
                .node("instr:agents")
                .at(Some("AGENTS.md".into()), Some(1)),
        );
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

// ------------------------------------------------------------------ purposes

/// What the repository is for: `code`, `research`, `strategy`, `docs`, in that
/// order, and where that came from. The scaffolder records its `purpose_*`
/// flags in the vars.json `/harness-update` reuses; without one the roster
/// says it - a `researcher` means research, a dev or review seat means code.
/// Nothing recognisable means code, the scaffolder's own default.
pub fn purposes(root: &Path, graph: &Value) -> (Vec<String>, &'static str) {
    const ORDER: &[&str] = &["code", "research", "strategy", "docs"];
    let order = |set: BTreeSet<String>| -> Vec<String> {
        ORDER.iter().filter(|p| set.contains(**p)).map(|p| p.to_string()).collect()
    };
    if let Ok(t) = fs::read_to_string(root.join(".claude/state/vars.json")) {
        if let Ok(v) = serde_json::from_str::<Value>(&t) {
            let set: BTreeSet<String> = v
                .get("flags")
                .and_then(|f| f.as_array())
                .map(|a| {
                    a.iter()
                        .filter_map(|x| x.as_str())
                        .filter_map(|x| x.strip_prefix("purpose_").map(String::from))
                        .collect()
                })
                .unwrap_or_default();
            if !set.is_empty() {
                return (order(set), "vars.json");
            }
        }
    }
    let mut set = BTreeSet::new();
    for n in graph.get("nodes").and_then(|n| n.as_array()).map(|a| a.as_slice()).unwrap_or(&[]) {
        if n.get("type").and_then(|t| t.as_str()) != Some("agent") || Ctx::disabled(n) {
            continue;
        }
        let name = Ctx::name(n);
        if name.ends_with("-dev") || CODE_SEATS.contains(&name) {
            set.insert("code".to_string());
        }
        match name {
            "researcher" => {
                set.insert("research".to_string());
            }
            "strategist" => {
                set.insert("strategy".to_string());
            }
            "writer" | "editor" => {
                set.insert("docs".to_string());
            }
            _ => {}
        }
    }
    if root.join(".claude/state/code-graph.json").is_file() {
        set.insert("code".to_string());
    }
    if set.is_empty() {
        return (vec!["code".to_string()], "default");
    }
    (order(set), "roster")
}

fn applies(r: &rubric::Rule, purposes: &[String]) -> bool {
    match r.applies {
        Applies::All => true,
        Applies::Code => purposes.iter().any(|p| p == "code"),
        Applies::NonCode => purposes.iter().any(|p| p != "code"),
    }
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
        let m = Ctx::meta(n, "model").and_then(|v| v.as_str()).filter(|s| !s.is_empty()).unwrap_or("(unset)");
        *by_model.entry(m.to_string()).or_insert(0) += 1;
    }
    let mut by_status: BTreeMap<String, usize> = BTreeMap::new();
    for n in c.of_type("task") {
        let s = Ctx::meta(n, "status").and_then(|v| v.as_str()).filter(|s| !s.is_empty()).unwrap_or("(none)");
        *by_status.entry(s.to_string()).or_insert(0) += 1;
    }

    // The session tax: bytes of rule text that load unconditionally, measured
    // from the files rather than estimated.
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
    let kept_out = (scoped_bytes * 100).checked_div(total).unwrap_or(0);

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

/// Overall score of a set of findings: the method in `rubric::METHOD`.
fn overall_of(findings: &[&Finding]) -> u32 {
    let n = rubric::CATEGORIES.len() as u32;
    let sum: u32 = rubric::CATEGORIES
        .iter()
        .map(|(cat, _)| {
            let penalty: u32 =
                findings.iter().filter(|f| f.rule().category == *cat).map(|f| f.rule().sev.weight()).sum();
            100u32.saturating_sub(penalty.min(100))
        })
        .sum();
    sum.checked_div(n).unwrap_or(100)
}

/// Category scores with their derivation: which rules took how much, so the
/// number can be checked against RUBRIC.md by hand.
fn scores(findings: &[Finding]) -> Value {
    let mut cats = Map::new();
    for (cat, cat_ja) in rubric::CATEGORIES {
        let mine: Vec<&Finding> = findings.iter().filter(|f| f.rule().category == *cat).collect();
        let mut by_rule: BTreeMap<&str, (u32, u32)> = BTreeMap::new();
        for f in &mine {
            let e = by_rule.entry(f.rule().id).or_insert((0, f.rule().sev.weight()));
            e.0 += 1;
        }
        let penalty: u32 = by_rule.values().map(|(n, w)| n * w).sum();
        let derivation: Vec<Value> = by_rule
            .iter()
            .filter(|(_, (_, w))| *w > 0)
            .map(|(id, (n, w))| json!({"rubric": id, "count": n, "weight": w, "points": n * w}))
            .collect();
        cats.insert(
            cat.to_string(),
            json!({
                "score": 100u32.saturating_sub(penalty.min(100)),
                "findings": mine.len(),
                "penalty": penalty,
                "label_ja": cat_ja,
                "derivation": derivation,
            }),
        );
    }
    let all: Vec<&Finding> = findings.iter().collect();
    json!({
        "categories": Value::Object(cats),
        "overall": overall_of(&all),
        "method": rubric::METHOD[0],
        "method_ja": rubric::METHOD[1],
        "not_measured": rubric::NOT_MEASURED.iter().map(|x| x[0]).collect::<Vec<_>>(),
        "not_measured_ja": rubric::NOT_MEASURED.iter().map(|x| x[1]).collect::<Vec<_>>(),
    })
}

/// The rules to fix first. One entry per rubric rule with findings, ordered by
/// `points * 6 / effort` (points = weight times count; 6 keeps efforts 1, 2 and
/// 3 integral), then severity, then id. `gain` is what the overall score would
/// become with that rule's findings gone - honest about the floor at 0.
fn worklist(findings: &[Finding]) -> Value {
    let all: Vec<&Finding> = findings.iter().collect();
    let now = overall_of(&all);
    let mut groups: BTreeMap<&str, Vec<&Finding>> = BTreeMap::new();
    for f in findings {
        groups.entry(f.rule().id).or_default().push(f);
    }
    let mut rows: Vec<(u32, u8, &str, Value)> = Vec::new();
    for (id, fs_) in groups {
        let r = fs_[0].rule();
        let points = r.sev.weight() * fs_.len() as u32;
        if points == 0 {
            continue;
        }
        let rest: Vec<&Finding> = all.iter().copied().filter(|f| f.rule().id != id).collect();
        let after = overall_of(&rest);
        let priority = points * 6 / u32::from(r.effort.max(1));
        let one_click = fs_.iter().filter(|f| f.action.is_some()).count();
        // One finding: its fix verbatim. Several: the fix with the subject left
        // as a placeholder, and the subjects listed beside it.
        let single = fs_.len() == 1;
        let fix = |i: usize| {
            let (n, e) = if single {
                (fs_[0].name.clone(), fs_[0].extra.clone())
            } else {
                (["<name>", "<名前>"][i].to_string(), ["<value>", "<値>"][i].to_string())
            };
            rubric::render(r.fix[i], &n, &e)
        };
        let mut names: Vec<String> = fs_.iter().map(|f| f.name.clone()).filter(|n| !n.is_empty()).collect();
        names.dedup();
        rows.push((
            priority,
            r.sev.rank(),
            r.id,
            json!({
                "rubric": r.id, "check": r.check, "severity": r.sev.as_str(),
                "category": r.category, "category_ja": rubric::category_ja(r.category),
                "title": r.title[0], "title_ja": r.title[1], "full": r.full[0], "full_ja": r.full[1],
                "fix": fix(0), "fix_ja": fix(1), "names": names,
                "count": fs_.len(), "effort": r.effort, "points": points, "priority": priority,
                "one_click": one_click,
                "overall_after": after, "gain": after.saturating_sub(now),
                "keys": fs_.iter().map(|f| f.key()).collect::<Vec<_>>(),
            }),
        ));
    }
    rows.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)).then(a.2.cmp(b.2)));
    Value::Array(rows.into_iter().map(|r| r.3).collect())
}

// ----------------------------------------------------------------------- diff

/// What changed between two assessments of the same repository: findings fixed
/// and introduced (matched by `key`), and every score that moved. `prev` and
/// `cur` are `assess()` outputs; a previous one from an older version without
/// keys simply reports everything as new.
pub fn diff(prev: &Value, cur: &Value) -> Value {
    let index = |a: &Value| -> BTreeMap<String, Value> {
        a.get("findings")
            .and_then(|f| f.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|f| f.get("key").and_then(|k| k.as_str()).map(|k| (k.to_string(), f.clone())))
                    .collect()
            })
            .unwrap_or_default()
    };
    let (p, c) = (index(prev), index(cur));
    let fixed: Vec<Value> = p.iter().filter(|(k, _)| !c.contains_key(*k)).map(|(_, v)| v.clone()).collect();
    let new: Vec<Value> = c.iter().filter(|(k, _)| !p.contains_key(*k)).map(|(_, v)| v.clone()).collect();
    let unchanged = c.keys().filter(|k| p.contains_key(*k)).count();
    let score = |a: &Value, path: &[&str]| -> Value {
        let mut v = a;
        for s in path {
            v = v.get(*s).unwrap_or(&Value::Null);
        }
        v.clone()
    };
    let mut cats = Map::new();
    for (cat, _) in rubric::CATEGORIES {
        let from = score(prev, &["scores", "categories", cat, "score"]);
        let to = score(cur, &["scores", "categories", cat, "score"]);
        if from != to {
            cats.insert(cat.to_string(), json!({"from": from, "to": to}));
        }
    }
    json!({
        "fixed": fixed,
        "new": new,
        "unchanged": unchanged,
        "overall": {"from": score(prev, &["scores", "overall"]), "to": score(cur, &["scores", "overall"])},
        "categories": cats,
    })
}

/// Nodes added and removed between two scans, by id.
pub fn graph_diff(prev: &Value, cur: &Value) -> Value {
    let ids = |g: &Value| -> BTreeSet<String> {
        g.get("nodes")
            .and_then(|n| n.as_array())
            .map(|a| a.iter().filter_map(|n| n.get("id").and_then(|i| i.as_str()).map(String::from)).collect())
            .unwrap_or_default()
    };
    let edges = |g: &Value| -> BTreeSet<String> {
        g.get("edges")
            .and_then(|n| n.as_array())
            .map(|a| a.iter().map(|e| format!("{} -{}-> {}", e["from"].as_str().unwrap_or(""),
                                               e["type"].as_str().unwrap_or(""), e["to"].as_str().unwrap_or(""))).collect())
            .unwrap_or_default()
    };
    let (a, b) = (ids(prev), ids(cur));
    let (ea, eb) = (edges(prev), edges(cur));
    json!({
        "nodes_added": b.difference(&a).collect::<Vec<_>>(),
        "nodes_removed": a.difference(&b).collect::<Vec<_>>(),
        "edges_added": eb.difference(&ea).collect::<Vec<_>>(),
        "edges_removed": ea.difference(&eb).collect::<Vec<_>>(),
    })
}

// ----------------------------------------------------------------- entrypoint

/// Assess a scanned graph. `graph` is the value `scan::scan` produced.
pub fn assess(root: &Path, graph: &Value) -> Value {
    assess_with(root, graph, None)
}

/// Assess with the purposes given rather than detected (`--purpose`).
pub fn assess_with(root: &Path, graph: &Value, purpose_override: Option<Vec<String>>) -> Value {
    let empty = vec![];
    let nodes: Vec<&Value> = graph.get("nodes").and_then(|n| n.as_array()).unwrap_or(&empty).iter().collect();
    let edges: &[Value] = graph.get("edges").and_then(|e| e.as_array()).map(|v| v.as_slice()).unwrap_or(&[]);
    let c = Ctx { root, nodes, edges };
    let (purposes, source) = match purpose_override {
        Some(p) if !p.is_empty() => (p, "given"),
        _ => purposes(root, graph),
    };

    let mut f: Vec<Finding> = Vec::new();
    check_agent_budget(&c, &mut f);
    check_review_seats(&c, &mut f);
    check_spawn_boundary(&c, &mut f);
    check_rule_scoping(&c, &mut f);
    check_hook_wiring(&c, &mut f);
    check_guardrail_layers(&c, &mut f, &purposes);
    check_task_owners(&c, &mut f);
    check_board(&c, &mut f);
    check_dangling_scripts(&c, &mut f);
    check_skill_wiring(&c, &mut f);
    check_broken_tables(&c, &mut f);
    check_instruction_files(&c, &mut f);
    // A rule about code does not grade a research repository, and a rule about
    // deliverables does not grade a code one.
    f.retain(|x| applies(x.rule(), &purposes));
    // an empty node id is "about no node"
    for x in f.iter_mut() {
        if x.node.as_deref() == Some("") {
            x.node = None;
        }
    }

    f.sort_by(|a, b| {
        a.rule()
            .sev
            .rank()
            .cmp(&b.rule().sev.rank())
            .then_with(|| a.rule().id.cmp(b.rule().id))
            .then_with(|| a.key().cmp(&b.key()))
    });

    let count = |s: Sev| f.iter().filter(|x| x.rule().sev == s).count();
    let counts = json!({
        "high": count(Sev::High), "medium": count(Sev::Medium),
        "low": count(Sev::Low), "info": count(Sev::Info),
    });
    let skipped: Vec<&str> = rubric::RULES.iter().filter(|r| !applies(r, &purposes)).map(|r| r.id).collect();

    // Without the strip a canonicalized Windows path printed as `//?/D:/...`.
    let shown = root.display().to_string();
    let root_text = shown.strip_prefix(r"\\?\").unwrap_or(&shown).replace('\\', "/");
    json!({
        "version": 1,
        "root": root_text,
        "purposes": {"list": purposes, "source": source, "rules_not_applied": skipped},
        "counts": counts,
        "scores": scores(&f),
        "worklist": worklist(&f),
        "statistics": statistics(&c),
        "findings": f.iter().map(|x| x.to_json()).collect::<Vec<_>>(),
    })
}

/// CLI options for `assess`.
#[derive(Default)]
pub struct CliOpts {
    pub json: bool,
    pub ja: bool,
    pub since: Option<std::path::PathBuf>,
    pub purposes: Option<Vec<String>>,
}

/// CLI entry: assess a path and print a report or JSON.
pub fn assess_cli(root: &Path, o: &CliOpts) -> Result<i32, String> {
    let graph = crate::scan::scan(root);
    let mut a = assess_with(root, &graph, o.purposes.clone());
    let since = match &o.since {
        Some(p) => {
            let t = fs::read_to_string(p).map_err(|e| format!("--since {}: {e}", p.display()))?;
            let prev: Value = serde_json::from_str(&t).map_err(|e| format!("--since {}: {e}", p.display()))?;
            Some(diff(&prev, &a))
        }
        None => None,
    };
    if o.json {
        if let Some(d) = since {
            a["since"] = d;
        }
        println!("{}", serde_json::to_string_pretty(&a).unwrap_or_default());
        return Ok(0);
    }
    let i = usize::from(o.ja);
    let pick = |v: &Value, k: &str| -> String {
        let key = if o.ja { format!("{k}_ja") } else { k.to_string() };
        v[key.as_str()].as_str().or(v[k].as_str()).unwrap_or("").to_string()
    };
    let counts = &a["counts"];
    let purposes = a["purposes"]["list"].as_array().map(|p| {
        p.iter().filter_map(|x| x.as_str()).collect::<Vec<_>>().join(", ")
    }).unwrap_or_default();
    println!("{}: {}", ["harness assessment", "ハーネス評価"][i], a["root"].as_str().unwrap_or(""));
    println!("  {}: {purposes} ({})", ["purposes", "目的"][i], a["purposes"]["source"].as_str().unwrap_or(""));
    println!(
        "  {} {}/100   high {}  medium {}  low {}",
        ["overall", "総合"][i], a["scores"]["overall"], counts["high"], counts["medium"], counts["low"]
    );
    if let Some(cats) = a["scores"]["categories"].as_object() {
        for (k, v) in cats {
            let label = if o.ja { v["label_ja"].as_str().unwrap_or(k).to_string() } else { k.clone() };
            println!("    {:<16} {:>3}/100  ({} {})", label, v["score"], v["findings"], ["findings", "件"][i]);
        }
    }
    if let Some(d) = &since {
        println!(
            "\n  {}: {} -> {}   {} {}, {} {}",
            ["since the previous assessment", "前回の評価から"][i],
            d["overall"]["from"], d["overall"]["to"],
            d["fixed"].as_array().map(|x| x.len()).unwrap_or(0), ["fixed", "件解消"][i],
            d["new"].as_array().map(|x| x.len()).unwrap_or(0), ["new", "件新規"][i],
        );
        for f in d["new"].as_array().into_iter().flatten() {
            println!("    + [{}] {}", f["rubric"].as_str().unwrap_or(""), pick(f, "title"));
        }
        for f in d["fixed"].as_array().into_iter().flatten() {
            println!("    - [{}] {}", f["rubric"].as_str().unwrap_or(""), pick(f, "title"));
        }
    }
    if let Some(w) = a["worklist"].as_array() {
        if !w.is_empty() {
            println!("\n  {}", ["fix these first:", "まずこれを直す:"][i]);
        }
        for (n, x) in w.iter().take(3).enumerate() {
            println!(
                "    {}. [{}] {} x{}  ({} {}, {} {})",
                n + 1, x["rubric"].as_str().unwrap_or(""), pick(x, "full"), x["count"],
                ["effort", "手間"][i], x["effort"], ["overall after", "解消後の総合"][i], x["overall_after"],
            );
        }
    }
    if let Some(list) = a["findings"].as_array() {
        if !list.is_empty() {
            println!("\n  {}", ["findings, worst first:", "指摘（重い順）:"][i]);
        }
        for x in list.iter().take(40) {
            println!(
                "    [{} {}] {}",
                x["severity"].as_str().unwrap_or("?"), x["rubric"].as_str().unwrap_or(""), pick(x, "title")
            );
            if let Some(e) = x["evidence"].as_str() {
                println!("        {}: {e}", ["at", "根拠"][i]);
            }
            println!("        {}: {}", ["fix", "修正"][i], pick(x, "fix"));
        }
        if list.len() > 40 {
            println!("    ... {} {}", list.len() - 40, ["more", "件省略"][i]);
        }
    }
    // exit 1 when anything high is outstanding, so CI can gate on it
    Ok(if counts["high"].as_u64().unwrap_or(0) > 0 { 1 } else { 0 })
}
