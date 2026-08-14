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
    toggle::toggle(&root, "rule", "testing", false, "test run").unwrap();
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
    toggle::toggle(&root, "rule", "testing", true, "").unwrap();
    assert!(root.join(".claude/rules/testing.md").exists());
    assert!(!root.join(".claude/disabled/rules/testing.md").exists());
    let disabled: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(root.join(".claude/disabled.json")).unwrap())
            .unwrap();
    assert_eq!(disabled["disabled"].as_array().unwrap().len(), 0);
    fs::remove_dir_all(&root).unwrap();
}

#[test]
fn toggle_hook_restores_settings_byte_exactly() {
    let root = temp_copy("hook");
    // canonical baseline first, so the round trip is byte-comparable
    toggle::canonicalize_settings(&root).unwrap();
    let before = fs::read_to_string(root.join(".claude/settings.json")).unwrap();

    toggle::toggle(&root, "hook", "graph-stale", false, "noisy during refactor").unwrap();
    assert!(!root.join(".claude/hooks/graph-stale.sh").exists());
    assert!(root.join(".claude/disabled/hooks/graph-stale.sh").exists());
    let mid = fs::read_to_string(root.join(".claude/settings.json")).unwrap();
    assert!(!mid.contains("graph-stale"), "registration must be stripped");

    toggle::toggle(&root, "hook", "graph-stale", true, "").unwrap();
    assert!(root.join(".claude/hooks/graph-stale.sh").exists());
    let after = fs::read_to_string(root.join(".claude/settings.json")).unwrap();
    assert_eq!(before, after, "enable must restore settings.json byte-exactly");
    fs::remove_dir_all(&root).unwrap();
}

#[test]
fn hard_protected_items_refuse() {
    let root = temp_copy("hard");
    let e = toggle::toggle(&root, "hook", "protect-secrets", false, "").unwrap_err();
    assert_eq!(e.code, 403);
    assert!(root.join(".claude/hooks/protect-secrets.sh").exists());
    let e = toggle::toggle(&root, "rule", "agent-guardrails", false, "").unwrap_err();
    assert_eq!(e.code, 403);
    let e = toggle::toggle(&root, "agent", "orchestrator", false, "").unwrap_err();
    assert_eq!(e.code, 400);
    fs::remove_dir_all(&root).unwrap();
}
