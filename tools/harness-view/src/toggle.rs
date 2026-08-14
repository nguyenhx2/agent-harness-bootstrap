//! Runtime enable/disable for rules, commands and hooks, sharing one contract
//! with the harness's own /harness-toggle command:
//!   - rules/commands move between .claude/<kind>s/X.md and .claude/disabled/<kind>s/X.md
//!   - hooks additionally have their settings.json registration objects removed
//!     and stored verbatim (with position) in .claude/disabled.json, so enabling
//!     restores the registration exactly where it was
//!   - .claude/disabled.json is the committed record; atomic writes, sorted
//!     keys, trailing newline, never a timestamp
//! Agents are never toggleable. HARD-protected items are refused here entirely;
//! the /harness-toggle command is the only path for those (typed confirmation).

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

fn canon_kind(kind: &str) -> Option<&'static str> {
    match kind {
        "rule" | "rules" => Some("rule"),
        "command" | "commands" => Some("command"),
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

fn atomic_write(path: &Path, content: &str) -> std::io::Result<()> {
    let tmp = path.with_extension("tmp-write");
    fs::write(&tmp, content)?;
    if path.exists() {
        fs::remove_file(path)?;
    }
    fs::rename(&tmp, path)
}

fn canonical(v: &Value) -> String {
    let mut s = serde_json::to_string_pretty(v).unwrap_or_else(|_| "{}".into());
    s.push('\n');
    s
}

fn load_disabled(root: &Path) -> Value {
    let p = root.join(".claude").join("disabled.json");
    fs::read_to_string(&p)
        .ok()
        .and_then(|t| serde_json::from_str(&t).ok())
        .unwrap_or_else(|| json!({"version": 1, "disabled": []}))
}

fn save_disabled(root: &Path, v: &Value) -> Result<(), ToggleError> {
    let p = root.join(".claude").join("disabled.json");
    atomic_write(&p, &canonical(v)).map_err(|e| err(500, format!("write disabled.json: {e}")))
}

fn move_file(from: &Path, to: &Path) -> Result<(), ToggleError> {
    if let Some(parent) = to.parent() {
        fs::create_dir_all(parent).map_err(|e| err(500, format!("mkdir: {e}")))?;
    }
    fs::rename(from, to).map_err(|e| err(500, format!("move {from:?} -> {to:?}: {e}")))
}

/// Strip a hook's registration objects out of settings.json. Returns the
/// removed registrations as [{event, matcher, index, hook}] with the group
/// index recorded so enable can reinsert at the original position.
fn strip_registration(settings: &mut Value, hook_name: &str) -> Vec<Value> {
    let mut removed = Vec::new();
    let needle = format!("hooks/{hook_name}.");
    let Some(events) = settings.get_mut("hooks").and_then(|h| h.as_object_mut()) else {
        return removed;
    };
    let mut empty_events = Vec::new();
    for (event, arr) in events.iter_mut() {
        let Some(groups) = arr.as_array_mut() else { continue };
        let mut kept_groups = Vec::new();
        for (gi, group) in groups.drain(..).enumerate() {
            let matcher = group
                .get("matcher")
                .and_then(|m| m.as_str())
                .unwrap_or("*")
                .to_string();
            let mut g = group.clone();
            let mut hit = false;
            if let Some(hooks) = g.get_mut("hooks").and_then(|x| x.as_array_mut()) {
                let mut kept = Vec::new();
                for h in hooks.drain(..) {
                    let cmd = h
                        .get("command")
                        .and_then(|c| c.as_str())
                        .unwrap_or("")
                        .replace('\\', "/");
                    if cmd.contains(&needle) {
                        removed.push(json!({
                            "event": event, "matcher": matcher, "index": gi, "hook": h
                        }));
                        hit = true;
                    } else {
                        kept.push(h);
                    }
                }
                *g.get_mut("hooks").unwrap() = Value::Array(kept);
            }
            let empty = g
                .get("hooks")
                .and_then(|x| x.as_array())
                .map(|a| a.is_empty())
                .unwrap_or(true);
            if hit && empty {
                // drop the emptied group; its position is recorded in `index`
            } else {
                kept_groups.push(g);
            }
        }
        if kept_groups.is_empty() {
            empty_events.push(event.clone());
        } else {
            *arr = Value::Array(kept_groups);
        }
    }
    for e in empty_events {
        events.remove(&e);
    }
    removed
}

/// Reinsert stored registrations, recreating groups (at their recorded index)
/// and event keys as needed.
fn restore_registration(settings: &mut Value, regs: &[Value]) {
    if settings.get("hooks").is_none() {
        settings["hooks"] = json!({});
    }
    let Some(events) = settings.get_mut("hooks").and_then(|h| h.as_object_mut()) else {
        return;
    };
    for reg in regs {
        let event = reg.get("event").and_then(|e| e.as_str()).unwrap_or("PostToolUse");
        let matcher = reg.get("matcher").and_then(|m| m.as_str()).unwrap_or("*");
        let index = reg.get("index").and_then(|i| i.as_u64()).unwrap_or(0) as usize;
        let hook = reg.get("hook").cloned().unwrap_or(Value::Null);
        let arr = events
            .entry(event.to_string())
            .or_insert_with(|| Value::Array(Vec::new()));
        let Some(groups) = arr.as_array_mut() else { continue };
        let pos = groups.iter().position(|g| {
            g.get("matcher").and_then(|m| m.as_str()).unwrap_or("*") == matcher
        });
        match pos {
            Some(i) => {
                if let Some(hooks) = groups[i].get_mut("hooks").and_then(|x| x.as_array_mut()) {
                    hooks.push(hook);
                }
            }
            None => {
                let group = json!({"matcher": matcher, "hooks": [hook]});
                let at = index.min(groups.len());
                groups.insert(at, group);
            }
        }
    }
}

pub fn toggle(
    root: &Path,
    kind: &str,
    name: &str,
    enable: bool,
    reason: &str,
) -> Result<String, ToggleError> {
    let kind = canon_kind(kind).ok_or_else(|| {
        err(400, "kind must be rule, command or hook; agents are roster changes, not toggles")
    })?;
    if name.contains('/') || name.contains('\\') || name.contains("..") {
        return Err(err(400, "invalid name"));
    }
    if !enable {
        // enabling something is always allowed; disabling protected items is not
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
    }

    let sub = kind_dir(kind);
    let mut disabled_doc = load_disabled(root);

    if !enable {
        let list = disabled_doc["disabled"].as_array().cloned().unwrap_or_default();
        if list.iter().any(|e| {
            e.get("kind").and_then(|k| k.as_str()) == Some(kind)
                && e.get("name").and_then(|n| n.as_str()) == Some(name)
        }) {
            return Err(err(409, format!("{kind}/{name} is already disabled")));
        }
        let mut entry = Map::new();
        entry.insert("kind".into(), json!(kind));
        entry.insert("name".into(), json!(name));
        entry.insert("reason".into(), json!(reason));
        if kind == "hook" {
            let mut moved = false;
            for ext in ["sh", "ps1"] {
                let from = root.join(".claude").join(sub).join(format!("{name}.{ext}"));
                if from.is_file() {
                    let to = root
                        .join(".claude")
                        .join("disabled")
                        .join(sub)
                        .join(format!("{name}.{ext}"));
                    move_file(&from, &to)?;
                    moved = true;
                }
            }
            if !moved {
                return Err(err(404, format!("no hook file found for {name}")));
            }
            entry.insert("from".into(), json!(format!(".claude/hooks/{name}.sh")));
            let sp = root.join(".claude").join("settings.json");
            if sp.is_file() {
                let txt = fs::read_to_string(&sp).map_err(|e| err(500, e.to_string()))?;
                if let Ok(mut settings) = serde_json::from_str::<Value>(&txt) {
                    let regs = strip_registration(&mut settings, name);
                    entry.insert("registration".into(), Value::Array(regs));
                    atomic_write(&sp, &canonical(&settings))
                        .map_err(|e| err(500, e.to_string()))?;
                }
            }
        } else {
            let from = root.join(".claude").join(sub).join(format!("{name}.md"));
            if !from.is_file() {
                return Err(err(404, format!("{} does not exist", from.display())));
            }
            let to = root
                .join(".claude")
                .join("disabled")
                .join(sub)
                .join(format!("{name}.md"));
            move_file(&from, &to)?;
            entry.insert("from".into(), json!(format!(".claude/{sub}/{name}.md")));
        }
        let arr = disabled_doc["disabled"].as_array_mut().unwrap();
        arr.push(Value::Object(entry));
        arr.sort_by(|a, b| {
            let ka = format!(
                "{}/{}",
                a.get("kind").and_then(|k| k.as_str()).unwrap_or(""),
                a.get("name").and_then(|n| n.as_str()).unwrap_or("")
            );
            let kb = format!(
                "{}/{}",
                b.get("kind").and_then(|k| k.as_str()).unwrap_or(""),
                b.get("name").and_then(|n| n.as_str()).unwrap_or("")
            );
            ka.cmp(&kb)
        });
        save_disabled(root, &disabled_doc)?;
        Ok(format!("disabled {kind}/{name}"))
    } else {
        let arr = disabled_doc["disabled"].as_array().cloned().unwrap_or_default();
        let idx = arr
            .iter()
            .position(|e| {
                e.get("kind").and_then(|k| k.as_str()) == Some(kind)
                    && e.get("name").and_then(|n| n.as_str()) == Some(name)
            })
            .ok_or_else(|| err(404, format!("{kind}/{name} is not in .claude/disabled.json")))?;
        let entry = arr[idx].clone();
        if kind == "hook" {
            for ext in ["sh", "ps1"] {
                let from = root
                    .join(".claude")
                    .join("disabled")
                    .join(sub)
                    .join(format!("{name}.{ext}"));
                if from.is_file() {
                    let to = root.join(".claude").join(sub).join(format!("{name}.{ext}"));
                    move_file(&from, &to)?;
                }
            }
            let regs = entry
                .get("registration")
                .and_then(|r| r.as_array())
                .cloned()
                .unwrap_or_default();
            let sp = root.join(".claude").join("settings.json");
            if sp.is_file() && !regs.is_empty() {
                let txt = fs::read_to_string(&sp).map_err(|e| err(500, e.to_string()))?;
                if let Ok(mut settings) = serde_json::from_str::<Value>(&txt) {
                    restore_registration(&mut settings, &regs);
                    atomic_write(&sp, &canonical(&settings))
                        .map_err(|e| err(500, e.to_string()))?;
                }
            }
        } else {
            let from = root
                .join(".claude")
                .join("disabled")
                .join(sub)
                .join(format!("{name}.md"));
            if !from.is_file() {
                return Err(err(404, format!("{} does not exist", from.display())));
            }
            let to = root.join(".claude").join(sub).join(format!("{name}.md"));
            move_file(&from, &to)?;
        }
        let list = disabled_doc["disabled"].as_array_mut().unwrap();
        list.remove(idx);
        save_disabled(root, &disabled_doc)?;
        Ok(format!("enabled {kind}/{name}"))
    }
}

/// Rewrite settings.json in the same canonical form toggling uses, so a later
/// disable/enable round trip is byte-exact. Used by tests and available to
/// callers that want a stable baseline.
pub fn canonicalize_settings(root: &Path) -> std::io::Result<()> {
    let sp: PathBuf = root.join(".claude").join("settings.json");
    if sp.is_file() {
        let txt = fs::read_to_string(&sp)?;
        if let Ok(v) = serde_json::from_str::<Value>(&txt) {
            let mut s = serde_json::to_string_pretty(&v)?;
            s.push('\n');
            fs::write(&sp, s)?;
        }
    }
    Ok(())
}
