//! Deterministic scanner: reads a harnessed repo's .claude/ tree (plus docs/tasks
//! and .claude/state/code-graph.json when present) and emits the harness graph,
//! schema version 1. No timestamps, sorted keys, sorted nodes and edges, so two
//! scans of the same tree are byte-identical.
//!
//! It also reads the instruction files that sit OUTSIDE .claude/ - `AGENTS.md`,
//! `CLAUDE.md` and the per-tool equivalents listed in `instruction::FILES` -
//! because those are the contract the seats are told to obey, and a graph that
//! stopped at the .claude/ boundary showed every enforcement mechanism and none
//! of the thing being enforced.

use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

use crate::refs;

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
    // A file saved by a Windows editor can start with a UTF-8 BOM, and then the
    // first line is "\u{feff}---": every key in it used to vanish.
    let text = text.strip_prefix('\u{feff}').unwrap_or(text);
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
            split_top(inner)
                .into_iter()
                .map(|p| unquote(&p))
                .filter(|p| !p.is_empty())
                .collect()
        }
        _ => Vec::new(),
    }
}

/// Split on commas that sit outside parentheses, brackets and quotes, so
/// `Agent(researcher, writer), Read` is two tools and not three fragments.
fn split_top(s: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut cur = String::new();
    let mut depth = 0i32;
    let mut quote: Option<char> = None;
    for c in s.chars() {
        if let Some(q) = quote {
            if c == q {
                quote = None;
            }
            cur.push(c);
            continue;
        }
        match c {
            '"' | '\'' => quote = Some(c),
            '(' | '[' | '{' => depth += 1,
            ')' | ']' | '}' => depth -= 1,
            ',' if depth <= 0 => {
                out.push(std::mem::take(&mut cur).trim().to_string());
                continue;
            }
            _ => {}
        }
        cur.push(c);
    }
    if !cur.trim().is_empty() {
        out.push(cur.trim().to_string());
    }
    out
}

/// The frontmatter as a tree: nested maps and lists by indentation, which the
/// flat reader above cannot see. Claude Code's subagent format nests three
/// fields - `hooks:`, `mcpServers:` and `experimental:` - and a seat's own hook
/// registrations live in the first of them. Scalars stay strings; a `[a, b]`
/// flow list becomes an array. Anything it cannot read is left out.
pub fn frontmatter_tree(text: &str) -> Map<String, Value> {
    let text = text.strip_prefix('\u{feff}').unwrap_or(text);
    let mut it = text.lines();
    if it.next().map(|l| l.trim()) != Some("---") {
        return Map::new();
    }
    let mut lines: Vec<(usize, String)> = Vec::new();
    for l in it {
        if l.trim() == "---" {
            break;
        }
        let t = l.trim_end();
        let body = t.trim_start();
        if body.is_empty() || body.starts_with('#') {
            continue;
        }
        lines.push((t.len() - body.len(), body.to_string()));
    }
    let mut i = 0;
    match yaml_block(&lines, &mut i, 0) {
        Value::Object(m) => m,
        _ => Map::new(),
    }
}

fn yaml_scalar(s: &str) -> Value {
    let t = strip_comment(s.trim());
    if t.starts_with('[') && t.ends_with(']') {
        return Value::Array(
            split_top(&t[1..t.len() - 1])
                .into_iter()
                .map(|x| unquote(&x))
                .filter(|x| !x.is_empty())
                .map(Value::String)
                .collect(),
        );
    }
    let single = t.starts_with('\'');
    let u = unquote(&t);
    Value::String(if single { u.replace("''", "'") } else { u })
}

/// `key: rest` when the line opens a mapping entry. A quoted or flow scalar,
/// or a colon not followed by a space (`Bash(git commit:*)`), is not one.
fn yaml_kv(s: &str) -> Option<(String, String)> {
    if s.starts_with(['"', '\'', '[', '{']) {
        return None;
    }
    let idx = s.find(": ").or(if s.ends_with(':') { Some(s.len() - 1) } else { None })?;
    let key = s[..idx].trim();
    if key.is_empty() || key.contains(' ') {
        return None;
    }
    Some((unquote(key), s[idx + 1..].trim().to_string()))
}

fn is_item(body: &str) -> bool {
    body == "-" || body.starts_with("- ")
}

fn yaml_block(lines: &[(usize, String)], i: &mut usize, indent: usize) -> Value {
    let Some((ind0, first)) = lines.get(*i) else {
        return Value::Null;
    };
    let indent = (*ind0).max(indent);
    if is_item(first) {
        let mut arr = Vec::new();
        while let Some((ind, body)) = lines.get(*i) {
            if *ind != indent || !is_item(body) {
                break;
            }
            let rest = body[1..].trim_start().to_string();
            let col = indent + body.len() - rest.len();
            *i += 1;
            if rest.is_empty() {
                match lines.get(*i) {
                    Some((n, _)) if *n > indent => {
                        let n = *n;
                        arr.push(yaml_block(lines, i, n));
                    }
                    _ => arr.push(Value::Null),
                }
            } else if let Some((k, v)) = yaml_kv(&rest) {
                // `- key: value` opens a map whose later keys sit at `col`
                let mut m = Map::new();
                let first_val = yaml_value(lines, i, col, &v);
                m.insert(k, first_val);
                if lines.get(*i).map(|l| l.0) == Some(col) {
                    if let Value::Object(more) = yaml_block(lines, i, col) {
                        m.extend(more);
                    }
                }
                arr.push(Value::Object(m));
            } else {
                arr.push(yaml_scalar(&rest));
            }
        }
        return Value::Array(arr);
    }
    let mut m = Map::new();
    while let Some((ind, body)) = lines.get(*i) {
        if *ind != indent || is_item(body) {
            break;
        }
        *i += 1;
        if let Some((k, v)) = yaml_kv(body) {
            let val = yaml_value(lines, i, indent, &v);
            m.insert(k, val);
        }
    }
    Value::Object(m)
}

/// The value after `key:` - inline, a block scalar, or a nested block.
fn yaml_value(lines: &[(usize, String)], i: &mut usize, indent: usize, inline: &str) -> Value {
    if matches!(inline, "|" | ">" | "|-" | ">-" | "|+" | ">+") {
        let mut parts = Vec::new();
        while let Some((ind, body)) = lines.get(*i) {
            if *ind <= indent {
                break;
            }
            parts.push(body.clone());
            *i += 1;
        }
        let sep = if inline.starts_with('|') { "\n" } else { " " };
        return Value::String(parts.join(sep));
    }
    if !inline.is_empty() {
        return yaml_scalar(inline);
    }
    match lines.get(*i) {
        Some((n, _)) if *n > indent => {
            let n = *n;
            yaml_block(lines, i, n)
        }
        // YAML lets a list sit at its key's own indent
        Some((n, b)) if *n == indent && is_item(b) => yaml_block(lines, i, indent),
        _ => Value::Null,
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
/// The `hooks/<name>.sh` (or `.ps1`) occurrence wins over any other `hooks/`
/// in the line, so an argument such as `.claude/hooks/data` after the script
/// cannot rename it; failing that, the last occurrence, as before.
pub fn hook_name_from_command(cmd: &str) -> Option<String> {
    let norm = cmd.replace('\\', "/");
    let mut last = None;
    let mut start = 0;
    while let Some(i) = norm[start..].find("hooks/") {
        let at = start + i + "hooks/".len();
        let name: String = norm[at..]
            .chars()
            .take_while(|c| c.is_ascii_alphanumeric() || *c == '-' || *c == '_')
            .collect();
        if !name.is_empty() {
            let after = &norm[at + name.len()..];
            if after.starts_with(".sh") || after.starts_with(".ps1") {
                return Some(name);
            }
            last = Some(name);
        }
        start = at;
    }
    last
}

/// Events whose hook gates a tool call: exit 2 stops the call or refuses the
/// permission. A hook is `blocking` when any of its registrations is on one of
/// these. Stop and UserPromptSubmit hooks can exit 2 as well, but most of them
/// are advisory (a graph refresh, a log line), and badging every one of them
/// "blocks the call" would say something the event alone cannot prove.
pub const TOOL_GATE_EVENTS: &[&str] = &["PreToolUse", "PermissionRequest"];

/// One hook registration, from settings.json or from a seat's own frontmatter.
pub struct HookReg {
    /// `settings` or `agent:<name>`
    pub source: String,
    pub event: String,
    pub matcher: String,
    /// The command, or for a prompt/agent/http hook its type and text.
    pub command: String,
    /// The `.claude/hooks/<name>` the command runs, when it runs one.
    pub hook: Option<String>,
}

impl HookReg {
    /// `PreToolUse Agent -> spawn-guard`, the form the viewer shows.
    pub fn summary(&self) -> String {
        let target = match &self.hook {
            Some(h) => h.clone(),
            None => cap(&self.command, 120),
        };
        if self.matcher == "*" || self.matcher.is_empty() {
            format!("{} -> {target}", self.event)
        } else {
            format!("{} {} -> {target}", self.event, self.matcher)
        }
    }
}

fn cap(s: &str, n: usize) -> String {
    let s = s.trim();
    if s.chars().count() > n {
        s.chars().take(n).collect::<String>() + "..."
    } else {
        s.to_string()
    }
}

/// Every registration in a `hooks:` value - settings.json's and a subagent
/// frontmatter's share one shape: event -> [{matcher, hooks: [{type, command}]}].
pub fn hook_regs(source: &str, hooks: &Value) -> Vec<HookReg> {
    let mut out = Vec::new();
    let Some(events) = hooks.as_object() else { return out };
    for (event, groups) in events {
        for group in groups.as_array().map(|a| a.as_slice()).unwrap_or(&[]) {
            let matcher = group.get("matcher").and_then(|m| m.as_str()).unwrap_or("*");
            for h in group.get("hooks").and_then(|x| x.as_array()).map(|a| a.as_slice()).unwrap_or(&[]) {
                let ty = h.get("type").and_then(|t| t.as_str()).unwrap_or("command");
                let cmd = h.get("command").and_then(|c| c.as_str());
                let command = match cmd {
                    Some(c) => c.to_string(),
                    None => {
                        let body = ["prompt", "url"]
                            .iter()
                            .find_map(|k| h.get(*k).and_then(|x| x.as_str()))
                            .unwrap_or("");
                        format!("{ty}: {body}")
                    }
                };
                out.push(HookReg {
                    source: source.to_string(),
                    event: event.clone(),
                    matcher: matcher.to_string(),
                    hook: cmd.and_then(hook_name_from_command),
                    command,
                });
            }
        }
    }
    out
}

/// Registrations declared in the active seats' own frontmatter. Public for the
/// assessment, which must see a registration whose hook file is missing - and
/// a missing file produces no node to find it through.
pub fn agent_hook_regs(root: &Path) -> Vec<HookReg> {
    let mut out = Vec::new();
    for name in md_stems(&root.join(".claude/agents")) {
        let text = fs::read_to_string(root.join(".claude/agents").join(format!("{name}.md")))
            .unwrap_or_default();
        if let Some(h) = frontmatter_tree(&text).get("hooks") {
            out.extend(hook_regs(&format!("agent:{name}"), h));
        }
    }
    out
}

/// A seat whose job is to judge work rather than produce it. The fixed names are
/// the scaffolder's; the suffixes catch the same role under another spelling
/// (`security-privacy-reviewer`, `fact-checker`); `checker` is the skill's own
/// review gate for research, strategy and docs repositories, and `editor` the
/// one a writing repository usually names.
pub fn is_review_seat(name: &str) -> bool {
    REVIEWERS.contains(&name)
        || name == "editor"
        || name == "checker"
        || ["reviewer", "-checker", "auditor", "critic", "verifier"]
            .iter()
            .any(|s| name.ends_with(s))
}

/// The seats an `Agent(a, b)` (or legacy `Task(a, b)`) grant names. None when
/// the tool list grants spawning without naming anyone, or not at all.
pub fn spawn_targets(tools: &[String]) -> Option<Vec<String>> {
    let mut out: Vec<String> = Vec::new();
    let mut named = false;
    for t in tools {
        for head in ["Agent(", "Task("] {
            if let Some(inner) = t.strip_prefix(head).and_then(|r| r.strip_suffix(')')) {
                named = true;
                out.extend(split_top(inner).into_iter().map(|x| unquote(&x)).filter(|x| !x.is_empty()));
            }
        }
    }
    if named {
        out.sort();
        out.dedup();
        Some(out)
    } else {
        None
    }
}

/// The subagent frontmatter fields beyond model/effort/maxTurns/tools/description
/// (code.claude.com/docs/en/sub-agents, "Supported frontmatter fields"). Each is
/// added only when the file sets it, flattened to a string, a bool or a list of
/// strings so every viewer can print it without knowing the field.
fn agent_meta_extra(
    stem: &str,
    fm: &BTreeMap<String, Value>,
    tree: &Map<String, Value>,
    meta: &mut Map<String, Value>,
) {
    let flat = |k: &str| match fm.get(k) {
        Some(Value::String(s)) => Some(unquote(&strip_comment(s))),
        _ => None,
    };
    if let Some(n) = flat("name") {
        // Claude Code dispatches by `name:`, not by the file name. Say so when
        // they differ, or the graph names a seat nobody can call.
        if !n.is_empty() && n != stem {
            meta.insert("name".into(), json!(n));
        }
    }
    for k in ["permissionMode", "memory", "isolation", "color"] {
        if let Some(v) = flat(k).filter(|v| !v.is_empty()) {
            meta.insert(k.into(), json!(v));
        }
    }
    for k in ["background", "omitClaudeMd"] {
        match flat(k).as_deref() {
            Some("true") => {
                meta.insert(k.into(), json!(true));
            }
            Some("false") => {
                meta.insert(k.into(), json!(false));
            }
            Some(v) if !v.is_empty() => {
                meta.insert(k.into(), json!(v));
            }
            _ => {}
        }
    }
    if let Some(Value::String(p)) = tree.get("initialPrompt") {
        if !p.trim().is_empty() {
            meta.insert("initialPrompt".into(), json!(cap(p, 300)));
        }
    }
    for k in ["disallowedTools", "skills"] {
        if let Some(v) = fm.get(k) {
            let list = as_list(v);
            if !list.is_empty() {
                meta.insert(k.into(), json!(list));
            }
        }
    }
    // mcpServers: a list of server names, inline definitions keyed by name, or both
    let mut servers: Vec<String> = Vec::new();
    match tree.get("mcpServers") {
        Some(Value::Array(a)) => {
            for x in a {
                match x {
                    Value::String(s) => servers.push(s.clone()),
                    Value::Object(m) => servers.extend(m.keys().cloned()),
                    _ => {}
                }
            }
        }
        Some(Value::Object(m)) => servers.extend(m.keys().cloned()),
        Some(Value::String(s)) => servers.extend(as_list(&Value::String(s.clone()))),
        _ => {}
    }
    if !servers.is_empty() {
        meta.insert("mcpServers".into(), json!(servers));
    }
    if let Some(h) = tree.get("hooks") {
        let regs: Vec<String> = hook_regs("", h).iter().map(HookReg::summary).collect();
        if !regs.is_empty() {
            meta.insert("hooks".into(), json!(regs));
        }
    }
    let ttl = tree
        .get("experimental")
        .and_then(|e| e.get("cacheTtl"))
        .and_then(|v| v.as_str())
        .map(String::from)
        .or_else(|| flat("experimental.cacheTtl"));
    if let Some(t) = ttl.filter(|t| !t.is_empty()) {
        meta.insert("cacheTtl".into(), json!(t));
    }
    if let Some(Value::Array(tools)) = meta.get("tools") {
        let tools: Vec<String> = tools.iter().filter_map(|t| t.as_str().map(String::from)).collect();
        if let Some(t) = spawn_targets(&tools) {
            meta.insert("spawns".into(), json!(t));
        }
    }
}

/// The state folders of an orchestrator-kit task board, in board order.
pub const BOARD_STATES: &[&str] = &["pending", "active", "completed", "canceled"];

/// Where the task board lives: `env.TASK_BOARD_DIR` in settings.json when it is
/// a relative path inside the repo, else `.agent-base/tasks` - the kit's default
/// - when that directory exists. None when there is no board.
pub fn board_dir(root: &Path, settings: Option<&Value>) -> Option<String> {
    let from_env = settings
        .and_then(|v| v.get("env"))
        .and_then(|e| e.get("TASK_BOARD_DIR"))
        .and_then(|d| d.as_str())
        .map(|d| d.replace('\\', "/").trim_matches('/').to_string())
        .filter(|d| {
            !d.is_empty()
                && !d.contains(':')
                && !d.split('/').any(|s| s == ".." || s.is_empty())
        });
    let pick = from_env.unwrap_or_else(|| ".agent-base/tasks".to_string());
    if root.join(&pick).is_dir() {
        Some(pick)
    } else {
        None
    }
}

/// One row of a board's TASKS.md: | ID | task | agent | state | deps | mission |
pub struct IndexRow {
    pub title: String,
    pub owner: String,
    pub state: String,
    pub deps: String,
}

/// TASKS.md rows keyed by TASK id. Columns are read by position, the layout
/// task.sh writes; a row whose first cell is not a TASK id is not a task.
pub fn board_index(path: &Path) -> BTreeMap<String, IndexRow> {
    let mut out = BTreeMap::new();
    let text = fs::read_to_string(path).unwrap_or_default();
    for line in text.lines() {
        let t = line.trim();
        if !t.starts_with('|') {
            continue;
        }
        let cells: Vec<String> = t.trim_matches('|').split('|').map(|c| c.trim().to_string()).collect();
        let id = cells.first().cloned().unwrap_or_default();
        if !id.starts_with("TASK-") || id.len() < 6 {
            continue;
        }
        let cell = |i: usize| cells.get(i).cloned().filter(|s| s != "-").unwrap_or_default();
        out.insert(
            id,
            IndexRow { title: cell(1), owner: cell(2), state: cell(3), deps: cell(4) },
        );
    }
    out
}

fn board_has_index(root: &Path, board: Option<&str>) -> bool {
    board.map(|b| root.join(b).join("TASKS.md").is_file()).unwrap_or(false)
}

/// `TASK-007-fix-login` -> `TASK-007`: the id task.sh keys the index by.
pub fn task_id(stem: &str) -> String {
    let digits: String = stem
        .strip_prefix("TASK-")
        .unwrap_or("")
        .chars()
        .take_while(|c| c.is_ascii_digit())
        .collect();
    if digits.is_empty() {
        stem.to_string()
    } else {
        format!("TASK-{digits}")
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

/// Edges read out of the files themselves: what each agent, rule, command,
/// hook, skill and instruction file names. See `refs.rs` for what counts as a
/// reference. Runs once every node exists, so a reference can only resolve to a
/// node that is really there.
fn content_edges(
    root: &Path,
    nodes: &mut BTreeMap<String, Value>,
    edges: &mut Vec<(String, String, String, i64)>,
) {
    let mut inv = refs::Inventory::default();
    for (id, n) in nodes.iter() {
        let ty = n.get("type").and_then(|t| t.as_str()).unwrap_or("");
        let name = match id.split_once(':') {
            Some((_, rest)) => rest.to_string(),
            None => continue,
        };
        match ty {
            "agent" => inv.agent.insert(name),
            "skill" => inv.skill.insert(name),
            "rule" => inv.rule.insert(name),
            "command" => inv.command.insert(name),
            "hook" => inv.hook.insert(name),
            "script" => inv.script.insert(name),
            _ => false,
        };
    }
    let sources: Vec<(String, String, String)> = nodes
        .values()
        .filter_map(|n| {
            let ty = n.get("type")?.as_str()?;
            if !matches!(ty, "agent" | "rule" | "command" | "hook" | "skill" | "instruction") {
                return None;
            }
            Some((
                n.get("id")?.as_str()?.to_string(),
                ty.to_string(),
                n.get("file")?.as_str()?.to_string(),
            ))
        })
        .collect();
    for (id, kind, file) in &sources {
        let text = fs::read_to_string(root.join(file)).unwrap_or_default();
        for (to_kind, name) in refs::references(&text, &inv) {
            let to = refs::id_for(to_kind, &name);
            if &to == id {
                continue;
            }
            edges.push((id.clone(), to, refs::edge_type(kind, to_kind).into(), 0));
        }
        // Claude Code's own subagent field: `skills:` in the frontmatter preloads
        // those skills into the seat, which is a wire whatever the names look like.
        if kind == "agent" {
            if let Some(v) = frontmatter(&text).get("skills") {
                for s in as_list(v) {
                    if inv.skill.contains(&s) {
                        edges.push((id.clone(), format!("skill:{s}"), "uses".into(), 0));
                    }
                }
            }
        }
    }
    // A hook nothing registers but another hook sources is a library, not a hook
    // that was switched off. Say so, or the viewer badges a shared helper OFF.
    let sourced: BTreeSet<String> = edges
        .iter()
        .filter(|e| e.2 == "sources")
        .map(|e| e.1.clone())
        .collect();
    for id in sourced {
        if let Some(Value::Object(n)) = nodes.get_mut(&id) {
            if let Some(Value::Object(m)) = n.get_mut("meta") {
                if m.get("registered") == Some(&Value::Bool(false)) {
                    m.insert("library".into(), Value::Bool(true));
                }
            }
        }
    }
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
    let mut agent_regs: Vec<HookReg> = Vec::new();
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
        let tree = frontmatter_tree(&text);
        agent_meta_extra(&name, &fm, &tree, &mut meta);
        if !dis {
            if let Some(h) = tree.get("hooks") {
                for r in hook_regs(&format!("agent:{name}"), h) {
                    agent_regs.push(r);
                }
            }
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
    let settings_path = claude.join("settings.json");
    let have_settings = settings_path.is_file();
    let settings_v: Option<Value> = fs::read_to_string(&settings_path)
        .ok()
        .and_then(|t| serde_json::from_str::<Value>(&t).ok());
    let settings_regs: Vec<HookReg> = settings_v
        .as_ref()
        .and_then(|v| v.get("hooks"))
        .map(|h| hook_regs("settings", h))
        .unwrap_or_default();
    if have_settings {
        let mut node = json!({"id": "settings", "type": "settings", "label": "settings.json",
                   "file": rel(root, ".claude/settings.json"), "disabled": false,
                   // Editable through the same key-and-name write path the
                   // instruction files use, which is why settings.json has an
                   // entry in instruction::FILES despite not being one.
                   "edit": {"key": "settings", "name": ""}});
        // Registrations that run no file in .claude/hooks/: an inline command, a
        // Python hook, a prompt or http hook. They fire all the same, and a
        // viewer that only drew hook files hid every SessionStart one-liner.
        let other: Vec<String> = settings_regs
            .iter()
            .filter(|r| r.hook.as_ref().map(|h| !hook_files.contains_key(h)).unwrap_or(true))
            .map(HookReg::summary)
            .collect();
        if !other.is_empty() {
            node["meta"] = json!({ "otherHooks": other });
        }
        nodes.insert("settings".into(), node);
    }

    for (name, (file, disabled)) in &hook_files {
        let id = format!("hook:{name}");
        let mut meta = Map::new();
        let regs: Vec<&HookReg> = settings_regs
            .iter()
            .chain(agent_regs.iter())
            .filter(|r| r.hook.as_deref() == Some(name.as_str()))
            .collect();
        let registered = !regs.is_empty();
        meta.insert("registered".into(), json!(registered));
        if let Some(first) = regs.first() {
            meta.insert("event".into(), json!(first.event));
            meta.insert("matcher".into(), json!(first.matcher));
            let gates = regs.iter().any(|r| TOOL_GATE_EVENTS.contains(&r.event.as_str()));
            meta.insert("blocking".into(), json!(gates));
        }
        // Registered more than once (two events, or settings plus a seat): list
        // every one, because the first alone under-reports what the hook guards.
        let mut seen: Vec<String> = Vec::new();
        for r in &regs {
            let s = if r.matcher == "*" { r.event.clone() } else { format!("{} {}", r.event, r.matcher) };
            if !seen.contains(&s) {
                seen.push(s);
            }
        }
        if seen.len() > 1 {
            meta.insert("events".into(), json!(seen));
        }
        // A hook a seat registers in its own frontmatter fires only while that
        // seat runs. `scope` names the seats; absent means session-wide.
        let mut scope: Vec<String> = regs
            .iter()
            .filter_map(|r| r.source.strip_prefix("agent:").map(String::from))
            .collect();
        scope.sort();
        scope.dedup();
        if !scope.is_empty() {
            for a in &scope {
                edges.push((format!("agent:{a}"), id.clone(), "triggers".into(), 0));
            }
            if !regs.iter().any(|r| r.source == "settings") {
                meta.insert("scope".into(), json!(scope));
            }
        }
        nodes.insert(
            id.clone(),
            json!({"id": id, "type": "hook", "label": name,
                   "file": rel(root, file), "disabled": disabled, "meta": Value::Object(meta)}),
        );
        if have_settings && regs.iter().any(|r| r.source == "settings") {
            edges.push(("settings".into(), format!("hook:{name}"), "triggers".into(), 0));
        }
    }

    // --- scripts: every .py, .sh and .ps1 under .claude/scripts/. One node per
    // name; when two flavors share a name the .py wins, then the .sh. ---
    if let Ok(rd) = fs::read_dir(claude.join("scripts")) {
        let mut files: Vec<String> = rd
            .flatten()
            .filter(|e| e.path().is_file())
            .filter_map(|e| e.file_name().to_str().map(|s| s.to_string()))
            .collect();
        files.sort();
        let mut by_stem: BTreeMap<String, String> = BTreeMap::new();
        for ext in ["py", "sh", "ps1"] {
            for f in &files {
                if let Some(stem) = f.strip_suffix(&format!(".{ext}")) {
                    if !stem.is_empty() {
                        by_stem.entry(stem.to_string()).or_insert_with(|| f.clone());
                    }
                }
            }
        }
        for (name, fname) in by_stem {
            nodes.insert(
                format!("script:{name}"),
                json!({"id": format!("script:{name}"), "type": "script",
                       "label": fname, "disabled": false,
                       "file": rel(root, &format!(".claude/scripts/{fname}"))}),
            );
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
    // The orchestrator-kit board: <board>/{pending,active,completed,canceled}/
    // TASK-NNN[-slug].md plus a TASKS.md index, kept in step by task.sh. The
    // folder IS the state, so it stands in for a missing `status:`.
    let board = board_dir(root, settings_v.as_ref());
    let mut board_files: Vec<(String, String)> = Vec::new();
    if let Some(b) = &board {
        if !b.starts_with("docs/tasks") {
            walk_tasks(&root.join(b), &mut board_files, root);
            board_files.sort();
        }
    }
    let index = board.as_deref().map(|b| board_index(&root.join(b).join("TASKS.md"))).unwrap_or_default();
    let mut indexed_seen: BTreeSet<String> = BTreeSet::new();
    let all_tasks: Vec<(String, String, bool)> = task_files
        .iter()
        .map(|(s, r)| (s.clone(), r.clone(), false))
        .chain(board_files.iter().map(|(s, r)| (s.clone(), r.clone(), true)))
        .collect();
    for (stem, relpath, on_board) in &all_tasks {
        let body = fs::read_to_string(root.join(relpath)).unwrap_or_default();
        let mut fm = frontmatter(&body);
        // task.sh writes `agent:` and `depends_on:` where the docs/tasks
        // templates write `owner:` and `deps:`; same fields, other spelling.
        for (canon, alias) in [("owner", "agent"), ("deps", "depends_on")] {
            if !fm.contains_key(canon) {
                if let Some(v) = fm.get(alias).cloned() {
                    fm.insert(canon.into(), v);
                }
            }
        }
        // The board fields, in the order the templates declare them. Everything
        // here is what makes a task row readable without opening the file.
        let mut meta = Map::new();
        for key in ["title", "status", "fr", "owner", "deps", "priority", "phase"] {
            if let Some(Value::String(v)) = fm.get(key) {
                let v = unquote(&strip_comment(v));
                // task.sh writes `-` for "none"; on its board that is no value at all
                if !v.is_empty() && (!*on_board || v != "-") {
                    meta.insert(key.to_string(), Value::String(v));
                }
            }
        }
        if *on_board {
            let folder = Path::new(relpath)
                .parent()
                .and_then(|p| p.file_name())
                .and_then(|x| x.to_str())
                .unwrap_or("")
                .to_string();
            if BOARD_STATES.contains(&folder.as_str()) {
                if !meta.contains_key("status") {
                    meta.insert("status".into(), json!(folder));
                }
                // task.sh check, restated: folder, `status:` and the index row
                // must agree. Record what disagrees rather than pick a winner.
                let mut drift: Vec<String> = Vec::new();
                if let Some(s) = meta.get("status").and_then(|v| v.as_str()) {
                    if s != folder {
                        drift.push(format!("status: {s} but the file is in {folder}/"));
                    }
                }
                let id = task_id(stem);
                match index.get(&id) {
                    Some(row) if row.state != folder => {
                        drift.push(format!("TASKS.md says {} but the file is in {folder}/", row.state))
                    }
                    Some(_) => {}
                    None if board_has_index(root, board.as_deref()) => {
                        drift.push("no row in TASKS.md".into())
                    }
                    None => {}
                }
                indexed_seen.insert(id);
                if !drift.is_empty() {
                    meta.insert("drift".into(), json!(drift));
                }
            }
            for key in ["mission", "attempts"] {
                if let Some(Value::String(v)) = fm.get(key) {
                    let v = unquote(&strip_comment(v));
                    if !v.is_empty() && v != "-" {
                        meta.insert(key.to_string(), Value::String(v));
                    }
                }
            }
            if let Some(b) = &board {
                meta.insert("board".into(), json!(b));
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
    // A TASKS.md row whose file is in no state folder: the index promises work
    // the board cannot show. It still gets a node, so the gap is visible.
    for (id, row) in &index {
        if indexed_seen.contains(id) || nodes.contains_key(&format!("task:{id}")) {
            continue;
        }
        let mut meta = Map::new();
        for (k, v) in [("title", &row.title), ("owner", &row.owner), ("status", &row.state), ("deps", &row.deps)] {
            if !v.is_empty() {
                meta.insert(k.into(), json!(v));
            }
        }
        if let Some(b) = &board {
            meta.insert("board".into(), json!(b));
        }
        meta.insert("drift".into(), json!(["in TASKS.md but no file in any state folder"]));
        nodes.insert(
            format!("task:{id}"),
            json!({"id": format!("task:{id}"), "type": "task", "label": id,
                   "disabled": false, "meta": Value::Object(meta)}),
        );
        for one in row.owner.split('+').map(str::trim).filter(|s| !s.is_empty()) {
            if agent_names.iter().any(|a| a == one) {
                edges.push((format!("agent:{one}"), format!("task:{id}"), "owns".into(), 0));
            }
        }
    }

    // --- relationship edges over the collected nodes ---
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

    // --- instruction files: AGENTS.md, CLAUDE.md and the per-tool equivalents.
    // These are the only nodes that live OUTSIDE .claude/, and that is the
    // point: they are the contract every seat is told to obey, and a viewer
    // that stopped at the .claude/ boundary could not show it. The paths come
    // from instruction::FILES, which carries the evidence for each one.
    let instr_found = crate::instruction::found(root);
    // Which tier the routing table names for a seat. Filled from whichever
    // instruction file actually carries the table (v1.18.0 puts it in
    // AGENTS.md); a repo whose AGENTS.md predates that release simply has no
    // tiers, and no tier is invented for a seat the table does not name.
    let mut agent_tier: BTreeMap<String, String> = BTreeMap::new();
    let rule_names: Vec<String> = nodes
        .values()
        .filter(|n| n.get("type").and_then(|t| t.as_str()) == Some("rule"))
        .filter(|n| n.get("disabled").and_then(|d| d.as_bool()) != Some(true))
        .filter_map(|n| n.get("label").and_then(|l| l.as_str()).map(|s| s.to_string()))
        .collect();
    for (sp, name, relpath) in &instr_found {
        let id = if name.is_empty() {
            format!("instr:{}", sp.key)
        } else {
            format!("instr:{}/{name}", sp.key)
        };
        let text = fs::read_to_string(root.join(relpath)).unwrap_or_default();
        let mut node = Map::new();
        node.insert("id".into(), json!(id));
        node.insert("type".into(), json!("instruction"));
        node.insert("label".into(), json!(relpath));
        node.insert("file".into(), json!(relpath));
        node.insert("disabled".into(), json!(false));
        let mut meta = crate::instruction::meta_for(sp);
        // Size travels with the node so `assess` can tell a per-folder contract that governs a
        // subtree from one that only looks like it does. Counted from the text already read for
        // the tier parse below, so this costs nothing extra.
        meta.insert("bytes".into(), json!(text.len()));
        node.insert("meta".into(), Value::Object(meta));
        // The write path takes a key and a bare name, never this path - see the
        // containment note in instruction.rs. The node carries both so the page
        // never has to compose one.
        node.insert("edit".into(), json!({"key": sp.key, "name": name}));
        let tiers = crate::instruction::tier_rows(&text);
        if !tiers.is_empty() {
            for row in &tiers {
                let tier = row.get("tier").and_then(|x| x.as_str()).unwrap_or("");
                let who = row.get("who").and_then(|x| x.as_str()).unwrap_or("");
                // A tier row that NAMES a seat routes to it. The Direct and
                // Standard rows say "the owning agent" and name nobody, so they
                // route to nobody: guessing which seats they mean is exactly
                // the invention the table exists to replace.
                for tok in slug_tokens(who) {
                    if agent_names.iter().any(|a| *a == tok) {
                        agent_tier.insert(tok.clone(), tier.to_string());
                        edges.push((id.clone(), format!("agent:{tok}"), "routes".into(), 0));
                    }
                }
            }
            node.insert("tiers".into(), Value::Array(tiers));
        }
        nodes.insert(id.clone(), Value::Object(node));

        // CLAUDE.md is a thin `@AGENTS.md` import, and saying so in the graph is
        // what stops a reader treating it as a second, competing contract.
        for (other_sp, other_name, other_rel) in &instr_found {
            if !other_name.is_empty() || other_rel == relpath {
                continue;
            }
            if text.contains(&format!("@{other_rel}")) {
                edges.push((
                    id.clone(),
                    format!("instr:{}", other_sp.key),
                    "imports".into(),
                    0,
                ));
            }
        }
        // A rule the contract actually points at, matched by the path it cites
        // rather than by the bare word: "testing" appears in prose everywhere,
        // `.claude/rules/testing.md` does not.
        let norm = text.replace('\\', "/");
        for r in &rule_names {
            if norm.contains(&format!("rules/{r}.md")) {
                edges.push((id.clone(), format!("rule:{r}"), "cites".into(), 0));
            }
        }
        // A seat the contract briefs. Agent names are slugs, so a token match is
        // exact; a substring match would brief every seat whose name happens to
        // sit inside another word.
        let tokens: std::collections::BTreeSet<String> = slug_tokens(&text).into_iter().collect();
        for a in &agent_names {
            if tokens.contains(a) {
                edges.push((id.clone(), format!("agent:{a}"), "briefs".into(), 0));
            }
        }
    }
    for (agent, tier) in &agent_tier {
        if let Some(Value::Object(n)) = nodes.get_mut(&format!("agent:{agent}")) {
            let meta = n
                .entry("meta".to_string())
                .or_insert_with(|| Value::Object(Map::new()));
            if let Some(m) = meta.as_object_mut() {
                m.insert("tier".into(), json!(tier));
            }
        }
    }

    content_edges(root, &mut nodes, &mut edges);

    // Who can start whom. `Agent(a, b)` in a seat's tools names exactly who it
    // may spawn; the orchestrator, or any seat holding a bare `Agent`, can spawn
    // every other seat on the roster.
    for agent in &agent_names {
        let m = nodes.get(&format!("agent:{agent}")).and_then(|n| n.get("meta"));
        let named: Option<Vec<String>> = m
            .and_then(|m| m.get("spawns"))
            .and_then(|s| s.as_array())
            .map(|a| a.iter().filter_map(|x| x.as_str().map(String::from)).collect());
        let bare = m
            .and_then(|m| m.get("tools"))
            .and_then(|t| t.as_array())
            .map(|a| a.iter().any(|t| matches!(t.as_str(), Some("Agent") | Some("Task"))))
            .unwrap_or(false);
        let targets: Vec<&String> = match &named {
            Some(list) => agent_names.iter().filter(|a| list.contains(a)).collect(),
            None if agent == "orchestrator" || bare => agent_names.iter().collect(),
            None => Vec::new(),
        };
        for t in targets {
            if t != agent {
                edges.push((format!("agent:{agent}"), format!("agent:{t}"), "spawns".into(), 0));
            }
        }
    }
    // orchestrator-kit's spawn-guard.sh admits, besides the roster, the built-in
    // agents listed one per line in .claude/hooks/spawn-allowlist. Built-ins are
    // not nodes, so the list rides on the seat whose guard reads it.
    let allow_path = claude.join("hooks").join("spawn-allowlist");
    if let Ok(txt) = fs::read_to_string(&allow_path) {
        let allow: Vec<String> = txt
            .lines()
            .map(|l| l.split('#').next().unwrap_or("").trim().to_string())
            .filter(|l| !l.is_empty())
            .collect();
        let readers: BTreeSet<String> = agent_regs
            .iter()
            .filter(|r| {
                r.hook
                    .as_ref()
                    .and_then(|h| hook_files.get(h))
                    .and_then(|(f, _)| fs::read_to_string(root.join(f)).ok())
                    .map(|t| t.contains("spawn-allowlist"))
                    .unwrap_or(false)
            })
            .filter_map(|r| r.source.strip_prefix("agent:").map(String::from))
            .collect();
        let seats: Vec<String> = if readers.is_empty() {
            agent_names.iter().filter(|a| *a == "orchestrator").cloned().collect()
        } else {
            readers.into_iter().collect()
        };
        for s in seats {
            if let Some(Value::Object(n)) = nodes.get_mut(&format!("agent:{s}")) {
                if let Some(Value::Object(m)) = n.get_mut("meta") {
                    m.insert("spawnAllowlist".into(), json!(allow));
                }
            }
        }
    }
    for r in &agent_names {
        // active seats only - a parked agent file reviews nothing
        if is_review_seat(r) {
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
