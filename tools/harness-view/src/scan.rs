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

const REVIEWERS: &[&str] = &["code-reviewer", "reviewer", "security-reviewer", "spec-guardian"];


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

pub fn scan(root: &Path) -> Value {
    let claude = root.join(".claude");
    let mut nodes: BTreeMap<String, Value> = BTreeMap::new();
    let mut edges: Vec<(String, String, String, i64)> = Vec::new();

    // --- agents (never toggleable, so no disabled variant) ---
    let mut agent_names: Vec<String> = Vec::new();
    for name in md_stems(&claude.join("agents")) {
        let path = claude.join("agents").join(format!("{name}.md"));
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
        nodes.insert(
            format!("agent:{name}"),
            json!({
                "id": format!("agent:{name}"),
                "type": "agent",
                "label": name,
                "file": rel(root, &format!(".claude/agents/{name}.md")),
                "disabled": false,
                "meta": Value::Object(meta),
            }),
        );
        agent_names.push(name);
    }

    // --- rules, commands: active tree plus the disabled/ quarantine tree ---
    for (kind, sub, prefix) in [("rule", "rules", "rule"), ("command", "commands", "cmd")] {
        for (dir_tail, disabled) in [
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
                let mut node = Map::new();
                node.insert("id".into(), json!(id));
                node.insert("type".into(), json!(kind));
                node.insert("label".into(), json!(label));
                node.insert("file".into(), json!(rel(root, &file)));
                node.insert("disabled".into(), json!(disabled));
                if kind == "rule" {
                    let text = fs::read_to_string(root.join(&file)).unwrap_or_default();
                    let fm = frontmatter(&text);
                    let mut meta = Map::new();
                    match fm.get("paths") {
                        Some(v) => {
                            let paths = as_list(v);
                            meta.insert("scoped".into(), json!(!paths.is_empty()));
                            if !paths.is_empty() {
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
                    node.insert("meta".into(), Value::Object(meta));
                }
                nodes.insert(id, Value::Object(node));
            }
        }
    }

    // --- hooks: one node per name, across both flavors and the quarantine ---
    let mut hook_files: BTreeMap<String, (String, bool)> = BTreeMap::new();
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
                let (stem, is_hook) = match fname.rsplit_once('.') {
                    Some((s, "sh")) => (s.to_string(), true),
                    Some((s, "ps1")) => (s.to_string(), true),
                    _ => (String::new(), false),
                };
                if !is_hook {
                    continue;
                }
                let file = format!("{dir_tail}/{fname}");
                // prefer the .sh flavor as the representative file
                let e = hook_files.entry(stem).or_insert((file.clone(), disabled));
                if e.0.ends_with(".ps1") && file.ends_with(".sh") {
                    e.0 = file;
                }
                if disabled {
                    e.1 = true;
                }
            }
        }
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

    // --- tasks (capped, like the Python twin) ---
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
        nodes.insert(
            format!("task:{stem}"),
            json!({"id": format!("task:{stem}"), "type": "task", "label": stem,
                   "disabled": false, "file": relpath}),
        );
        if !module_names.is_empty() {
            if let Ok(body) = fs::read_to_string(root.join(relpath)) {
                for m in &module_names {
                    if body.contains(m.as_str()) {
                        edges.push((format!("task:{stem}"), format!("mod:{m}"), "references".into(), 0));
                    }
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
    let unconditional_rules: Vec<String> = nodes
        .values()
        .filter(|n| {
            n.get("type").and_then(|t| t.as_str()) == Some("rule")
                && n.get("meta")
                    .and_then(|m| m.get("scoped"))
                    .and_then(|s| s.as_bool())
                    == Some(false)
        })
        .filter_map(|n| n.get("id").and_then(|i| i.as_str()).map(|s| s.to_string()))
        .collect();
    for rule_id in &unconditional_rules {
        for agent in &agent_names {
            edges.push((rule_id.clone(), format!("agent:{agent}"), "gates".into(), 0));
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
        if nodes.contains_key(&format!("agent:{r}")) {
            edges.push((format!("agent:{r}"), "gate:merge-request".into(), "reviews".into(), 0));
        }
    }
    edges.push(("gate:merge-request".into(), "human".into(), "escalates".into(), 0));
    let command_ids: Vec<String> = nodes
        .values()
        .filter(|n| n.get("type").and_then(|t| t.as_str()) == Some("command"))
        .filter_map(|n| n.get("id").and_then(|i| i.as_str()).map(|s| s.to_string()))
        .collect();
    for cmd_id in &command_ids {
        edges.push(("human".into(), cmd_id.clone(), "invokes".into(), 0));
        if let Some(file) = nodes
            .get(cmd_id)
            .and_then(|n| n.get("file"))
            .and_then(|f| f.as_str())
        {
            if let Ok(body) = fs::read_to_string(root.join(file)) {
                // every ".claude/scripts/<name>.py" reference counts, whether or
                // not the script file exists yet - the edge records the wiring
                let norm = body.replace('\\', "/");
                let mut start = 0;
                while let Some(i) = norm[start..].find("scripts/") {
                    let at = start + i + "scripts/".len();
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

/// Canonical serialization: sorted keys (serde_json's default map is ordered),
/// two-space indent, trailing newline, no timestamps.
pub fn to_canonical_json(v: &Value) -> String {
    let mut s = serde_json::to_string_pretty(v).unwrap_or_else(|_| "{}".into());
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
