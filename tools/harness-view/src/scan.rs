//! Deterministic scanner: reads a harnessed repo's .claude/ tree (plus docs/tasks
//! and .claude/state/code-graph.json when present) and emits the harness graph,
//! schema version 1. No timestamps, sorted keys, sorted nodes and edges, so two
//! scans of the same tree are byte-identical.

use serde_json::{json, Map, Value};
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

/// hook name -> rule it enforces. This relationship exists only in prose inside
/// the harness assets, so the graph carries it as a static table.
const ENFORCES: &[(&str, &str)] = &[
    ("agent-history", "task-tracking"),
    ("check-commit-msg", "conventional-commits"),
    ("guard-agent-scope", "agent-guardrails"),
    ("guard-agent-spawn", "agent-guardrails"),
    ("guard-main-commit", "conventional-commits"),
    ("protect-adr", "docs-workflow"),
    ("protect-repos", "security-privacy"),
    ("protect-secrets", "security-privacy"),
    ("specs-reminder", "docs-workflow"),
];

const REVIEWERS: &[&str] = &[
    "code-reviewer",
    "merge-manager",
    "reviewer",
    "security-reviewer",
    "spec-guardian",
];


/// Minimal line-based YAML-subset frontmatter parser: `key: value` pairs and
/// block lists. Good enough for the harness's own agent/rule files; anything
/// it cannot read is simply absent from the node meta.
fn frontmatter(text: &str) -> BTreeMap<String, Value> {
    let mut out = BTreeMap::new();
    let mut lines = text.lines();
    match lines.next() {
        Some(l) if l.trim() == "---" => {}
        _ => return out,
    }
    let mut cur_key: Option<String> = None;
    let mut cur_list: Vec<String> = Vec::new();
    for line in lines {
        if line.trim() == "---" {
            break;
        }
        let trimmed = line.trim_start();
        if let Some(item) = trimmed.strip_prefix("- ") {
            if cur_key.is_some() {
                cur_list.push(item.trim().to_string());
                continue;
            }
        }
        if let Some(k) = cur_key.take() {
            if !cur_list.is_empty() {
                out.insert(
                    k,
                    Value::Array(cur_list.drain(..).map(Value::String).collect()),
                );
            }
        }
        if line.starts_with(' ') || line.starts_with('\t') {
            continue;
        }
        if let Some(idx) = line.find(':') {
            let key = line[..idx].trim().to_string();
            let val = line[idx + 1..].trim().to_string();
            if key.is_empty() {
                continue;
            }
            if val.is_empty() {
                cur_key = Some(key);
            } else {
                out.insert(key, Value::String(val));
            }
        }
    }
    if let Some(k) = cur_key.take() {
        if !cur_list.is_empty() {
            out.insert(k, Value::Array(cur_list.into_iter().map(Value::String).collect()));
        }
    }
    out
}

/// Frontmatter `description:`, trimmed and capped. The sidebar shows it, so a
/// runaway value must not push the rest of the panel off screen; the full text
/// is one Preview click away.
fn description(fm: &BTreeMap<String, Value>) -> Option<String> {
    let raw = match fm.get("description") {
        Some(Value::String(s)) => unquote(s),
        _ => return None,
    };
    let d = raw.trim().to_string();
    if d.is_empty() {
        return None;
    }
    Some(if d.chars().count() > 300 {
        d.chars().take(300).collect::<String>() + "..."
    } else {
        d
    })
}

/// Drop a trailing YAML comment from a scalar: `Done # Active | Blocked` -> `Done`.
/// A `#` only opens a comment when whitespace precedes it, so `P0#1` survives.
/// Real task files keep the template's enum comment on the line, and without
/// this the status reads as "Done # Active | Blocked | Pending | Done".
fn strip_comment(s: &str) -> String {
    if s.starts_with('"') || s.starts_with('\'') {
        return s.to_string();
    }
    let b = s.as_bytes();
    for i in 0..b.len() {
        if b[i] == b'#' && (i == 0 || b[i - 1].is_ascii_whitespace()) {
            return s[..i].trim_end().to_string();
        }
    }
    s.to_string()
}

/// Strip one layer of surrounding single or double quotes.
fn unquote(s: &str) -> String {
    let t = s.trim();
    if t.len() >= 2
        && ((t.starts_with('"') && t.ends_with('"')) || (t.starts_with('\'') && t.ends_with('\'')))
    {
        t[1..t.len() - 1].to_string()
    } else {
        t.to_string()
    }
}

/// "Read, Write, Bash(git commit:*)" or a YAML list -> list of strings.
fn as_list(v: &Value) -> Vec<String> {
    match v {
        Value::Array(a) => a
            .iter()
            .filter_map(|x| x.as_str())
            .map(unquote)
            .collect(),
        Value::String(s) => {
            let inner = s.trim().trim_start_matches('[').trim_end_matches(']');
            inner
                .split(',')
                .map(unquote)
                .filter(|p| !p.is_empty())
                .collect()
        }
        _ => Vec::new(),
    }
}

/// True when a line declares skills for a seat, e.g. "Skills to load when
/// relevant: webapp-testing." /skill-wire records a wire as an entry under the
/// seat's "Skills available" section, so a declaration line is the only
/// trustworthy signal. Matching a bare skill name anywhere in an agent file
/// invents wiring: five of ost's agents contain the word "performance" while the
/// skill of that name is wired to no seat.
pub fn skill_decl_value(line: &str) -> Option<&str> {
    let lower = line.to_lowercase();
    let kw = lower.find("skill")?;
    let colon = line.find(':')?;
    if colon < kw {
        return None;
    }
    let between = &lower[kw..colon];
    let marks = ["available", "to load", "in use", "when relevant"];
    if !marks.iter().any(|m| between.contains(m)) {
        return None;
    }
    Some(&line[colon + 1..])
}

/// Slug-shaped tokens, trailing punctuation dropped: " webapp-testing." yields
/// "webapp-testing", not "webapp-testing.".
pub fn slug_tokens(text: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut cur = String::new();
    for c in text.chars() {
        if c.is_ascii_alphanumeric() || c == '_' || c == '-' || c == '.' {
            cur.push(c);
        } else if !cur.is_empty() {
            out.push(std::mem::take(&mut cur));
        }
    }
    if !cur.is_empty() {
        out.push(cur);
    }
    out.into_iter()
        .map(|t| t.trim_matches(|c: char| !c.is_ascii_alphanumeric()).to_string())
        .filter(|t| !t.is_empty())
        .collect()
}

fn md_stems(dir: &Path) -> Vec<String> {
    let mut out = Vec::new();
    if let Ok(rd) = fs::read_dir(dir) {
        for e in rd.flatten() {
            let p = e.path();
            if p.extension().and_then(|x| x.to_str()) == Some("md") {
                if let Some(stem) = p.file_stem().and_then(|x| x.to_str()) {
                    if stem != "README" {
                        out.push(stem.to_string());
                    }
                }
            }
        }
    }
    out.sort();
    out
}

fn rel(root: &Path, tail: &str) -> String {
    let _ = root;
    tail.replace('\\', "/")
}

/// Pull the hook script name out of a registration command string.
fn hook_name_from_command(cmd: &str) -> Option<String> {
    let norm = cmd.replace('\\', "/");
    let idx = norm.rfind("hooks/")?;
    let tail = &norm[idx + "hooks/".len()..];
    let name: String = tail
        .chars()
        .take_while(|c| c.is_ascii_alphanumeric() || *c == '-' || *c == '_')
        .collect();
    if name.is_empty() {
        None
    } else {
        Some(name)
    }
}

/// "<kind>/<name>" keys listed in .claude/disabled.json - OR-ed into the
/// disabled flag for rules and hooks, like harness-graph.py.
fn disabled_entries(claude: &Path) -> std::collections::BTreeSet<String> {
    let mut out = std::collections::BTreeSet::new();
    if let Ok(txt) = fs::read_to_string(claude.join("disabled.json")) {
        if let Ok(v) = serde_json::from_str::<Value>(&txt) {
            for e in v.get("disabled").and_then(|d| d.as_array()).cloned().unwrap_or_default() {
                if let (Some(k), Some(n)) = (
                    e.get("kind").and_then(|x| x.as_str()),
                    e.get("name").and_then(|x| x.as_str()),
                ) {
                    out.insert(format!("{k}/{n}"));
                }
            }
        }
    }
    out
}

pub fn scan(root: &Path) -> Value {
    let claude = root.join(".claude");
    let mut nodes: BTreeMap<String, Value> = BTreeMap::new();
    let mut edges: Vec<(String, String, String, i64)> = Vec::new();
    let listed = disabled_entries(&claude);

    // --- agents: both trees, because a seat can be parked under
    // disabled/agents and still belongs in the graph, greyed out
    // (harness-graph.py scans both trees; parity depends on it) ---
    let mut agent_names: Vec<String> = Vec::new();
    for (dir_tail, dis) in [(".claude/agents", false), (".claude/disabled/agents", true)] {
        for name in md_stems(&root.join(dir_tail)) {
        let path = root.join(dir_tail).join(format!("{name}.md"));
        let text = fs::read_to_string(&path).unwrap_or_default();
        let fm = frontmatter(&text);
        let mut meta = Map::new();
        for key in ["model", "effort"] {
            if let Some(Value::String(v)) = fm.get(key) {
                meta.insert(key.to_string(), Value::String(v.clone()));
            }
        }
        for key in ["maxTurns", "max-turns"] {
            if let Some(Value::String(v)) = fm.get(key) {
                if let Ok(n) = v.parse::<i64>() {
                    meta.insert("maxTurns".to_string(), json!(n));
                }
            }
        }
        for key in ["tools", "allowed-tools"] {
            if let Some(v) = fm.get(key) {
                let list = as_list(v);
                if !list.is_empty() {
                    meta.insert(
                        "tools".to_string(),
                        Value::Array(list.into_iter().map(Value::String).collect()),
                    );
                    break;
                }
            }
        }
        if let Some(d) = description(&fm) {
            meta.insert("description".to_string(), Value::String(d));
        }
        nodes.insert(
            format!("agent:{name}"),
            json!({
                "id": format!("agent:{name}"),
                "type": "agent",
                "label": name,
                "file": rel(root, &format!("{dir_tail}/{name}.md")),
                "disabled": dis,
                "meta": Value::Object(meta),
            }),
        );
        if !dis {
            agent_names.push(name);
        }
        }
    }

    // --- rules, commands: active tree plus the disabled/ quarantine tree ---
    // gating_rules: unconditional rules in the ACTIVE tree - only these emit
    // gates edges (harness-graph.py: `if not dis and not scoped`). Same for
    // active_commands and their invokes edges.
    let mut gating_rules: Vec<String> = Vec::new();
    let mut active_commands: Vec<String> = Vec::new();
    for (kind, sub, prefix) in [("rule", "rules", "rule"), ("command", "commands", "cmd")] {
        for (dir_tail, dir_disabled) in [
            (format!(".claude/{sub}"), false),
            (format!(".claude/disabled/{sub}"), true),
        ] {
            for name in md_stems(&root.join(&dir_tail)) {
                let file = format!("{dir_tail}/{name}.md");
                let id = format!("{prefix}:{name}");
                let label = if kind == "command" {
                    format!("/{name}")
                } else {
                    name.clone()
                };
                // disabled.json ORs into the flag for rules (and hooks below);
                // commands follow the directory only, like harness-graph.py
                let disabled = dir_disabled
                    || (kind == "rule" && listed.contains(&format!("rule/{name}")));
                let mut node = Map::new();
                node.insert("id".into(), json!(id));
                node.insert("type".into(), json!(kind));
                node.insert("label".into(), json!(label));
                node.insert("file".into(), json!(rel(root, &file)));
                node.insert("disabled".into(), json!(disabled));
                let text = fs::read_to_string(root.join(&file)).unwrap_or_default();
                let fm_any = frontmatter(&text);
                if kind == "rule" {
                    let fm = fm_any;
                    let mut meta = Map::new();
                    let mut scoped = false;
                    match fm.get("paths") {
                        Some(v) => {
                            let mut paths = as_list(v);
                            paths.truncate(8);
                            scoped = !paths.is_empty();
                            meta.insert("scoped".into(), json!(scoped));
                            if scoped {
                                meta.insert(
                                    "paths".into(),
                                    Value::Array(paths.into_iter().map(Value::String).collect()),
                                );
                            }
                        }
                        None => {
                            meta.insert("scoped".into(), json!(false));
                        }
                    }
                    if let Some(d) = description(&fm) {
                        meta.insert("description".into(), Value::String(d));
                    }
                    node.insert("meta".into(), Value::Object(meta));
                    if !dir_disabled && !scoped {
                        gating_rules.push(id.clone());
                    }
                } else {
                    if let Some(d) = description(&fm_any) {
                        let mut meta = Map::new();
                        meta.insert("description".into(), Value::String(d));
                        node.insert("meta".into(), Value::Object(meta));
                    }
                    if !dir_disabled {
                        active_commands.push(id.clone());
                    }
                }
                nodes.insert(id, Value::Object(node));
            }
        }
    }

    // --- hooks: one node per name, across both flavors and the quarantine.
    // A hook counts as disabled only when ALL its flavor files are quarantined;
    // the representative file is the .sh if present, an active flavor beating a
    // disabled one at equal extension (harness-graph.py's tie-break). ---
    let mut hook_variants: BTreeMap<String, Vec<(String, bool)>> = BTreeMap::new();
    for (dir_tail, disabled) in [
        (".claude/hooks".to_string(), false),
        (".claude/disabled/hooks".to_string(), true),
    ] {
        if let Ok(rd) = fs::read_dir(root.join(&dir_tail)) {
            let mut entries: Vec<_> = rd
                .flatten()
                .filter_map(|e| e.file_name().to_str().map(|s| s.to_string()))
                .collect();
            entries.sort();
            for fname in entries {
                let stem = match fname.rsplit_once('.') {
                    Some((s, "sh")) | Some((s, "ps1")) => s.to_string(),
                    _ => continue,
                };
                let file = format!("{dir_tail}/{fname}");
                hook_variants.entry(stem).or_default().push((file, disabled));
            }
        }
    }
    let mut hook_files: BTreeMap<String, (String, bool)> = BTreeMap::new();
    for (stem, mut files) in hook_variants {
        let all_disabled = files.iter().all(|(_, d)| *d);
        files.sort_by_key(|(f, d)| (!f.ends_with(".sh"), *d, f.clone()));
        let dis = all_disabled || listed.contains(&format!("hook/{stem}"));
        hook_files.insert(stem, (files[0].0.clone(), dis));
    }

    // --- settings.json: which hooks are registered, and under what ---
    let mut registrations: BTreeMap<String, (String, String)> = BTreeMap::new();
    let settings_path = claude.join("settings.json");
    let have_settings = settings_path.is_file();
    if have_settings {
        if let Ok(txt) = fs::read_to_string(&settings_path) {
            if let Ok(v) = serde_json::from_str::<Value>(&txt) {
                if let Some(events) = v.get("hooks").and_then(|h| h.as_object()) {
                    for (event, arr) in events {
                        let groups: &[Value] =
                            arr.as_array().map(|a| a.as_slice()).unwrap_or(&[]);
                        for group in groups {
                            let matcher = group
                                .get("matcher")
                                .and_then(|m| m.as_str())
                                .unwrap_or("*");
                            let hooks: &[Value] = group
                                .get("hooks")
                                .and_then(|x| x.as_array())
                                .map(|a| a.as_slice())
                                .unwrap_or(&[]);
                            for h in hooks {
                                if let Some(cmd) = h.get("command").and_then(|c| c.as_str()) {
                                    if let Some(name) = hook_name_from_command(cmd) {
                                        registrations
                                            .entry(name)
                                            .or_insert((event.clone(), matcher.to_string()));
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        nodes.insert(
            "settings".into(),
            json!({"id": "settings", "type": "settings", "label": "settings.json",
                   "file": rel(root, ".claude/settings.json"), "disabled": false}),
        );
    }

    for (name, (file, disabled)) in &hook_files {
        let id = format!("hook:{name}");
        let mut meta = Map::new();
        let registered = registrations.contains_key(name);
        meta.insert("registered".into(), json!(registered));
        if let Some((event, matcher)) = registrations.get(name) {
            meta.insert("event".into(), json!(event));
            meta.insert("matcher".into(), json!(matcher));
            meta.insert("blocking".into(), json!(event == "PreToolUse"));
        }
        nodes.insert(
            id.clone(),
            json!({"id": id, "type": "hook", "label": name,
                   "file": rel(root, file), "disabled": disabled, "meta": Value::Object(meta)}),
        );
        if registered && have_settings {
            edges.push(("settings".into(), format!("hook:{name}"), "triggers".into(), 0));
        }
    }

    // --- scripts ---
    let mut _script_count = 0usize;
    if let Ok(rd) = fs::read_dir(claude.join("scripts")) {
        let mut names: Vec<String> = rd
            .flatten()
            .filter_map(|e| {
                let p = e.path();
                if p.extension().and_then(|x| x.to_str()) == Some("py") {
                    p.file_stem().and_then(|x| x.to_str()).map(|s| s.to_string())
                } else {
                    None
                }
            })
            .collect();
        names.sort();
        for name in names {
            nodes.insert(
                format!("script:{name}"),
                json!({"id": format!("script:{name}"), "type": "script",
                       "label": format!("{name}.py"), "disabled": false,
                       "file": rel(root, &format!(".claude/scripts/{name}.py"))}),
            );
            _script_count += 1;
        }
    }

    // --- synthetic flow anchors ---
    nodes.insert(
        "gate:merge-request".into(),
        json!({"id": "gate:merge-request", "type": "gate", "label": "Merge request",
               "disabled": false, "synthetic": true}),
    );
    nodes.insert(
        "human".into(),
        json!({"id": "human", "type": "human", "label": "Human",
               "disabled": false, "synthetic": true}),
    );

    // --- modules from code-graph.json (best effort, absence is fine) ---
    let mut module_names: Vec<String> = Vec::new();
    if let Ok(txt) = fs::read_to_string(claude.join("state").join("code-graph.json")) {
        if let Ok(v) = serde_json::from_str::<Value>(&txt) {
            if let Some(mods) = v.get("modules").and_then(|m| m.as_object()) {
                for (name, info) in mods {
                    let mut meta = Map::new();
                    // code-graph.json stores files as a path array; a bare count
                    // is tolerated for forward compatibility
                    let files = info
                        .get("files")
                        .map(|x| x.as_array().map(|a| a.len() as i64).or_else(|| x.as_i64()).unwrap_or(0))
                        .unwrap_or(0);
                    meta.insert("files".into(), json!(files));
                    let owner = info.get("owner").and_then(|x| x.as_str()).unwrap_or("-");
                    meta.insert("owner".into(), json!(owner));
                    if owner != "-" && nodes.contains_key(&format!("agent:{owner}")) {
                        edges.push((
                            format!("agent:{owner}"),
                            format!("mod:{name}"),
                            "owns".into(),
                            0,
                        ));
                    }
                    nodes.insert(
                        format!("mod:{name}"),
                        json!({"id": format!("mod:{name}"), "type": "module",
                               "label": name, "disabled": false,
                               "meta": Value::Object(meta)}),
                    );
                    module_names.push(name.clone());
                }
            }
            if let Some(arr) = v.get("edges").and_then(|e| e.as_array()) {
                for e in arr {
                    let (from, to) = if let Some(pair) = e.as_array() {
                        (
                            pair.first().and_then(|x| x.as_str()),
                            pair.get(1).and_then(|x| x.as_str()),
                        )
                    } else {
                        (
                            e.get("from").and_then(|x| x.as_str()),
                            e.get("to").and_then(|x| x.as_str()),
                        )
                    };
                    if let (Some(f), Some(t)) = (from, to) {
                        if nodes.contains_key(&format!("mod:{f}"))
                            && nodes.contains_key(&format!("mod:{t}"))
                        {
                            let refs = e.get("refs").and_then(|x| x.as_i64()).unwrap_or(1);
                            edges.push((
                                format!("mod:{f}"),
                                format!("mod:{t}"),
                                "references".into(),
                                refs,
                            ));
                        }
                    }
                }
            }
        }
    }

    // --- tasks: every TASK-*.md under docs/tasks/** is a node by contract ---
    let mut task_files: Vec<(String, String)> = Vec::new();
    fn walk_tasks(dir: &Path, out: &mut Vec<(String, String)>, root: &Path) {
        if let Ok(rd) = fs::read_dir(dir) {
            let mut entries: Vec<_> = rd.flatten().map(|e| e.path()).collect();
            entries.sort();
            for p in entries {
                if p.is_dir() {
                    walk_tasks(&p, out, root);
                } else if let Some(name) = p.file_name().and_then(|x| x.to_str()) {
                    if name.starts_with("TASK-") && name.ends_with(".md") {
                        let stem = name.trim_end_matches(".md").to_string();
                        let relpath = p
                            .strip_prefix(root)
                            .map(|q| q.to_string_lossy().replace('\\', "/"))
                            .unwrap_or_default();
                        out.push((stem, relpath));
                    }
                }
            }
        }
    }
    walk_tasks(&root.join("docs").join("tasks"), &mut task_files, root);
    task_files.sort();
    for (stem, relpath) in &task_files {
        let body = fs::read_to_string(root.join(relpath)).unwrap_or_default();
        let fm = frontmatter(&body);
        // The board fields, in the order the templates declare them. Everything
        // here is what makes a task row readable without opening the file.
        let mut meta = Map::new();
        for key in ["title", "status", "fr", "owner", "deps", "priority", "phase"] {
            if let Some(Value::String(v)) = fm.get(key) {
                let v = unquote(&strip_comment(v));
                if !v.is_empty() {
                    meta.insert(key.to_string(), Value::String(v));
                }
            }
        }
        let mut node = Map::new();
        node.insert("id".into(), json!(format!("task:{stem}")));
        node.insert("type".into(), json!("task"));
        node.insert("label".into(), json!(stem));
        node.insert("disabled".into(), json!(false));
        node.insert("file".into(), json!(relpath));
        if !meta.is_empty() {
            node.insert("meta".into(), Value::Object(meta));
        }
        nodes.insert(format!("task:{stem}"), Value::Object(node));
        // agent -owns-> task, the same edge type an agent uses for a module.
        // Emitted only when the named seat exists: a task owned by a retired
        // agent would otherwise anchor to nothing. (Contrast `runs`, which is
        // deliberately allowed to dangle because a command naming a missing
        // script is itself the finding.)
        if let Some(Value::String(owner)) = fm.get("owner") {
            let owner = unquote(&strip_comment(owner));
            // Real boards co-own a task as "frontend-ui-dev+platform-dev", so
            // each named seat gets its own edge. Dropping the pair entirely
            // would leave a task that HAS owners looking unowned.
            for one in owner.split('+').map(|s| s.trim()).filter(|s| !s.is_empty()) {
                if agent_names.iter().any(|a| a == one) {
                    edges.push((
                        format!("agent:{one}"),
                        format!("task:{stem}"),
                        "owns".into(),
                        0,
                    ));
                }
            }
        }
        if !module_names.is_empty() {
            for m in &module_names {
                if body.contains(m.as_str()) {
                    edges.push((format!("task:{stem}"), format!("mod:{m}"), "references".into(), 0));
                }
            }
        }
    }

    // --- relationship edges over the collected nodes ---
    for (hook, rule) in ENFORCES {
        if nodes.contains_key(&format!("hook:{hook}")) && nodes.contains_key(&format!("rule:{rule}"))
        {
            edges.push((format!("hook:{hook}"), format!("rule:{rule}"), "enforces".into(), 0));
        }
    }
    for rule_id in &gating_rules {
        for agent in &agent_names {
            edges.push((rule_id.clone(), format!("agent:{agent}"), "gates".into(), 0));
        }
    }
    // --- skills: .claude/skills/<slug>/SKILL.md. A skill may ship its own
    // agents and scripts, but those are internal to the skill and are not roster
    // seats, so they are meta rather than harness nodes.
    let mut skill_names: std::collections::BTreeSet<String> = std::collections::BTreeSet::new();
    let skills_dir = claude.join("skills");
    if let Ok(rd) = fs::read_dir(&skills_dir) {
        let mut dirs: Vec<_> = rd.flatten().map(|e| e.path()).collect();
        dirs.sort();
        for sd in dirs {
            let sm = sd.join("SKILL.md");
            if !sd.is_dir() || !sm.is_file() {
                continue;
            }
            let name = match sd.file_name().and_then(|x| x.to_str()) {
                Some(n) => n.to_string(),
                None => continue,
            };
            let text = fs::read_to_string(&sm).unwrap_or_default();
            let mut meta = Map::new();
            if let Some(d) = description(&frontmatter(&text)) {
                meta.insert("description".into(), Value::String(d));
            }
            for extra in ["agents", "scripts"] {
                let n = fs::read_dir(sd.join(extra)).map(|r| r.flatten().count()).unwrap_or(0);
                if n > 0 {
                    meta.insert(format!("own_{extra}"), json!(n as i64));
                }
            }
            nodes.insert(
                format!("skill:{name}"),
                json!({
                    "id": format!("skill:{name}"),
                    "type": "skill",
                    "label": name,
                    "file": rel(root, &format!(".claude/skills/{name}/SKILL.md")),
                    "disabled": false,
                    "meta": Value::Object(meta),
                }),
            );
            skill_names.insert(name);
        }
    }
    // Only installed skills get an edge; a wire to a node that does not exist
    // would dangle in every viewer. The assessment reports a seat that declares
    // an uninstalled skill, reading the seat files directly.
    for (dir_tail, _dis) in [(".claude/agents", false), (".claude/disabled/agents", true)] {
        for name in md_stems(&root.join(dir_tail)) {
            let text =
                fs::read_to_string(root.join(dir_tail).join(format!("{name}.md"))).unwrap_or_default();
            for line in text.lines() {
                if let Some(val) = skill_decl_value(line) {
                    for tok in slug_tokens(val) {
                        if skill_names.contains(&tok) {
                            edges.push((
                                format!("agent:{name}"),
                                format!("skill:{tok}"),
                                "uses".into(),
                                0,
                            ));
                        }
                    }
                }
            }
        }
    }

    if agent_names.iter().any(|a| a == "orchestrator") {
        for agent in &agent_names {
            if agent != "orchestrator" {
                edges.push(("agent:orchestrator".into(), format!("agent:{agent}"), "spawns".into(), 0));
            }
        }
    }
    for r in REVIEWERS {
        // active seats only - a parked agent file reviews nothing
        if agent_names.iter().any(|a| a == r) {
            edges.push((format!("agent:{r}"), "gate:merge-request".into(), "reviews".into(), 0));
        }
    }
    edges.push(("gate:merge-request".into(), "human".into(), "escalates".into(), 0));
    // invokes edges only for active commands; runs edges for every command
    // node including quarantined ones (harness-graph.py emits runs for both)
    for cmd_id in &active_commands {
        edges.push(("human".into(), cmd_id.clone(), "invokes".into(), 0));
    }
    let command_ids: Vec<String> = nodes
        .values()
        .filter(|n| n.get("type").and_then(|t| t.as_str()) == Some("command"))
        .filter_map(|n| n.get("id").and_then(|i| i.as_str()).map(|s| s.to_string()))
        .collect();
    for cmd_id in &command_ids {
        if let Some(file) = nodes
            .get(cmd_id)
            .and_then(|n| n.get("file"))
            .and_then(|f| f.as_str())
        {
            if let Ok(body) = fs::read_to_string(root.join(file)) {
                // every ".claude/scripts/<name>.py" reference counts, whether or
                // not the script file exists yet - the edge records the wiring.
                // The ".claude/" prefix is required: commands also cite the SKILL's
                // own "<skill>/scripts/scaffold.py", which is not an installed script
                // and must not become a node or an edge.
                let norm = body.replace('\\', "/");
                let needle = ".claude/scripts/";
                let mut start = 0;
                while let Some(i) = norm[start..].find(needle) {
                    let at = start + i + needle.len();
                    let name: String = norm[at..]
                        .chars()
                        .take_while(|c| c.is_ascii_alphanumeric() || *c == '-' || *c == '_')
                        .collect();
                    start = at + name.len().max(1);
                    if !name.is_empty() && norm[start.min(norm.len())..].starts_with(".py") {
                        edges.push((cmd_id.clone(), format!("script:{name}"), "runs".into(), 0));
                    }
                }
            }
        }
    }

    edges.sort();
    edges.dedup();

    let node_list: Vec<Value> = nodes.into_values().collect();
    let edge_list: Vec<Value> = edges
        .into_iter()
        .map(|(f, t, ty, refs)| {
            let mut e = json!({"from": f, "to": t, "type": ty});
            if refs > 0 {
                e["refs"] = json!(refs);
            }
            e
        })
        .collect();
    json!({"version": 1, "nodes": node_list, "edges": edge_list})
}

/// Recursively rebuild a Value with object keys in sorted order. serde_json is
/// compiled with preserve_order (settings.json needs its key order kept), so
/// canonical outputs must sort explicitly.
pub fn sort_keys_deep(v: &Value) -> Value {
    match v {
        Value::Object(m) => {
            let mut keys: Vec<&String> = m.keys().collect();
            keys.sort();
            let mut out = Map::new();
            for k in keys {
                out.insert(k.clone(), sort_keys_deep(&m[k]));
            }
            Value::Object(out)
        }
        Value::Array(a) => Value::Array(a.iter().map(sort_keys_deep).collect()),
        _ => v.clone(),
    }
}

/// Canonical serialization: sorted keys at every depth, two-space indent,
/// trailing newline, no timestamps.
pub fn to_canonical_json(v: &Value) -> String {
    let mut s = serde_json::to_string_pretty(&sort_keys_deep(v)).unwrap_or_else(|_| "{}".into());
    s.push('\n');
    s
}

pub fn scan_to_file(root: &Path, out: Option<&Path>) -> std::io::Result<(usize, usize, String)> {
    let graph = scan(root);
    let n = graph["nodes"].as_array().map(|a| a.len()).unwrap_or(0);
    let m = graph["edges"].as_array().map(|a| a.len()).unwrap_or(0);
    let default_out = root.join(".claude").join("state").join("harness-graph.json");
    let out_path = out.map(|p| p.to_path_buf()).unwrap_or(default_out);
    if let Some(parent) = out_path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(&out_path, to_canonical_json(&graph))?;
    Ok((n, m, out_path.to_string_lossy().to_string()))
}
