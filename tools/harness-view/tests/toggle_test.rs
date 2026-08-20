use harness_view::{scan, toggle};
use std::fs;
use std::path::{Path, PathBuf};

fn fixture() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests").join("fixture")
}

/// Copy the fixture into a unique temp dir so tests never mutate the source.
fn temp_copy(tag: &str) -> PathBuf {
    let dst = std::env::temp_dir().join(format!("harness-view-test-{tag}-{}", std::process::id()));
    if dst.exists() {
        fs::remove_dir_all(&dst).unwrap();
    }
    copy_dir(&fixture(), &dst);
    dst
}

fn copy_dir(from: &Path, to: &Path) {
    fs::create_dir_all(to).unwrap();
    for e in fs::read_dir(from).unwrap().flatten() {
        let p = e.path();
        let t = to.join(e.file_name());
        if p.is_dir() {
            copy_dir(&p, &t);
        } else {
            fs::copy(&p, &t).unwrap();
        }
    }
}

#[test]
fn toggle_rule_round_trip() {
    let root = temp_copy("rule");
    toggle::toggle(&root, "rule", "testing", false, "test run", false, "").unwrap();
    assert!(!root.join(".claude/rules/testing.md").exists());
    assert!(root.join(".claude/disabled/rules/testing.md").exists());
    let g = scan::scan(&root);
    let node = g["nodes"]
        .as_array()
        .unwrap()
        .iter()
        .find(|n| n["id"] == "rule:testing")
        .expect("disabled rule still appears as a node");
    assert_eq!(node["disabled"], true);
    // a quarantined rule gates nothing
    assert!(!g["edges"].as_array().unwrap().iter().any(|e| {
        e["from"] == "rule:testing" && e["type"] == "gates"
    }));
    toggle::toggle(&root, "rule", "testing", true, "", false, "").unwrap();
    assert!(root.join(".claude/rules/testing.md").exists());
    assert!(!root.join(".claude/disabled/rules/testing.md").exists());
    let disabled: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(root.join(".claude/disabled.json")).unwrap())
            .unwrap();
    assert_eq!(disabled["disabled"].as_array().unwrap().len(), 0);
    fs::remove_dir_all(&root).unwrap();
}

#[test]
fn toggle_command_round_trip() {
    let root = temp_copy("cmd");
    toggle::toggle(&root, "command", "deploy", false, "manual deploys only", false, "").unwrap();
    assert!(!root.join(".claude/commands/deploy.md").exists());
    assert!(root.join(".claude/disabled/commands/deploy.md").exists());
    let g = scan::scan(&root);
    // a quarantined command is not user-invokable, but its wiring stays visible
    assert!(!g["edges"].as_array().unwrap().iter().any(|e| {
        e["to"] == "cmd:deploy" && e["type"] == "invokes"
    }));
    toggle::toggle(&root, "command", "deploy", true, "", false, "").unwrap();
    assert!(root.join(".claude/commands/deploy.md").exists());
    fs::remove_dir_all(&root).unwrap();
}

#[test]
fn toggle_hook_restores_settings_byte_exactly() {
    let root = temp_copy("hook");
    // canonical baseline first, so the round trip is byte-comparable
    toggle::canonicalize_settings(&root).unwrap();
    let before = fs::read_to_string(root.join(".claude/settings.json")).unwrap();
    // the fixture is hand-ordered: permissions before hooks, type before
    // command - canonicalization must PRESERVE that order, not sort it
    let perm_at = before.find("\"permissions\"").unwrap();
    let hooks_at = before.find("\"hooks\"").unwrap();
    assert!(perm_at < hooks_at, "settings.json key order must be preserved");

    // graph-stale is the FIRST of two hooks in its matcher group; restoring it
    // must put it back at position 0, not append it. Its own object is
    // key-sorted in the fixture because disabled.json is written with sorted
    // keys (same as harness-toggle.py), so that is the form that comes back.
    toggle::toggle(&root, "hook", "graph-stale", false, "noisy during refactor", false, "").unwrap();
    assert!(!root.join(".claude/hooks/graph-stale.sh").exists());
    assert!(root.join(".claude/disabled/hooks/graph-stale.sh").exists());
    let mid = fs::read_to_string(root.join(".claude/settings.json")).unwrap();
    assert!(!mid.contains("graph-stale"), "registration must be stripped");
    assert!(mid.contains("specs-reminder"), "other hooks in the group must survive");

    // the record carries the Python-compatible coordinates
    let disabled: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(root.join(".claude/disabled.json")).unwrap())
            .unwrap();
    let reg = &disabled["disabled"][0]["registration"][0];
    assert_eq!(reg["group_index"], 0);
    assert_eq!(reg["hook_index"], 0);
    assert!(reg.get("index").is_none(), "legacy `index` key must not be written");

    toggle::toggle(&root, "hook", "graph-stale", true, "", false, "").unwrap();
    assert!(root.join(".claude/hooks/graph-stale.sh").exists());
    let after = fs::read_to_string(root.join(".claude/settings.json")).unwrap();
    assert_eq!(before, after, "enable must restore settings.json byte-exactly");
    fs::remove_dir_all(&root).unwrap();
}

#[test]
fn hard_protected_items_refuse() {
    let root = temp_copy("hard");
    // every HARD item refuses with 403, whether or not its file exists in the
    // fixture (missing files must still refuse on the safety tier first)
    for (kind, name) in [
        ("hook", "protect-secrets"),
        ("hook", "guard-agent-spawn"),
        ("rule", "security-privacy"),
        ("rule", "agent-guardrails"),
        ("command", "review-changes"),
        // the seats the harness is built around are HARD too: only the
        // orchestrator spawns, and the review seats are the code-review gate
        ("agent", "orchestrator"),
        ("agent", "code-reviewer"),
    ] {
        let e = toggle::toggle(&root, kind, name, false, "", false, "").unwrap_err();
        assert_eq!(e.code, 403, "{kind}/{name} must refuse with 403");
        // a near miss is not the phrase: no trimming, no case folding
        for wrong in [
            format!("Disable {name}"),
            format!("disable {name} "),
            format!(" disable {name}"),
            "disable".to_string(),
            format!("disable {name}\n"),
        ] {
            let e = toggle::toggle(&root, kind, name, false, "", true, &wrong).unwrap_err();
            assert_eq!(e.code, 403, "{kind}/{name} accepted `{wrong}` as the phrase");
        }
    }
    assert!(root.join(".claude/hooks/protect-secrets.sh").exists());
    assert!(root.join(".claude/rules/agent-guardrails.md").exists());
    fs::remove_dir_all(&root).unwrap();
}

/// The phrase is the whole gate: with it, a HARD item moves like any other.
/// It still has to clear the SOFT tier as well where one applies, which is what
/// makes a HARD agent need both flags rather than either.
#[test]
fn the_exact_phrase_disables_a_hard_item() {
    let root = temp_copy("hardphrase");
    toggle::toggle(&root, "command", "review-changes", false, "rescoped",
                   false, "disable review-changes")
        .expect("the exact phrase must be accepted");
    assert!(root.join(".claude/disabled/commands/review-changes.md").exists());
    assert!(!root.join(".claude/commands/review-changes.md").exists());
    // re-enabling never needs a phrase: restoring a control is not the risk
    toggle::toggle(&root, "command", "review-changes", true, "", false, "").unwrap();
    assert!(root.join(".claude/commands/review-changes.md").exists());
    fs::remove_dir_all(&root).unwrap();
}

/// A roster seat parks and comes back like anything else. Every seat is at
/// least SOFT, because the orchestrator's routing table still names it.
#[test]
fn an_agent_seat_parks_and_returns() {
    let root = temp_copy("agenttoggle");
    let e = toggle::toggle(&root, "agent", "app-dev", false, "", false, "").unwrap_err();
    assert_eq!(e.code, 409, "every seat is at least SOFT");
    toggle::toggle(&root, "agent", "app-dev", false, "on hold", true, "").unwrap();
    assert!(root.join(".claude/disabled/agents/app-dev.md").exists());
    assert!(!root.join(".claude/agents/app-dev.md").exists());

    let led: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(root.join(".claude/disabled.json")).unwrap())
            .unwrap();
    let e0 = &led["disabled"][0];
    assert_eq!(e0["kind"], "agent");
    assert_eq!(e0["name"], "app-dev");
    assert_eq!(e0["from"], ".claude/agents/app-dev.md");
    assert_eq!(e0["reason"], "on hold");

    toggle::toggle(&root, "agent", "app-dev", true, "", false, "").unwrap();
    assert!(root.join(".claude/agents/app-dev.md").exists());
    fs::remove_dir_all(&root).unwrap();
}

#[test]
fn soft_protected_items_need_confirmation() {
    let root = temp_copy("soft");
    // stage a SOFT hook in the fixture
    fs::write(root.join(".claude/hooks/check-commit-msg.sh"), "#!/bin/sh\nexit 0\n").unwrap();
    let e = toggle::toggle(&root, "hook", "check-commit-msg", false, "", false, "").unwrap_err();
    assert_eq!(e.code, 409, "SOFT item must refuse without confirmation");
    assert!(root.join(".claude/hooks/check-commit-msg.sh").exists());
    toggle::toggle(&root, "hook", "check-commit-msg", false, "", true, "")
        .expect("SOFT item must proceed with confirm_soft");
    assert!(root.join(".claude/disabled/hooks/check-commit-msg.sh").exists());
    fs::remove_dir_all(&root).unwrap();
}

#[test]
fn error_paths() {
    let root = temp_copy("err");
    // enable of something never disabled
    let e = toggle::toggle(&root, "rule", "testing", true, "", false, "").unwrap_err();
    assert_eq!(e.code, 404);
    // unknown name
    let e = toggle::toggle(&root, "rule", "no-such-rule", false, "", false, "").unwrap_err();
    assert_eq!(e.code, 404);
    // double disable
    toggle::toggle(&root, "rule", "testing", false, "", false, "").unwrap();
    fs::write(root.join(".claude/rules/testing.md"), "resurrected\n").unwrap();
    let e = toggle::toggle(&root, "rule", "testing", false, "", false, "").unwrap_err();
    assert_eq!(e.code, 409);
    // bad names and kinds
    assert_eq!(toggle::toggle(&root, "rule", "../escape", false, "", false, "").unwrap_err().code, 400);
    assert_eq!(toggle::toggle(&root, "widget", "x", false, "", false, "").unwrap_err().code, 400);
    fs::remove_dir_all(&root).unwrap();
}

#[test]
fn enable_falls_back_to_filesystem_state() {
    let root = temp_copy("fallback");
    // quarantine a rule by hand, with no disabled.json record
    let q = root.join(".claude/disabled/rules");
    fs::create_dir_all(&q).unwrap();
    fs::rename(root.join(".claude/rules/testing.md"), q.join("testing.md")).unwrap();
    toggle::toggle(&root, "rule", "testing", true, "", false, "")
        .expect("enable must work from filesystem state alone");
    assert!(root.join(".claude/rules/testing.md").exists());
    fs::remove_dir_all(&root).unwrap();
}
