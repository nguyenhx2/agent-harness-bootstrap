//! Runtime enable/disable for rules, commands and hooks, sharing one contract
//! with the harness's own harness-toggle.py (the reference implementation):
//!   - rules/commands move between .claude/<kind>s/X.md and .claude/disabled/<kind>s/X.md
//!   - hooks additionally have their settings.json registration objects removed
//!     and stored verbatim (with event/matcher/group_index/hook_index) in
//!     .claude/disabled.json, so enabling restores them exactly where they were
//!   - .claude/disabled.json is the committed record; atomic writes, sorted
//!     keys, trailing newline, never a timestamp
//!   - settings.json is rewritten with indent 2 PRESERVING key order (order is
//!     semantic there); disabled.json is the only file written with sorted keys
//! Safety tiers match harness-toggle.py:
//!   HARD  - refused here entirely (403); only /harness-toggle with the typed
//!           user phrase may disable them
//!   SOFT  - refused (409) unless the caller passes an explicit acknowledgement
//! Agents are never toggleable.

use crate::scan::sort_keys_deep;
use serde_json::{json, Map, Value};
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug)]
pub struct ToggleError {
    pub code: u16,
    pub msg: String,
}

fn err(code: u16, msg: impl Into<String>) -> ToggleError {
    ToggleError { code, msg: msg.into() }
}

const HARD: &[(&str, &str)] = &[
    ("hook", "protect-secrets"),
    ("hook", "guard-agent-spawn"),
    ("rule", "security-privacy"),
    ("rule", "agent-guardrails"),
    ("command", "review-changes"),
];

/// SOFT-protected items and what each one protects, mirroring
/// harness-toggle.py's SOFT set (which requires --yes).
const SOFT: &[(&str, &str, &str)] = &[
    ("hook", "guard-main-commit", "blocks direct commits to the default branch"),
    ("hook", "check-commit-msg", "enforces the conventional-commit contract"),
    ("hook", "protect-adr", "protects accepted ADRs from silent edits"),
    ("rule", "ai-governance", "carries the AI-governance ground rules"),
];

fn canon_kind(kind: &str) -> Option<&'static str> {
    match kind {
        "rule" | "rules" => Some("rule"),
        "command" | "commands" | "cmd" => Some("command"),
        "hook" | "hooks" => Some("hook"),
        _ => None,
    }
}

fn kind_dir(kind: &str) -> &'static str {
    match kind {
        "rule" => "rules",
        "command" => "commands",
        _ => "hooks",
    }
}

/// Atomic replace: write a temp file then rename over the target. fs::rename
/// replaces the destination on both Windows and Unix, so the target never
/// stops existing.
fn atomic_write(path: &Path, content: &str) -> std::io::Result<()> {
    let tmp = path.with_extension("tmp-write");
    fs::write(&tmp, content)?;
    fs::rename(&tmp, path)
}

/// Canonical form for disabled.json: sorted keys at every depth, indent 2,
/// trailing newline.
fn canonical_sorted(v: &Value) -> String {
    let mut s = serde_json::to_string_pretty(&sort_keys_deep(v)).unwrap_or_else(|_| "{}".into());
    s.push('\n');
    s
}

/// Canonical form for settings.json: indent 2, trailing newline, key order
/// preserved (NOT sorted - order is semantic there).
fn pretty_preserve(v: &Value) -> String {
    let mut s = serde_json::to_string_pretty(v).unwrap_or_else(|_| "{}".into());
    s.push('\n');
    s
}

fn load_disabled(root: &Path) -> Vec<Value> {
    let p = root.join(".claude").join("disabled.json");
    let entries = fs::read_to_string(&p)
        .ok()
        .and_then(|t| serde_json::from_str::<Value>(&t).ok())
        .and_then(|v| v.get("disabled").and_then(|d| d.as_array()).cloned())
        .unwrap_or_default();
    entries
        .into_iter()
        .filter(|e| {
            e.get("kind").and_then(|k| k.as_str()).is_some()
                && e.get("name").and_then(|n| n.as_str()).is_some()
        })
        .collect()
}

fn save_disabled(root: &Path, mut entries: Vec<Value>) -> Result<(), ToggleError> {
    entries.sort_by_key(|e| {
        format!(
            "{}/{}",
            e.get("kind").and_then(|k| k.as_str()).unwrap_or(""),
            e.get("name").and_then(|n| n.as_str()).unwrap_or("")
        )
    });
    let doc = json!({"disabled": entries, "version": 1});
    let p = root.join(".claude").join("disabled.json");
    atomic_write(&p, &canonical_sorted(&doc))
        .map_err(|e| err(500, format!("write disabled.json: {e}")))
}

fn move_file(from: &Path, to: &Path) -> Result<(), ToggleError> {
    if let Some(parent) = to.parent() {
        fs::create_dir_all(parent).map_err(|e| err(500, format!("mkdir: {e}")))?;
    }
    fs::rename(from, to).map_err(|e| err(500, format!("move {from:?} -> {to:?}: {e}")))
}

/// Files belonging to an item on the given side, in harness-toggle.py's order:
/// for hooks the .sh flavor first, then .ps1; only files that exist.
fn item_files(root: &Path, kind: &str, name: &str, disabled: bool) -> Vec<PathBuf> {
    let sub = kind_dir(kind);
    let base = if disabled {
        root.join(".claude").join("disabled").join(sub)
    } else {
        root.join(".claude").join(sub)
    };
    if kind == "hook" {
        ["sh", "ps1"]
            .iter()
            .map(|ext| base.join(format!("{name}.{ext}")))
            .filter(|p| p.is_file())
            .collect()
    } else {
        let p = base.join(format!("{name}.md"));
        if p.is_file() {
            vec![p]
        } else {
            Vec::new()
        }
    }
}

/// Remove every hook object whose command references hooks/<name>. and return
/// the removed objects with their coordinates, matching harness-toggle.py:
/// [{event, matcher, group_index, hook_index, hook}]. Groups left without
/// hooks are dropped; event keys are kept even when their group list empties.
fn strip_registration(settings: &mut Value, hook_name: &str) -> Vec<Value> {
    let mut removed = Vec::new();
    let needle = format!("hooks/{hook_name}.");
    let Some(events) = settings.get_mut("hooks").and_then(|h| h.as_object_mut()) else {
        return removed;
    };
    for (event, arr) in events.iter_mut() {
        let Some(groups) = arr.as_array_mut() else { continue };
        for (gi, group) in groups.iter_mut().enumerate() {
            let Some(g) = group.as_object_mut() else { continue };
            let matcher = g
                .get("matcher")
                .and_then(|m| m.as_str())
                .unwrap_or("*")
                .to_string();
            let hooks_in = g
                .get("hooks")
                .and_then(|x| x.as_array())
                .cloned()
                .unwrap_or_default();
            let mut kept = Vec::new();
            for (hi, h) in hooks_in.into_iter().enumerate() {
                let cmd = h
                    .get("command")
                    .and_then(|c| c.as_str())
                    .unwrap_or("")
                    .replace('\\', "/");
                if cmd.contains(&needle) {
                    removed.push(json!({
                        "event": event, "matcher": matcher,
                        "group_index": gi, "hook_index": hi, "hook": h
                    }));
                } else {
                    kept.push(h);
                }
            }
            g.insert("hooks".into(), Value::Array(kept));
        }
        // drop groups with no hooks left; keep the event key itself
        let filtered: Vec<Value> = groups
            .iter()
            .filter(|g| {
                !g.is_object()
                    || g.get("hooks")
                        .and_then(|x| x.as_array())
                        .map(|a| !a.is_empty())
                        .unwrap_or(false)
            })
            .cloned()
            .collect();
        *arr = Value::Array(filtered);
    }
    removed
}

/// Reinsert stored registrations at their recorded positions, matching
/// harness-toggle.py: the group is found by matcher (created at group_index if
/// missing) and the hook object is inserted at hook_index.
fn restore_registration(settings: &mut Value, regs: &[Value]) {
    if !settings.get("hooks").map(|h| h.is_object()).unwrap_or(false) {
        settings["hooks"] = json!({});
    }
    let Some(events) = settings.get_mut("hooks").and_then(|h| h.as_object_mut()) else {
        return;
    };
    for reg in regs {
        let event = reg.get("event").and_then(|e| e.as_str()).unwrap_or("PostToolUse");
        let matcher = reg.get("matcher").and_then(|m| m.as_str()).unwrap_or("*");
        let group_index = reg.get("group_index").and_then(|i| i.as_u64()).unwrap_or(0) as usize;
        let hook_index = reg.get("hook_index").and_then(|i| i.as_u64()).unwrap_or(u64::MAX) as usize;
        let hook = reg.get("hook").cloned().unwrap_or(Value::Null);
        let arr = events
            .entry(event.to_string())
            .or_insert_with(|| Value::Array(Vec::new()));
        let Some(groups) = arr.as_array_mut() else { continue };
        let pos = groups.iter().position(|g| {
            g.get("matcher").and_then(|m| m.as_str()).unwrap_or("*") == matcher
        });
        let gi = match pos {
            Some(i) => i,
            None => {
                let group = json!({"matcher": matcher, "hooks": []});
                let at = group_index.min(groups.len());
                groups.insert(at, group);
                at
            }
        };
        if let Some(hooks) = groups[gi].get_mut("hooks").and_then(|x| x.as_array_mut()) {
            let at = hook_index.min(hooks.len());
            hooks.insert(at, hook);
        } else if let Some(g) = groups[gi].as_object_mut() {
            g.insert("hooks".into(), json!([hook]));
        }
    }
}

fn load_settings(root: &Path) -> Option<Value> {
    let sp = root.join(".claude").join("settings.json");
    fs::read_to_string(&sp)
        .ok()
        .and_then(|t| serde_json::from_str(&t).ok())
}

fn write_settings(root: &Path, settings: &Value) -> Result<(), ToggleError> {
    let sp = root.join(".claude").join("settings.json");
    atomic_write(&sp, &pretty_preserve(settings))
        .map_err(|e| err(500, format!("write settings.json: {e}")))
}

/// Toggle one item. `confirm_soft` is the explicit acknowledgement required to
/// disable a SOFT-protected item (harness-toggle.py's --yes).
pub fn toggle(
    root: &Path,
    kind: &str,
    name: &str,
    enable: bool,
    reason: &str,
    confirm_soft: bool,
) -> Result<String, ToggleError> {
    let kind = canon_kind(kind).ok_or_else(|| {
        err(400, "kind must be rule, command or hook; agents are roster changes, not toggles")
    })?;
    if name.is_empty() || name.contains('/') || name.contains('\\') || name.contains("..") {
        return Err(err(400, "invalid name"));
    }
    if !enable {
        if HARD.iter().any(|(k, n)| *k == kind && *n == name) {
            return Err(err(
                403,
                format!(
                    "{kind}/{name} is HARD-protected. Disabling it removes a safety control; \
                     use the /harness-toggle command, which requires the user to type the \
                     confirmation phrase."
                ),
            ));
        }
        if let Some((_, _, protects)) = SOFT.iter().find(|(k, n, _)| *k == kind && *n == name) {
            if !confirm_soft {
                return Err(err(
                    409,
                    format!(
                        "{kind}/{name} is a protected control - it {protects}. \
                         Confirm the user asked for this (confirm_soft) to proceed."
                    ),
                ));
            }
        }
    }

    if enable {
        do_enable(root, kind, name)
    } else {
        do_disable(root, kind, name, reason)
    }
}

fn do_disable(root: &Path, kind: &str, name: &str, reason: &str) -> Result<String, ToggleError> {
    let files = item_files(root, kind, name, false);
    if files.is_empty() {
        return Err(err(404, format!("no active {kind} named `{name}`")));
    }
    let entries = load_disabled(root);
    if entries.iter().any(|e| {
        e.get("kind").and_then(|k| k.as_str()) == Some(kind)
            && e.get("name").and_then(|n| n.as_str()) == Some(name)
    }) {
        return Err(err(
            409,
            format!("{kind}/{name} is already listed in disabled.json"),
        ));
    }

    let sub = kind_dir(kind);
    let mut entry = Map::new();
    entry.insert("kind".into(), json!(kind));
    entry.insert("name".into(), json!(name));
    // the file actually present, not an assumed flavor (correct on a
    // ps1-only harness)
    let first_name = files[0].file_name().and_then(|x| x.to_str()).unwrap_or(name);
    entry.insert("from".into(), json!(format!(".claude/{sub}/{first_name}")));
    entry.insert("reason".into(), json!(reason));

    // settings first, then files: a mid-operation failure must never leave a
    // quarantined hook still registered (harness-toggle.py's order)
    let mut removed_count = 0usize;
    if kind == "hook" {
        if let Some(mut settings) = load_settings(root) {
            let regs = strip_registration(&mut settings, name);
            if !regs.is_empty() {
                removed_count = regs.len();
                entry.insert("registration".into(), Value::Array(regs));
                write_settings(root, &settings)?;
            }
        }
    }

    let qdir = root.join(".claude").join("disabled").join(sub);
    for f in &files {
        let to = qdir.join(f.file_name().unwrap());
        move_file(f, &to)?;
    }
    let mut entries = entries;
    entries.push(Value::Object(entry));
    save_disabled(root, entries)?;
    Ok(if kind == "hook" {
        format!("disabled {kind}/{name} ({removed_count} registration(s) removed)")
    } else {
        format!("disabled {kind}/{name}")
    })
}

fn do_enable(root: &Path, kind: &str, name: &str) -> Result<String, ToggleError> {
    let entries = load_disabled(root);
    let idx = entries.iter().position(|e| {
        e.get("kind").and_then(|k| k.as_str()) == Some(kind)
            && e.get("name").and_then(|n| n.as_str()) == Some(name)
    });
    let files = item_files(root, kind, name, true);
    // filesystem fallback: a quarantined file with no disabled.json record is
    // still enabled (harness-toggle.py behaves the same)
    if idx.is_none() && files.is_empty() {
        return Err(err(404, format!("{kind}/{name} is not disabled")));
    }

    let adir = root.join(".claude").join(kind_dir(kind));
    fs::create_dir_all(&adir).map_err(|e| err(500, format!("mkdir: {e}")))?;
    for f in &files {
        let to = adir.join(f.file_name().unwrap());
        move_file(f, &to)?;
    }
    if kind == "hook" {
        if let Some(i) = idx {
            let regs = entries[i]
                .get("registration")
                .and_then(|r| r.as_array())
                .cloned()
                .unwrap_or_default();
            if !regs.is_empty() {
                if let Some(mut settings) = load_settings(root) {
                    restore_registration(&mut settings, &regs);
                    write_settings(root, &settings)?;
                }
            }
        }
    }
    if let Some(i) = idx {
        let mut entries = entries;
        entries.remove(i);
        save_disabled(root, entries)?;
    }
    Ok(format!("enabled {kind}/{name}"))
}

/// Rewrite settings.json in the same canonical form toggling uses (indent 2,
/// key order preserved, trailing newline), so a later disable/enable round
/// trip is byte-exact.
pub fn canonicalize_settings(root: &Path) -> std::io::Result<()> {
    let sp: PathBuf = root.join(".claude").join("settings.json");
    if sp.is_file() {
        let txt = fs::read_to_string(&sp)?;
        if let Ok(v) = serde_json::from_str::<Value>(&txt) {
            fs::write(&sp, pretty_preserve(&v))?;
        }
    }
    Ok(())
}
