//! Editing an agent's frontmatter, and the model/tool reference the pickers are
//! built from.
//!
//! Two jobs live here because they are two halves of one promise: the viewer
//! lets someone control their roster - which model a seat runs on, how hard it
//! thinks, and exactly which tools it may call - and a roster is only
//! controllable if the choices on offer are real. So one half writes
//! `.claude/agents/<name>.md`, and the other half serves (and lets the user
//! correct) the list of models and tools each vendor actually has.
//!
//! # The frontmatter writer, and the one thing it guarantees
//!
//! **The markdown body comes back byte-identical.** That is not a nice-to-have.
//! The body of an agent file IS the agent - it is the instructions a model will
//! read - and a "helpful" reformat that re-wraps a line, normalizes a list
//! marker or strips a trailing space has silently rewritten someone's prompt.
//! So this module never parses the body, never re-emits the document, and never
//! round-trips through a YAML library. It finds the byte offset where the
//! closing `---` line starts, and everything from that offset onward is copied
//! through untouched. `frontmatter_span` returns exactly that offset;
//! `apply_frontmatter` splices only inside it. See
//! `body_is_byte_identical_after_a_write` in tests/agentedit_test.rs.
//!
//! Inside the frontmatter the same discipline applies one level down: a key is
//! edited by replacing THE LINES IT OCCUPIES, not by rebuilding the block. A
//! `color:` this editor has never heard of, a comment, a blank line, the order
//! the keys were written in, and a `tools:` written as a block list instead of a
//! comma-separated one all survive an edit to a neighbouring key, because they
//! are never read in the first place. And a key whose rendered form is identical
//! to what is already there is not rewritten at all, so "write only the keys
//! that changed" holds even if a client posts a field it did not change.
//!
//! Four keys are writable - `model`, `effort`, `tools`, `description` - and
//! nothing else. That allow-list is the containment for CONTENT, the same way
//! `resolve_agent` is the containment for PATHS: a request cannot introduce a
//! `permissions:` block or overwrite `name:` (which is the seat's identity and
//! the thing the graph keys on) no matter what it sends.
//!
//! # The reference, and why a user's edits never touch the shipped asset
//!
//! `harness-bootstrap/assets/references/models-and-tools.json` is SEED data,
//! compiled in. It is versioned with the skill, it is what an upgrade replaces,
//! and it goes stale the moment a vendor ships a model - which is the whole
//! reason the user asked to be able to correct it.
//!
//! A user's corrections therefore do NOT go back into that file. They are stored
//! as an overlay at `<served-root>/.claude/state/references.json` - inside the
//! repository being VIEWED, which is where a fact about that repository's roster
//! belongs - and merged over the seed on every read. An upgrade replaces the
//! seed and the overlay still applies; a repo copied to another machine carries
//! its corrections with it; and the asset in this repository is never written by
//! a server request, so no amount of clicking can make the shipped list drift
//! from what was researched.
//!
//! `verified` is the one field the overlay may not touch on a seed entry. That
//! flag is the honesty of the file - one Z.AI model carries `verified: false`
//! because it could not be confirmed against a first-party source, and the UI
//! marks it - so an override that "corrects" a note is applied and an override
//! that flips `verified` on a seed entry is dropped at merge time, not merely
//! discouraged. An entry the USER adds carries whatever `verified` they claim,
//! plus `custom: true`, so the two can never be confused.
//!
//! Output is canonical: sorted keys at every depth, two-space indent, trailing
//! newline, no timestamps and no counters. State this repository generates has
//! to be diffable, and a file that changes every time it is written is a file
//! nobody can review.

use crate::scan;
use serde_json::{json, Map, Value};
use std::fs;
use std::path::{Path, PathBuf};

/// The researched reference, compiled in. Reaching out of the crate is
/// deliberate: this is the same file the skill ships to a bootstrapped repo, and
/// a second copy under `tools/` would be a second thing to keep in step - which
/// is exactly how a reference goes stale in one place and not the other.
pub const SEED: &str =
    include_str!("../../../harness-bootstrap/assets/references/models-and-tools.json");

/// The only frontmatter keys a request may write. See the module header.
pub const WRITABLE: [&str; 4] = ["model", "effort", "tools", "description"];

/// Largest agent file this will rewrite. Three orders of magnitude above the
/// biggest shipped agent; a cap exists so a runaway page cannot fill a disk.
pub const AGENT_CAP: usize = 512 * 1024;

/// Caps on the values themselves. A description is prose and gets room; a model
/// id, an effort and a tool name are slugs and do not.
const SLUG_CAP: usize = 200;
const TEXT_CAP: usize = 8_000;
const TOOLS_CAP: usize = 200;

// ---------------------------------------------------------------------------
// frontmatter
// ---------------------------------------------------------------------------

/// Byte offsets `(start, end)` of the frontmatter block: `start` is the first
/// byte after the opening `---` line, `end` is the first byte OF the closing
/// `---` line. `text[end..]` is the closing delimiter plus the entire body, and
/// it is what a write copies through untouched.
pub fn frontmatter_span(text: &str) -> Result<(usize, usize), String> {
    let bom = if text.starts_with('\u{feff}') { '\u{feff}'.len_utf8() } else { 0 };
    let rest = &text[bom..];
    let first_end = match rest.find('\n') {
        Some(i) => i + 1,
        None => return Err("no YAML frontmatter: the file has no line break".into()),
    };
    if strip_eol(&rest[..first_end]).trim() != "---" {
        return Err("no YAML frontmatter: the file does not open with `---`".into());
    }
    let start = bom + first_end;
    let mut i = start;
    while i < text.len() {
        let line_end = text[i..].find('\n').map(|k| i + k + 1).unwrap_or(text.len());
        if strip_eol(&text[i..line_end]).trim() == "---" {
            return Ok((start, i));
        }
        i = line_end;
    }
    Err("no YAML frontmatter: the opening `---` is never closed".into())
}

/// A line without its terminator, LF or CRLF. Used everywhere a line is
/// COMPARED; the raw line with its terminator is what is ever written back.
fn strip_eol(s: &str) -> &str {
    let s = s.strip_suffix('\n').unwrap_or(s);
    s.strip_suffix('\r').unwrap_or(s)
}

/// The line ending the frontmatter already uses, so an edit does not convert a
/// CRLF file to LF halfway down.
fn eol_of(src: &str) -> &'static str {
    if src.contains("\r\n") {
        "\r\n"
    } else {
        "\n"
    }
}

/// Frontmatter split into raw lines, each still carrying its own terminator.
fn to_lines(src: &str) -> Vec<String> {
    src.split_inclusive('\n').map(|s| s.to_string()).collect()
}

/// The top-level key a line opens, if it opens one. Indented lines, list items,
/// comments and blank lines belong to whatever key came before them.
fn line_key(raw: &str) -> Option<String> {
    let s = strip_eol(raw);
    if s.is_empty() || s.starts_with(' ') || s.starts_with('\t') || s.trim_start().starts_with('#') {
        return None;
    }
    if s.trim_start().starts_with("- ") {
        return None;
    }
    let idx = s.find(':')?;
    let k = &s[..idx];
    if k.is_empty() || !k.chars().all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-' || c == '.') {
        return None;
    }
    Some(k.to_string())
}

/// The half-open line range `key` occupies, including any continuation lines
/// (a block list, a folded scalar) that follow it.
fn key_span(lines: &[String], key: &str) -> Option<(usize, usize)> {
    let start = lines.iter().position(|l| line_key(l).as_deref() == Some(key))?;
    let mut end = start + 1;
    while end < lines.len() && line_key(&lines[end]).is_none() {
        end += 1;
    }
    // Trailing blank lines belong to the block, not to the key: leaving them in
    // the span would delete someone's spacing when a key is rewritten.
    while end > start + 1 && strip_eol(&lines[end - 1]).trim().is_empty() {
        end -= 1;
    }
    Some((start, end))
}

/// Unwrap a YAML scalar written plainly, single-quoted or double-quoted.
fn parse_scalar(raw: &str) -> String {
    let s = raw.trim();
    if s.len() >= 2 && s.starts_with('"') && s.ends_with('"') {
        let inner = &s[1..s.len() - 1];
        let mut out = String::with_capacity(inner.len());
        let mut esc = false;
        for c in inner.chars() {
            if esc {
                out.push(match c {
                    'n' => '\n',
                    'r' => '\r',
                    't' => '\t',
                    other => other,
                });
                esc = false;
            } else if c == '\\' {
                esc = true;
            } else {
                out.push(c);
            }
        }
        return out;
    }
    if s.len() >= 2 && s.starts_with('\'') && s.ends_with('\'') {
        return s[1..s.len() - 1].replace("''", "'");
    }
    s.to_string()
}

/// Render a scalar, quoting only when a plain scalar would not survive a
/// re-read. Quoting when it is not needed is not wrong, but it churns bytes in
/// a file a human reads, so it is avoided.
fn emit_scalar(v: &str) -> String {
    let first = v.chars().next();
    let needs = v.is_empty()
        || v.contains(['\n', '\r', '\t'])
        || v.trim() != v
        || v.contains(": ")
        || v.ends_with(':')
        || v.contains(" #")
        || matches!(
            first,
            Some('"') | Some('\'') | Some('&') | Some('*') | Some('!') | Some('|') | Some('>')
                | Some('%') | Some('@') | Some('`') | Some('#') | Some('-') | Some('?')
                | Some(',') | Some('[') | Some(']') | Some('{') | Some('}')
        );
    if !needs {
        return v.to_string();
    }
    let mut out = String::with_capacity(v.len() + 8);
    out.push('"');
    for c in v.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

/// The lines a key's new value occupies. `tools` is emitted as the
/// comma-separated flow the harness's own agent files use, in the order given -
/// the caller's order, never a sorted one, because the order a roster lists its
/// tools in is a choice someone made.
fn emit_key(key: &str, value: &Value, eol: &str) -> Result<Vec<String>, String> {
    match value {
        Value::Array(items) => {
            let names: Vec<String> = items
                .iter()
                .map(|i| i.as_str().unwrap_or_default().trim().to_string())
                .collect();
            Ok(vec![format!("{key}: {}{eol}", names.join(", "))])
        }
        Value::String(s) => Ok(vec![format!("{key}: {}{eol}", emit_scalar(s))]),
        _ => Err(format!("`{key}` must be a string or a list of strings")),
    }
}

/// Read the top-level frontmatter keys back out. Used by the tests and by
/// anything that needs the CURRENT value of a key it is about to change;
/// `tools` comes back as a list whether it was written inline or as a block.
pub fn read_frontmatter(text: &str) -> Result<Map<String, Value>, String> {
    let (start, end) = frontmatter_span(text)?;
    let lines = to_lines(&text[start..end]);
    let mut out = Map::new();
    let mut i = 0;
    while i < lines.len() {
        let Some(key) = line_key(&lines[i]) else {
            i += 1;
            continue;
        };
        let (s, e) = key_span(&lines, &key).unwrap_or((i, i + 1));
        let head = strip_eol(&lines[s]);
        let inline = head.split_once(':').map(|(_, v)| v.trim()).unwrap_or("");
        let mut items: Vec<String> = Vec::new();
        for l in &lines[s + 1..e] {
            let t = strip_eol(l).trim_start();
            if let Some(item) = t.strip_prefix("- ") {
                items.push(parse_scalar(item));
            }
        }
        let value = if !items.is_empty() {
            Value::Array(items.into_iter().map(Value::String).collect())
        } else if inline.starts_with('[') && inline.ends_with(']') {
            Value::Array(
                inline[1..inline.len() - 1]
                    .split(',')
                    .map(|x| Value::String(parse_scalar(x)))
                    .filter(|v| !v.as_str().unwrap_or_default().is_empty())
                    .collect(),
            )
        } else if key == "tools" {
            Value::Array(
                inline
                    .split(',')
                    .map(|x| x.trim())
                    .filter(|x| !x.is_empty())
                    .map(|x| Value::String(x.to_string()))
                    .collect(),
            )
        } else {
            Value::String(parse_scalar(inline))
        };
        out.insert(key, value);
        i = e.max(i + 1);
    }
    Ok(out)
}

/// Rewrite the named frontmatter keys and nothing else.
///
/// `changes` is applied one key at a time so line numbers cannot drift. A key
/// that is absent is appended to the end of the frontmatter block; a key whose
/// rendered lines already match what is there is left alone, which is what makes
/// "only the keys that changed are written" true of the FILE rather than only of
/// the request.
pub fn apply_frontmatter(text: &str, changes: &Map<String, Value>) -> Result<String, String> {
    let (start, end) = frontmatter_span(text)?;
    let src = &text[start..end];
    let eol = eol_of(if src.is_empty() { text } else { src });
    let mut lines = to_lines(src);

    // A stable order, so two clients posting the same two new keys produce the
    // same file rather than two files that differ only in append order.
    let mut keys: Vec<&String> = changes.keys().collect();
    keys.sort();
    for key in keys {
        if !WRITABLE.contains(&key.as_str()) {
            return Err(format!(
                "refused: `{key}` is not editable here - only {} are",
                WRITABLE.join(", ")
            ));
        }
        let rendered = emit_key(key, &changes[key], eol)?;
        match key_span(&lines, key) {
            Some((s, e)) => {
                if lines[s..e] == rendered[..] {
                    continue; // already exactly this: not a change, not a write
                }
                lines.splice(s..e, rendered);
            }
            None => {
                // Append, and make sure the line before it is terminated: a
                // frontmatter whose last line lost its newline would otherwise
                // swallow the new key onto the end of it.
                if let Some(last) = lines.last_mut() {
                    if !last.ends_with('\n') {
                        last.push_str(eol);
                    }
                }
                lines.extend(rendered);
            }
        }
    }

    let mut out = String::with_capacity(text.len() + 64);
    out.push_str(&text[..start]);
    out.push_str(&lines.concat());
    // Everything from the closing `---` onward, byte for byte.
    out.push_str(&text[end..]);
    Ok(out)
}

// ---------------------------------------------------------------------------
// the agent file: containment and validation
// ---------------------------------------------------------------------------

/// Resolve the agent file a write is allowed to touch.
///
/// This takes a NAME, never a path - the same rule `resolve_command` follows in
/// serve.rs and for the same reason. Building the path from a validated bare
/// name means there is no traversal to contain: `..`, a separator, a drive
/// letter or a URL fail the character check before any path exists, so the
/// refusal cannot depend on getting a canonicalization right on two operating
/// systems.
pub fn resolve_agent(root: &Path, name: &str) -> Result<PathBuf, String> {
    let n = name.trim();
    if n.is_empty() {
        return Err("no agent named".into());
    }
    if n.len() > SLUG_CAP
        || !n.chars().all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
        || n.starts_with('-')
    {
        return Err(format!(
            "refused: `{name}` is not a bare agent name (letters, digits, dash, underscore)"
        ));
    }
    let p = root.join(".claude").join("agents").join(format!("{n}.md"));
    if !p.is_file() {
        return Err(format!(
            "no active agent named `{n}` - a disabled agent is not editable; enable it first"
        ));
    }
    Ok(p)
}

fn check_slug(key: &str, v: &str) -> Result<String, String> {
    let t = v.trim();
    if t.is_empty() {
        return Err(format!("refused: `{key}` cannot be empty"));
    }
    if t.len() > SLUG_CAP {
        return Err(format!("refused: `{key}` is longer than {SLUG_CAP} characters"));
    }
    if t.chars().any(|c| c.is_control()) {
        return Err(format!("refused: `{key}` contains a line break or control character"));
    }
    Ok(t.to_string())
}

/// Turn a request body into the exact set of frontmatter changes to apply,
/// refusing anything malformed before a file is opened.
pub fn changes_from_request(v: &Value) -> Result<Map<String, Value>, String> {
    let mut out = Map::new();
    for key in ["model", "effort"] {
        if let Some(raw) = v.get(key) {
            let s = raw
                .as_str()
                .ok_or_else(|| format!("refused: `{key}` must be a string"))?;
            out.insert(key.to_string(), Value::String(check_slug(key, s)?));
        }
    }
    if let Some(raw) = v.get("description") {
        let s = raw
            .as_str()
            .ok_or_else(|| "refused: `description` must be a string".to_string())?;
        let s = s.replace("\r\n", "\n");
        let s = s.trim().to_string();
        if s.is_empty() {
            return Err("refused: `description` cannot be empty - it is what routes work to this \
                        seat"
                .into());
        }
        if s.len() > TEXT_CAP {
            return Err(format!("refused: `description` is longer than {TEXT_CAP} characters"));
        }
        out.insert("description".into(), Value::String(s));
    }
    if let Some(raw) = v.get("tools") {
        let arr = raw
            .as_array()
            .ok_or_else(|| "refused: `tools` must be a list of strings".to_string())?;
        if arr.is_empty() {
            // In Claude Code an ABSENT `tools` means "inherit everything", so an
            // empty list is not "no tools" - it is a different, much wider grant
            // wearing the wrong clothes. Refuse rather than guess.
            return Err("refused: an empty tools list is not the same as no tools - pick at least \
                        one, or remove the key by hand to inherit every tool"
                .into());
        }
        if arr.len() > TOOLS_CAP {
            return Err(format!("refused: more than {TOOLS_CAP} tools"));
        }
        let mut seen: Vec<String> = Vec::with_capacity(arr.len());
        for item in arr {
            let s = item
                .as_str()
                .ok_or_else(|| "refused: every tool must be a string".to_string())?
                .trim()
                .to_string();
            if s.is_empty()
                || s.len() > SLUG_CAP
                || !s.chars().all(|c| {
                    c.is_ascii_alphanumeric() || c == '_' || c == '-' || c == '.' || c == ':'
                })
            {
                return Err(format!("refused: `{s}` is not a tool name"));
            }
            // Order is the caller's, so a duplicate is dropped rather than
            // sorted away - and nothing is ever ADDED that was not sent.
            if !seen.contains(&s) {
                seen.push(s);
            }
        }
        out.insert("tools".into(), Value::Array(seen.into_iter().map(Value::String).collect()));
    }
    if out.is_empty() {
        return Err(format!(
            "nothing to change - send at least one of {}",
            WRITABLE.join(", ")
        ));
    }
    Ok(out)
}

/// Read, edit and atomically replace one agent file. Returns the message the
/// page shows verbatim.
pub fn write_agent(root: &Path, name: &str, body: &Value) -> Result<String, String> {
    let changes = changes_from_request(body)?;
    let path = resolve_agent(root, name)?;
    let text = fs::read_to_string(&path).map_err(|e| format!("could not read {name}.md: {e}"))?;
    if text.len() > AGENT_CAP {
        return Err(format!("refused: {name}.md is larger than the {AGENT_CAP}-byte cap"));
    }
    let out = apply_frontmatter(&text, &changes)?;
    if out == text {
        return Ok(format!("no change - {name}.md already reads that way"));
    }
    crate::toggle::atomic_write(&path, &out).map_err(|e| format!("write failed: {e}"))?;
    let mut wrote: Vec<&str> = changes.keys().map(|k| k.as_str()).collect();
    wrote.sort();
    Ok(format!("wrote {} in .claude/agents/{name}.md", wrote.join(", ")))
}

// ---------------------------------------------------------------------------
// the reference: seed, overlay, merge
// ---------------------------------------------------------------------------

/// Where a repository's own corrections live. Built entirely from the root -
/// no part of it comes from a request - so there is no path to contain.
pub fn overrides_path(root: &Path) -> PathBuf {
    root.join(".claude").join("state").join("references.json")
}

/// The overlay as stored, or an empty one. A corrupt file reads as empty rather
/// than failing the whole page: the seed is still useful, and the alternative is
/// a viewer that cannot show a reference because someone hand-edited a comma.
pub fn load_overrides(root: &Path) -> Value {
    fs::read_to_string(overrides_path(root))
        .ok()
        .and_then(|t| serde_json::from_str::<Value>(&t).ok())
        .filter(|v| v.is_object())
        .unwrap_or_else(|| json!({ "version": 1, "vendors": {} }))
}

fn obj(v: Option<&Value>) -> Map<String, Value> {
    v.and_then(|x| x.as_object()).cloned().unwrap_or_default()
}

fn is_removed(v: Option<&Value>) -> bool {
    v.and_then(|x| x.get("removed")).and_then(|x| x.as_bool()).unwrap_or(false)
}

/// Merge one keyed list (models by `id`, tools by `name`).
///
/// Seed order is kept, because it is a researched order (most capable first for
/// models, grouped by category for tools) and alphabetizing it would throw that
/// away. Entries the user added come after, sorted, so the response is
/// deterministic.
///
/// `verified` on a seed entry is taken from the SEED, always. An overlay that
/// carries one is not honoured and not an error - see the module header.
fn merge_list(
    seed_arr: &[Value],
    ov: &Map<String, Value>,
    key: &str,
    fields: &[&str],
) -> Vec<Value> {
    let mut out: Vec<Value> = Vec::with_capacity(seed_arr.len());
    let mut used: Vec<String> = Vec::new();
    for entry in seed_arr {
        let Some(id) = entry.get(key).and_then(|x| x.as_str()) else { continue };
        used.push(id.to_string());
        let o = ov.get(id);
        if is_removed(o) {
            continue;
        }
        let mut m = obj(Some(entry));
        let mut edited = false;
        if let Some(o) = o.and_then(|x| x.as_object()) {
            for f in fields {
                if let Some(nv) = o.get(*f) {
                    if m.get(*f) != Some(nv) {
                        edited = true;
                    }
                    m.insert((*f).to_string(), nv.clone());
                }
            }
        }
        // Restated rather than assumed: whatever the overlay said, the seed's
        // flag is the one that ships.
        m.insert(
            "verified".into(),
            entry.get("verified").cloned().unwrap_or(Value::Bool(false)),
        );
        if edited {
            m.insert("edited".into(), Value::Bool(true));
        }
        out.push(Value::Object(m));
    }
    let mut extra: Vec<&String> = ov.keys().filter(|k| !used.contains(k)).collect();
    extra.sort();
    for id in extra {
        let o = obj(ov.get(id));
        if is_removed(ov.get(id)) {
            continue;
        }
        let mut m = Map::new();
        m.insert(key.to_string(), Value::String(id.clone()));
        for f in fields {
            m.insert(
                (*f).to_string(),
                o.get(*f).cloned().unwrap_or_else(|| Value::String(String::new())),
            );
        }
        // A user-added entry carries the claim the user made, and `custom: true`
        // so nothing can mistake it for something that was researched.
        m.insert(
            "verified".into(),
            Value::Bool(o.get("verified").and_then(|x| x.as_bool()).unwrap_or(false)),
        );
        m.insert("custom".into(), Value::Bool(true));
        out.push(Value::Object(m));
    }
    out
}

const VENDOR_FIELDS: [&str; 3] = ["label", "source", "notes"];
const MODEL_FIELDS: [&str; 2] = ["label", "note"];
const TOOL_FIELDS: [&str; 3] = ["desc", "category", "permission"];

fn merge_vendor(id: &str, seed: Option<&Value>, ov: Option<&Value>) -> Value {
    let s = obj(seed);
    let o = obj(ov);
    let mut m = Map::new();
    m.insert("id".into(), Value::String(id.to_string()));
    let mut edited = false;
    for f in VENDOR_FIELDS {
        let v = match o.get(f) {
            Some(x) => {
                if s.get(f) != Some(x) && seed.is_some() {
                    edited = true;
                }
                x.clone()
            }
            None => s.get(f).cloned().unwrap_or_else(|| Value::String(String::new())),
        };
        m.insert(f.to_string(), v);
    }
    let efforts = match o.get("efforts") {
        Some(x) => {
            edited = seed.is_some() && s.get("efforts") != Some(x);
            x.clone()
        }
        None => s.get("efforts").cloned().unwrap_or_else(|| Value::Array(vec![])),
    };
    m.insert("efforts".into(), efforts);
    let seed_models = s.get("models").and_then(|x| x.as_array()).cloned().unwrap_or_default();
    let seed_tools = s.get("tools").and_then(|x| x.as_array()).cloned().unwrap_or_default();
    m.insert(
        "models".into(),
        Value::Array(merge_list(&seed_models, &obj(o.get("models")), "id", &MODEL_FIELDS)),
    );
    m.insert(
        "tools".into(),
        Value::Array(merge_list(&seed_tools, &obj(o.get("tools")), "name", &TOOL_FIELDS)),
    );
    if seed.is_none() {
        m.insert("custom".into(), Value::Bool(true));
    } else if edited {
        m.insert("edited".into(), Value::Bool(true));
    }
    Value::Object(m)
}

/// The seed, as parsed. A broken seed is a build problem, not a runtime one, so
/// it surfaces as an error rather than an empty reference that looks like a
/// vendor list nobody filled in.
pub fn seed_value() -> Result<Value, String> {
    serde_json::from_str(SEED).map_err(|e| format!("the shipped reference is not valid JSON: {e}"))
}

/// The reference the pickers are built from: the seed with this repository's
/// overlay applied.
pub fn merged(root: &Path) -> Result<Value, String> {
    let seed = seed_value()?;
    let ov = load_overrides(root);
    let seed_vendors = obj(seed.get("vendors"));
    let ov_vendors = obj(ov.get("vendors"));
    let mut vendors = Map::new();
    for (id, sv) in seed_vendors.iter() {
        let o = ov_vendors.get(id);
        if is_removed(o) {
            continue;
        }
        vendors.insert(id.clone(), merge_vendor(id, Some(sv), o));
    }
    let mut extra: Vec<&String> = ov_vendors.keys().filter(|k| !seed_vendors.contains_key(*k)).collect();
    extra.sort();
    for id in extra {
        if is_removed(ov_vendors.get(id)) {
            continue;
        }
        vendors.insert(id.clone(), merge_vendor(id, None, ov_vendors.get(id)));
    }
    Ok(json!({
        "version": seed.get("version").cloned().unwrap_or(json!(1)),
        "comment": seed.get("comment").cloned().unwrap_or(Value::String(String::new())),
        "overrides": overrides_path(root).exists(),
        "vendors": vendors,
    }))
}

// ---------------------------------------------------------------------------
// the reference: CRUD on the overlay
// ---------------------------------------------------------------------------

fn check_id(kind: &str, v: &str) -> Result<String, String> {
    let t = v.trim();
    if t.is_empty() {
        return Err(format!("refused: a {kind} needs an id"));
    }
    if t.len() > SLUG_CAP {
        return Err(format!("refused: that {kind} id is longer than {SLUG_CAP} characters"));
    }
    if !t
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_' || c == '.' || c == ':')
    {
        return Err(format!(
            "refused: `{v}` is not a {kind} id (letters, digits, dash, underscore, dot, colon)"
        ));
    }
    Ok(t.to_string())
}

fn check_text(field: &str, v: &Value) -> Result<Value, String> {
    let s = v
        .as_str()
        .ok_or_else(|| format!("refused: `{field}` must be a string"))?;
    let s = s.replace(['\r', '\n', '\t'], " ");
    if s.len() > 2_000 {
        return Err(format!("refused: `{field}` is longer than 2000 characters"));
    }
    Ok(Value::String(s.trim().to_string()))
}

/// Canonical form: sorted keys at every depth, indent 2, trailing newline. No
/// timestamp, no counter, nothing that changes when the content did not.
fn canonical(v: &Value) -> String {
    let mut s = serde_json::to_string_pretty(&scan::sort_keys_deep(v)).unwrap_or_else(|_| "{}".into());
    s.push('\n');
    s
}

/// Apply one add / edit / delete to the overlay and store it.
///
/// The shape is `{ op: "upsert"|"delete", kind: "vendor"|"model"|"tool",
/// vendor: <id>, id: <model id or tool name>, entry: { ...fields } }`. A delete
/// of a SEED entry is recorded as a tombstone (`{"removed": true}`) because the
/// seed will still be there after an upgrade and the user's decision has to
/// outlive it; a delete of an entry the user added just drops it, leaving no
/// tombstone for something that was never in the seed.
pub fn write_override(root: &Path, body: &Value) -> Result<String, String> {
    let op = body.get("op").and_then(|x| x.as_str()).unwrap_or("");
    let kind = body.get("kind").and_then(|x| x.as_str()).unwrap_or("");
    if !matches!(op, "upsert" | "delete") {
        return Err("refused: `op` must be \"upsert\" or \"delete\"".into());
    }
    if !matches!(kind, "vendor" | "model" | "tool") {
        return Err("refused: `kind` must be \"vendor\", \"model\" or \"tool\"".into());
    }
    let seed = seed_value()?;
    let seed_vendors = obj(seed.get("vendors"));

    let mut store = load_overrides(root);
    if !store.is_object() {
        store = json!({ "version": 1, "vendors": {} });
    }
    let mut vendors = obj(store.get("vendors"));

    let entry = body.get("entry").cloned().unwrap_or(json!({}));
    let vendor_id = if kind == "vendor" && op == "upsert" {
        check_id("vendor", entry.get("id").and_then(|x| x.as_str()).unwrap_or(""))?
    } else {
        check_id("vendor", body.get("vendor").and_then(|x| x.as_str()).unwrap_or(""))?
    };
    let in_seed = seed_vendors.contains_key(&vendor_id);
    let mut vendor = obj(vendors.get(&vendor_id));

    let msg = match (kind, op) {
        ("vendor", "upsert") => {
            vendor.remove("removed");
            for f in VENDOR_FIELDS {
                if let Some(v) = entry.get(f) {
                    vendor.insert(f.to_string(), check_text(f, v)?);
                }
            }
            if let Some(v) = entry.get("efforts") {
                let arr = v
                    .as_array()
                    .ok_or_else(|| "refused: `efforts` must be a list of strings".to_string())?;
                let mut out = Vec::new();
                for e in arr {
                    out.push(Value::String(check_id(
                        "effort",
                        e.as_str().unwrap_or_default(),
                    )?));
                }
                vendor.insert("efforts".into(), Value::Array(out));
            }
            format!("saved vendor `{vendor_id}`")
        }
        ("vendor", _) => {
            if in_seed {
                vendor.clear();
                vendor.insert("removed".into(), Value::Bool(true));
                format!("hid vendor `{vendor_id}` (a shipped vendor; re-add it to bring it back)")
            } else {
                vendor.clear();
                format!("removed vendor `{vendor_id}`")
            }
        }
        (k, o) => {
            let (bucket, id_field, fields) = if k == "model" {
                ("models", "id", &MODEL_FIELDS[..])
            } else {
                ("tools", "name", &TOOL_FIELDS[..])
            };
            let id = if o == "upsert" {
                check_id(k, entry.get(id_field).and_then(|x| x.as_str()).unwrap_or(""))?
            } else {
                check_id(k, body.get("id").and_then(|x| x.as_str()).unwrap_or(""))?
            };
            let seed_list = seed_vendors
                .get(&vendor_id)
                .and_then(|v| v.get(bucket))
                .and_then(|x| x.as_array())
                .cloned()
                .unwrap_or_default();
            let in_seed_list = seed_list
                .iter()
                .any(|e| e.get(id_field).and_then(|x| x.as_str()) == Some(id.as_str()));
            let mut list = obj(vendor.get(bucket));
            if o == "upsert" {
                let mut m = Map::new();
                for f in fields {
                    if let Some(v) = entry.get(*f) {
                        m.insert((*f).to_string(), check_text(f, v)?);
                    }
                }
                if !in_seed_list {
                    // Only an entry the USER is adding carries a verified claim.
                    // On a seed entry the flag belongs to the seed, so it is not
                    // stored here at all - it cannot then be honoured by mistake.
                    m.insert(
                        "verified".into(),
                        Value::Bool(entry.get("verified").and_then(|x| x.as_bool()).unwrap_or(false)),
                    );
                }
                list.insert(id.clone(), Value::Object(m));
            } else if in_seed_list {
                list.insert(id.clone(), json!({ "removed": true }));
            } else {
                list.remove(&id);
            }
            if list.is_empty() {
                vendor.remove(bucket);
            } else {
                vendor.insert(bucket.to_string(), Value::Object(list));
            }
            let verb = if o == "upsert" { "saved" } else { "removed" };
            format!("{verb} {k} `{id}` in `{vendor_id}`")
        }
    };

    if vendor.is_empty() {
        vendors.remove(&vendor_id);
    } else {
        vendors.insert(vendor_id.clone(), Value::Object(vendor));
    }

    let path = overrides_path(root);
    if vendors.is_empty() {
        // Nothing left to say. Leaving an empty overlay behind would be a file
        // that means the same as no file, and this repository does not commit
        // state that carries no information.
        if path.exists() {
            fs::remove_file(&path).map_err(|e| format!("could not clear the overrides: {e}"))?;
        }
        return Ok(format!("{msg} - no local overrides left, .claude/state/references.json removed"));
    }
    let out = canonical(&json!({ "version": 1, "vendors": vendors }));
    if let Some(dir) = path.parent() {
        fs::create_dir_all(dir).map_err(|e| format!("could not create .claude/state: {e}"))?;
    }
    crate::toggle::atomic_write(&path, &out).map_err(|e| format!("write failed: {e}"))?;
    Ok(format!("{msg} - saved to .claude/state/references.json"))
}
