//! Fixtures that each trip one rule of the assessment engine. A check nothing
//! can fail is a check nobody can trust, so every rule here is proven by a tree
//! that breaks it and a tree that does not.

use harness_view::{assess, scan};
use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};

fn tmp(name: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!("hv-assess-{name}"));
    let _ = fs::remove_dir_all(&d);
    fs::create_dir_all(&d).unwrap();
    d
}

fn write(root: &Path, rel: &str, body: &str) {
    let p = root.join(rel);
    fs::create_dir_all(p.parent().unwrap()).unwrap();
    fs::write(p, body).unwrap();
}

/// A harness that passes everything the engine checks, as the baseline other
/// fixtures deviate from.
fn good(root: &Path) {
    write(root, ".claude/settings.json", r#"{
      "permissions": { "deny": ["Bash(git push --force:*)", "Bash(rm -rf:*)", "Read(./**/.env)"] },
      "hooks": { "PreToolUse": [ { "matcher": "Bash",
        "hooks": [ { "type": "command", "command": "bash .claude/hooks/protect-secrets.sh" } ] } ] }
    }"#);
    write(root, ".claude/hooks/protect-secrets.sh", "#!/bin/sh\nexit 0\n");
    write(root, ".claude/rules/agent-guardrails.md", "# guardrails\n");
    write(root, ".claude/rules/testing.md", "---\npaths:\n  - \"tests/**\"\n---\n# testing\n");
    write(root, ".claude/commands/review-changes.md", "# review\n");
    write(root, ".claude/agents/orchestrator.md",
          "---\nname: orchestrator\nmodel: opus\neffort: high\ntools: Read, Grep, Agent\n---\nbody\n");
    write(root, ".claude/agents/code-reviewer.md",
          "---\nname: code-reviewer\nmodel: opus\neffort: high\ntools: Read, Grep, Glob\n---\nbody\n");
}

fn run(root: &Path) -> Value {
    let g = scan::scan(root);
    assess::assess(root, &g)
}

fn checks(a: &Value) -> Vec<String> {
    a["findings"]
        .as_array()
        .unwrap()
        .iter()
        .map(|f| f["check"].as_str().unwrap_or("").to_string())
        .collect()
}

#[test]
fn clean_harness_reports_nothing() {
    let d = tmp("clean");
    good(&d);
    let a = run(&d);
    let found = checks(&a);
    assert!(found.is_empty(), "clean fixture should be silent, got {found:?}");
    assert_eq!(a["scores"]["overall"], 100);
}

#[test]
fn agent_without_model_or_effort_is_reported() {
    let d = tmp("model");
    good(&d);
    write(&d, ".claude/agents/app-dev.md",
          "---\nname: app-dev\ntools: Read, Write\n---\nbody\n");
    let found = checks(&run(&d));
    assert!(found.contains(&"agent-model".to_string()), "{found:?}");
    assert!(found.contains(&"agent-effort".to_string()), "{found:?}");
}

#[test]
fn agent_without_tools_is_high_severity() {
    let d = tmp("tools");
    good(&d);
    write(&d, ".claude/agents/app-dev.md",
          "---\nname: app-dev\nmodel: sonnet\neffort: medium\n---\nbody\n");
    let a = run(&d);
    let f = a["findings"].as_array().unwrap();
    let hit = f.iter().find(|x| x["check"] == "agent-tools").expect("agent-tools finding");
    assert_eq!(hit["severity"], "high");
    assert_eq!(hit["node"], "agent:app-dev");
}

#[test]
fn writing_reviewer_and_extra_spawner_are_reported() {
    let d = tmp("review");
    good(&d);
    write(&d, ".claude/agents/security-reviewer.md",
          "---\nname: security-reviewer\nmodel: opus\neffort: high\ntools: Read, Write\n---\nbody\n");
    write(&d, ".claude/agents/rogue.md",
          "---\nname: rogue\nmodel: haiku\neffort: low\ntools: Read, Agent\n---\nbody\n");
    let found = checks(&run(&d));
    assert!(found.contains(&"reviewer-readonly".to_string()), "{found:?}");
    assert!(found.contains(&"spawn-boundary".to_string()), "{found:?}");
}

#[test]
fn unscoped_rule_is_reported_but_the_six_always_on_are_not() {
    let d = tmp("scope");
    good(&d);
    // allowed to be unconditional
    write(&d, ".claude/rules/model-policy.md", "# model policy\n");
    // not allowed
    write(&d, ".claude/rules/frontend.md", "# frontend\n");
    let a = run(&d);
    let titles: Vec<String> = a["findings"].as_array().unwrap().iter()
        .filter(|f| f["check"] == "rule-scoping")
        .map(|f| f["title"].as_str().unwrap().to_string())
        .collect();
    assert!(titles.iter().any(|t| t.contains("frontend")), "{titles:?}");
    assert!(!titles.iter().any(|t| t.contains("model-policy")), "{titles:?}");
}

#[test]
fn registered_hook_with_no_file_is_high() {
    let d = tmp("deadhook");
    good(&d);
    fs::remove_file(d.join(".claude/hooks/protect-secrets.sh")).unwrap();
    let a = run(&d);
    let hit = a["findings"].as_array().unwrap().iter()
        .find(|x| x["check"] == "hook-missing-file")
        .expect("hook-missing-file finding");
    assert_eq!(hit["severity"], "high");
}

#[test]
fn missing_deny_list_and_review_gate_are_reported() {
    let d = tmp("layers");
    good(&d);
    write(&d, ".claude/settings.json", "{ \"permissions\": { \"deny\": [] } }");
    fs::remove_file(d.join(".claude/commands/review-changes.md")).unwrap();
    fs::remove_file(d.join(".claude/agents/code-reviewer.md")).unwrap();
    let found = checks(&run(&d));
    assert!(found.contains(&"deny-list".to_string()), "{found:?}");
    assert!(found.contains(&"no-blocking-hook".to_string()), "{found:?}");
    assert!(found.contains(&"no-review-gate".to_string()), "{found:?}");
}

/// The false positive found on a real harness: a repo whose review gate is
/// called `/review-pr` has a review gate.
#[test]
fn a_differently_named_review_command_still_counts() {
    let d = tmp("reviewpr");
    good(&d);
    fs::rename(
        d.join(".claude/commands/review-changes.md"),
        d.join(".claude/commands/review-pr.md"),
    ).unwrap();
    let found = checks(&run(&d));
    assert!(!found.contains(&"no-review-gate".to_string()), "{found:?}");
    assert!(!found.contains(&"no-review-command".to_string()), "{found:?}");
}

#[test]
fn task_owned_by_a_seat_not_on_the_roster_is_reported() {
    let d = tmp("owner");
    good(&d);
    write(&d, "docs/tasks/active/TASK-001-x.md",
          "---\ntitle: x\nstatus: Active\nowner: ghost-dev\n---\nbody\n");
    let a = run(&d);
    let hit = a["findings"].as_array().unwrap().iter()
        .find(|x| x["check"] == "task-owner-missing")
        .expect("task-owner-missing finding");
    assert!(hit["title"].as_str().unwrap().contains("ghost-dev"));
}

#[test]
fn blocked_task_with_no_dependency_is_reported() {
    let d = tmp("blocked");
    good(&d);
    write(&d, "docs/tasks/active/TASK-002-y.md",
          "---\ntitle: y\nstatus: Blocked\nowner: code-reviewer\n---\nbody\n");
    let found = checks(&run(&d));
    assert!(found.contains(&"blocked-no-unblocker".to_string()), "{found:?}");
}

#[test]
fn blank_line_inside_a_table_is_located() {
    // the exact shape from the real repo: rows, a blank line, more rows
    let text = "# t\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n| 3 | 4 |\n";
    assert_eq!(assess::blank_line_in_table(text), Some(6));
    // a table that simply ends is not a defect
    let ok = "| a | b |\n|---|---|\n| 1 | 2 |\n\nprose after the table\n";
    assert_eq!(assess::blank_line_in_table(ok), None);
}

#[test]
fn scores_fall_only_for_the_category_that_failed() {
    let d = tmp("scoring");
    good(&d);
    write(&d, ".claude/agents/app-dev.md",
          "---\nname: app-dev\nmodel: sonnet\neffort: medium\n---\nbody\n"); // no tools
    let a = run(&d);
    let c = &a["scores"]["categories"];
    assert!(c["Cost control"]["score"].as_u64().unwrap() < 100);
    assert_eq!(c["Safety"]["score"], 100);
    assert_eq!(c["Board health"]["score"], 100);
}
