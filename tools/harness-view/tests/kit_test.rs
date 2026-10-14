//! orchestrator-kit output, and the subagent frontmatter fields Claude Code
//! documents. `tests/kit-fixture` is a writing repository (researcher, writer,
//! editor - no code, no tests) with the kit installed by following its
//! INSTALL.md: files copied unedited, settings.merge.json merged, both snippets
//! appended, and the board built by the kit's own `task.sh` (dates fixed to one
//! value afterwards so the fixture never changes on its own).

use harness_view::{assess, scan};
use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};

fn fixture() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests").join("kit-fixture")
}

fn node<'a>(g: &'a Value, id: &str) -> &'a Value {
    g["nodes"]
        .as_array()
        .unwrap()
        .iter()
        .find(|n| n["id"] == id)
        .unwrap_or_else(|| panic!("no node {id}"))
}

fn has_edge(g: &Value, from: &str, to: &str, ty: &str) -> bool {
    g["edges"]
        .as_array()
        .unwrap()
        .iter()
        .any(|e| e["from"] == from && e["to"] == to && e["type"] == ty)
}

fn strs(v: &Value) -> Vec<String> {
    v.as_array()
        .map(|a| a.iter().filter_map(|x| x.as_str().map(String::from)).collect())
        .unwrap_or_default()
}

fn copy_tree(from: &Path, to: &Path) {
    fs::create_dir_all(to).unwrap();
    for e in fs::read_dir(from).unwrap().flatten() {
        let p = e.path();
        let dest = to.join(e.file_name());
        if p.is_dir() {
            copy_tree(&p, &dest);
        } else {
            fs::copy(&p, &dest).unwrap();
        }
    }
}

fn temp_copy(tag: &str) -> PathBuf {
    let tmp = std::env::temp_dir().join(format!("hv-kit-{tag}-{}", std::process::id()));
    let _ = fs::remove_dir_all(&tmp);
    copy_tree(&fixture(), &tmp);
    tmp
}

#[test]
fn the_board_shows_every_task_in_its_state() {
    let g = scan::scan(&fixture());
    for (stem, status, owner) in [
        ("TASK-001-collect-sources-on-field-notebooks", "completed", "researcher"),
        ("TASK-002-draft-the-comparison", "active", "writer"),
        ("TASK-003-review-the-draft", "pending", "editor"),
        ("TASK-004-translate-the-summary", "canceled", "writer"),
    ] {
        let n = node(&g, &format!("task:{stem}"));
        assert_eq!(n["meta"]["status"], status, "{stem}");
        assert_eq!(n["meta"]["owner"], owner, "{stem}: task.sh writes agent:, read as owner");
        assert_eq!(n["meta"]["board"], ".agent-base/tasks");
        assert_eq!(n["meta"]["mission"], "field-notes");
        assert!(n["meta"].get("drift").is_none(), "{stem} drifted: {}", n["meta"]["drift"]);
        assert!(has_edge(&g, &format!("agent:{owner}"), &format!("task:{stem}"), "owns"));
        assert!(n["file"].as_str().unwrap().starts_with(&format!(".agent-base/tasks/{status}/")));
    }
    // depends_on: read as deps; task.sh's `-` means none and is dropped
    assert_eq!(node(&g, "task:TASK-002-draft-the-comparison")["meta"]["deps"], "TASK-001");
    assert!(node(&g, "task:TASK-001-collect-sources-on-field-notebooks")["meta"].get("deps").is_none());
}

#[test]
fn board_drift_is_detected_and_assessed() {
    let root = temp_copy("drift");
    let b = root.join(".agent-base/tasks");
    // moved by hand: the folder says completed, status: and TASKS.md say active
    fs::rename(
        b.join("active/TASK-002-draft-the-comparison.md"),
        b.join("completed/TASK-002-draft-the-comparison.md"),
    )
    .unwrap();
    // an index row with no file anywhere
    let idx = fs::read_to_string(b.join("TASKS.md")).unwrap();
    fs::write(b.join("TASKS.md"), idx + "| TASK-009 | Ghost | writer | active | - | - |\n").unwrap();

    let g = scan::scan(&root);
    let d = strs(&node(&g, "task:TASK-002-draft-the-comparison")["meta"]["drift"]);
    assert!(d.iter().any(|x| x.contains("status: active")), "{d:?}");
    assert!(d.iter().any(|x| x.contains("TASKS.md says active")), "{d:?}");
    let ghost = node(&g, "task:TASK-009");
    assert!(ghost.get("file").is_none());
    assert!(strs(&ghost["meta"]["drift"])[0].contains("no file"));

    let a = assess::assess(&root, &g);
    let drift: Vec<&Value> = a["findings"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|f| f["check"] == "board-drift")
        .collect();
    assert_eq!(drift.len(), 3, "{drift:?}");
    let _ = fs::remove_dir_all(&root);
}

#[test]
fn kit_hooks_are_wired_with_their_events() {
    let g = scan::scan(&fixture());
    // registered in the orchestrator's own frontmatter, not in settings.json
    for (h, matcher) in [
        ("spawn-guard", "Agent"),
        ("scope-guard", "Edit|Write|MultiEdit|NotebookEdit"),
    ] {
        let m = &node(&g, &format!("hook:{h}"))["meta"];
        assert_eq!(m["registered"], true, "{h}");
        assert_eq!(m["event"], "PreToolUse", "{h}");
        assert_eq!(m["matcher"], matcher, "{h}");
        assert_eq!(m["blocking"], true, "{h}");
        assert_eq!(strs(&m["scope"]), vec!["orchestrator"], "{h}");
        assert!(has_edge(&g, "agent:orchestrator", &format!("hook:{h}"), "triggers"));
        assert!(!has_edge(&g, "settings", &format!("hook:{h}"), "triggers"));
    }
    // merged into settings.json by the install
    let m = &node(&g, "hook:task-board-guard")["meta"];
    assert_eq!(m["event"], "PreToolUse");
    assert!(m.get("scope").is_none());
    assert!(has_edge(&g, "settings", "hook:task-board-guard", "triggers"));
    // sourced by all three, registered by none
    assert_eq!(node(&g, "hook:orch-lib")["meta"]["library"], true);
    for h in ["spawn-guard", "scope-guard", "task-board-guard"] {
        assert!(has_edge(&g, &format!("hook:{h}"), "hook:orch-lib", "sources"), "{h}");
    }
    // the allowlist is a data file, not a hook
    assert!(g["nodes"].as_array().unwrap().iter().all(|n| n["id"] != "hook:spawn-allowlist"));
}

#[test]
fn hooks_on_other_events_are_read() {
    let g = scan::scan(&fixture());
    for (h, ev, blocking) in [
        ("session-brief", "SessionStart", false),
        ("prompt-log", "UserPromptSubmit", false),
        ("precompact-save", "PreCompact", false),
        ("stop-check", "Stop", false),
        // gates the permission, so it blocks like a PreToolUse hook
        ("permission-audit", "PermissionRequest", true),
    ] {
        let m = &node(&g, &format!("hook:{h}"))["meta"];
        assert_eq!(m["event"], ev, "{h}");
        assert_eq!(m["blocking"], blocking, "{h}");
    }
    assert_eq!(node(&g, "hook:precompact-save")["meta"]["matcher"], "auto");
    // one script registered under two events lists both
    assert_eq!(strs(&node(&g, "hook:stop-check")["meta"]["events"]), vec!["Stop", "SubagentStop"]);
    // an inline command has no hook file and still shows up
    let other = strs(&node(&g, "settings")["meta"]["otherHooks"]);
    assert_eq!(other, vec!["SessionStart -> echo 'Read docs/brief.md before starting.'"]);
}

#[test]
fn the_orchestrator_and_its_spawn_allowlist() {
    let g = scan::scan(&fixture());
    let o = &node(&g, "agent:orchestrator")["meta"];
    assert_eq!(strs(&o["spawnAllowlist"]), vec!["Explore", "Plan"]);
    assert_eq!(o["permissionMode"], "default");
    assert_eq!(o["tier"], "Guarded", "the kit's Japanese tier table routes Guarded work here");
    for seat in ["researcher", "writer", "editor", "lead-researcher"] {
        assert!(has_edge(&g, "agent:orchestrator", &format!("agent:{seat}"), "spawns"), "{seat}");
    }
    // Agent(researcher, Explore): exactly the named seat, and the built-in is listed
    let l = &node(&g, "agent:lead-researcher")["meta"];
    assert_eq!(strs(&l["tools"]), vec!["Read", "Grep", "Glob", "Agent(researcher, Explore)"]);
    assert_eq!(strs(&l["spawns"]), vec!["Explore", "researcher"]);
    assert!(has_edge(&g, "agent:lead-researcher", "agent:researcher", "spawns"));
    assert!(!has_edge(&g, "agent:lead-researcher", "agent:writer", "spawns"));
    // the instruction file's tier table, written in Japanese
    let instr = node(&g, "instr:agents");
    let tiers: Vec<String> = instr["tiers"]
        .as_array()
        .unwrap()
        .iter()
        .map(|t| t["tier"].as_str().unwrap().to_string())
        .collect();
    assert_eq!(tiers, vec!["Direct", "Standard", "Guarded"]);
}

#[test]
fn every_documented_subagent_field_is_read() {
    let g = scan::scan(&fixture());
    let w = &node(&g, "agent:writer")["meta"];
    assert_eq!(strs(&w["disallowedTools"]), vec!["Bash(rm *)", "WebFetch"]);
    assert_eq!(w["permissionMode"], "acceptEdits");
    assert_eq!(strs(&w["skills"]), vec!["citation-style"]);
    assert_eq!(strs(&w["mcpServers"]), vec!["drive", "glossary"]);
    assert_eq!(
        strs(&w["hooks"]),
        vec![
            "PostToolUse Edit|Write -> style-lint",
            "Stop -> prompt: Check every claim in the draft cites a source."
        ]
    );
    assert_eq!(w["memory"], "project");
    assert_eq!(w["background"], false);
    assert_eq!(w["omitClaudeMd"], false);
    assert_eq!(w["isolation"], "worktree");
    assert_eq!(w["color"], "green");
    assert_eq!(
        w["initialPrompt"],
        "Read the brief in docs/brief.md first.\nThen ask the researcher for sources."
    );
    assert_eq!(w["cacheTtl"], "1h");
    assert_eq!(w["maxTurns"], 40);
    // a skills: preload is a wire; a frontmatter hook is a trigger
    assert!(has_edge(&g, "agent:writer", "skill:citation-style", "uses"));
    assert!(has_edge(&g, "agent:writer", "hook:style-lint", "triggers"));
    assert_eq!(strs(&node(&g, "hook:style-lint")["meta"]["scope"]), vec!["writer"]);
}

#[test]
fn a_writing_repo_is_not_graded_as_a_code_repo() {
    let root = fixture();
    let g = scan::scan(&root);
    let a = assess::assess(&root, &g);
    let checks: Vec<String> = a["findings"]
        .as_array()
        .unwrap()
        .iter()
        .map(|f| format!("{} {}", f["check"].as_str().unwrap(), f["title"].as_str().unwrap()))
        .collect();
    assert_eq!(a["counts"]["high"], 0, "{checks:#?}");
    for bad in ["no-review-gate", "hook-unregistered", "hook-missing-file", "board-drift", "spawn-boundary"] {
        assert!(!checks.iter().any(|c| c.starts_with(bad)), "{bad}: {checks:#?}");
    }
    // the editor is the review gate here
    assert!(has_edge(&g, "agent:editor", "gate:merge-request", "reviews"));
    assert!(!a["root"].as_str().unwrap().contains("//?/"), "{}", a["root"]);
}

#[test]
fn a_seat_registering_a_missing_hook_is_reported() {
    let root = temp_copy("missing");
    fs::remove_file(root.join(".claude/hooks/scope-guard.sh")).unwrap();
    let g = scan::scan(&root);
    let a = assess::assess(&root, &g);
    let f = a["findings"]
        .as_array()
        .unwrap()
        .iter()
        .find(|f| f["check"] == "hook-missing-file")
        .unwrap_or_else(|| panic!("not reported: {}", a["findings"]));
    assert!(f["title"].as_str().unwrap().contains("scope-guard"));
    assert_eq!(f["file"], ".claude/agents/orchestrator.md");
    let _ = fs::remove_dir_all(&root);
}

#[test]
fn frontmatter_edge_cases() {
    let tmp = std::env::temp_dir().join(format!("hv-kit-fm-{}", std::process::id()));
    let _ = fs::remove_dir_all(&tmp);
    fs::create_dir_all(tmp.join(".claude/agents")).unwrap();
    // a BOM before the opening fence used to hide every key
    fs::write(
        tmp.join(".claude/agents/bom.md"),
        "\u{feff}---\nname: bom\nmodel: haiku\ntools: [Read, \"Agent(a, b)\"]\n---\nbody\n",
    )
    .unwrap();
    // `name:` differs from the file name: Claude Code dispatches by name
    fs::write(
        tmp.join(".claude/agents/file-name.md"),
        "---\nname: real-name\ntools: Read\n---\n",
    )
    .unwrap();
    let g = scan::scan(&tmp);
    let b = &node(&g, "agent:bom")["meta"];
    assert_eq!(b["model"], "haiku");
    assert_eq!(strs(&b["tools"]), vec!["Read", "Agent(a, b)"]);
    assert_eq!(strs(&b["spawns"]), vec!["a", "b"]);
    assert_eq!(node(&g, "agent:file-name")["meta"]["name"], "real-name");
    let _ = fs::remove_dir_all(&tmp);
}

#[test]
fn the_hook_script_wins_over_other_hooks_paths_in_a_command() {
    assert_eq!(
        scan::hook_name_from_command("bash .claude/hooks/guard.sh .claude/hooks/data").as_deref(),
        Some("guard")
    );
    assert_eq!(
        scan::hook_name_from_command(r#"bash "${CLAUDE_PROJECT_DIR}/.claude/hooks/scope-guard.sh" ".agent-base/tasks/*""#)
            .as_deref(),
        Some("scope-guard")
    );
    assert_eq!(scan::hook_name_from_command("echo hi"), None);
}

#[test]
fn review_seats_are_matched_by_role() {
    for yes in ["code-reviewer", "security-privacy-reviewer", "fact-checker", "checker", "editor", "auditor"] {
        assert!(scan::is_review_seat(yes), "{yes}");
    }
    for no in ["writer", "researcher", "strategist", "app-dev", "orchestrator"] {
        assert!(!scan::is_review_seat(no), "{no}");
    }
}

#[test]
fn kit_fixture_scan_is_deterministic() {
    let a = scan::to_canonical_json(&scan::scan(&fixture()));
    let b = scan::to_canonical_json(&scan::scan(&fixture()));
    assert_eq!(a, b);
}
