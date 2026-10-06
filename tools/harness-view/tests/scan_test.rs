use harness_view::scan;
use serde_json::Value;
use std::path::PathBuf;

fn fixture() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests").join("fixture")
}

fn ids(graph: &Value, key: &str) -> Vec<String> {
    graph[key]
        .as_array()
        .unwrap()
        .iter()
        .map(|n| n.get("id").and_then(|i| i.as_str()).unwrap_or("").to_string())
        .collect()
}

fn has_edge(graph: &Value, from: &str, to: &str, ty: &str) -> bool {
    graph["edges"].as_array().unwrap().iter().any(|e| {
        e["from"] == from && e["to"] == to && e["type"] == ty
    })
}

#[test]
fn scan_finds_expected_nodes() {
    let g = scan::scan(&fixture());
    let node_ids = ids(&g, "nodes");
    for expected in [
        "agent:orchestrator",
        "agent:code-reviewer",
        "agent:app-dev",
        "rule:agent-guardrails",
        "rule:testing",
        "cmd:review-changes",
        "cmd:deploy",
        "hook:protect-secrets",
        "hook:graph-stale",
        "settings",
        "script:code-graph",
        "mod:src/app",
        "mod:src/lib",
        "task:TASK-01",
        "gate:merge-request",
        "human",
    ] {
        assert!(node_ids.contains(&expected.to_string()), "missing node {expected}");
    }
    assert_eq!(g["version"], 1);
}

#[test]
fn scan_builds_expected_edges() {
    let g = scan::scan(&fixture());
    assert!(has_edge(&g, "settings", "hook:protect-secrets", "triggers"));
    assert!(has_edge(&g, "settings", "hook:graph-stale", "triggers"));
    assert!(has_edge(&g, "rule:agent-guardrails", "agent:app-dev", "gates"));
    // path-scoped rules gate nobody
    assert!(!has_edge(&g, "rule:testing", "agent:app-dev", "gates"));
    assert!(has_edge(&g, "agent:orchestrator", "agent:code-reviewer", "spawns"));
    assert!(has_edge(&g, "agent:code-reviewer", "gate:merge-request", "reviews"));
    assert!(has_edge(&g, "gate:merge-request", "human", "escalates"));
    assert!(has_edge(&g, "human", "cmd:deploy", "invokes"));
    // one command referencing two scripts emits two runs edges
    assert!(has_edge(&g, "cmd:review-changes", "script:code-graph", "runs"));
    assert!(has_edge(&g, "cmd:review-changes", "script:graph-html", "runs"));
    assert!(has_edge(&g, "agent:app-dev", "mod:src/app", "owns"));
    assert!(has_edge(&g, "mod:src/app", "mod:src/lib", "references"));
    assert!(has_edge(&g, "task:TASK-01", "mod:src/app", "references"));
}

#[test]
fn scan_reads_frontmatter_meta() {
    let g = scan::scan(&fixture());
    let orch = g["nodes"]
        .as_array()
        .unwrap()
        .iter()
        .find(|n| n["id"] == "agent:orchestrator")
        .unwrap();
    assert_eq!(orch["meta"]["model"], "opus");
    assert_eq!(orch["meta"]["maxTurns"], 40);
    let tools: Vec<&str> = orch["meta"]["tools"]
        .as_array()
        .unwrap()
        .iter()
        .map(|t| t.as_str().unwrap())
        .collect();
    assert!(tools.contains(&"Agent"));
    let hook = g["nodes"]
        .as_array()
        .unwrap()
        .iter()
        .find(|n| n["id"] == "hook:protect-secrets")
        .unwrap();
    assert_eq!(hook["meta"]["event"], "PreToolUse");
    assert_eq!(hook["meta"]["blocking"], true);
    assert_eq!(hook["meta"]["registered"], true);
    // .sh flavor preferred as the representative file
    assert_eq!(hook["file"], ".claude/hooks/protect-secrets.sh");
}

#[test]
fn every_node_carries_label_and_disabled() {
    let g = scan::scan(&fixture());
    for n in g["nodes"].as_array().unwrap() {
        let id = n["id"].as_str().unwrap();
        assert!(n.get("label").and_then(|l| l.as_str()).is_some(), "{id} lacks label");
        assert!(n.get("disabled").and_then(|d| d.as_bool()).is_some(), "{id} lacks disabled");
    }
    let by_id = |id: &str| {
        g["nodes"].as_array().unwrap().iter().find(|n| n["id"] == id).unwrap().clone()
    };
    // canonical label forms
    assert_eq!(by_id("cmd:review-changes")["label"], "/review-changes");
    assert_eq!(by_id("gate:merge-request")["label"], "Merge request");
    assert_eq!(by_id("human")["label"], "Human");
    assert_eq!(by_id("settings")["label"], "settings.json");
    assert_eq!(by_id("script:code-graph")["label"], "code-graph.py");
    assert_eq!(by_id("mod:src/app")["label"], "src/app");
    assert_eq!(by_id("rule:testing")["label"], "testing");
    // module meta carries both files and owner, owner "-" when unknown
    assert_eq!(by_id("mod:src/app")["meta"]["files"], 3);
    assert_eq!(by_id("mod:src/app")["meta"]["owner"], "app-dev");
    assert_eq!(by_id("mod:src/lib")["meta"]["files"], 2);
    assert_eq!(by_id("mod:src/lib")["meta"]["owner"], "-");
    // rule paths are unquoted
    let paths = by_id("rule:testing")["meta"]["paths"].clone();
    assert_eq!(paths[0], "tests/**");
    // settings node has no meta
    assert!(by_id("settings").get("meta").is_none());
}

#[test]
fn scan_is_deterministic() {
    let a = scan::to_canonical_json(&scan::scan(&fixture()));
    let b = scan::to_canonical_json(&scan::scan(&fixture()));
    assert_eq!(a, b, "two scans of the same tree must be byte-identical");
    assert!(!a.contains("generated"), "no timestamps or run metadata allowed");
}

// ------------------------------------------------- references read from content

fn node<'a>(g: &'a Value, id: &str) -> &'a Value {
    g["nodes"].as_array().unwrap().iter().find(|n| n["id"] == id).unwrap()
}

#[test]
fn references_written_in_the_files_become_edges() {
    let g = scan::scan(&fixture());
    // an agent's table: a rule by path, a command by its slash form
    assert!(has_edge(&g, "agent:app-dev", "rule:testing", "cites"));
    assert!(has_edge(&g, "agent:app-dev", "cmd:review-changes", "invokes"));
    // a hyphenated seat name in prose is a name
    assert!(has_edge(&g, "agent:app-dev", "agent:code-reviewer", "delegates"));
    // a command naming a command and a seat; a seat naming a non-Python script
    assert!(has_edge(&g, "cmd:deploy", "cmd:review-changes", "invokes"));
    assert!(has_edge(&g, "cmd:deploy", "agent:code-reviewer", "delegates"));
    assert!(has_edge(&g, "agent:app-dev", "script:check-env", "runs"));
    assert!(has_edge(&g, "cmd:deploy", "rule:agent-guardrails", "cites"));
    // a hook citing its rule in its header, and sourcing the shared helper
    assert!(has_edge(&g, "hook:protect-secrets", "rule:agent-guardrails", "enforces"));
    assert!(has_edge(&g, "hook:protect-secrets", "hook:_lib", "sources"));
}

#[test]
fn a_single_word_in_prose_is_not_a_reference() {
    // app-dev says "the testing rule" and "the word testing" in prose. Only the
    // backticked path is a reference, and it is counted once, as one edge.
    let g = scan::scan(&fixture());
    let n = g["edges"].as_array().unwrap().iter()
        .filter(|e| e["from"] == "agent:app-dev" && e["to"] == "rule:testing").count();
    assert_eq!(n, 1);
    // no static table: a hook that names no rule enforces none
    assert!(!g["edges"].as_array().unwrap().iter()
        .any(|e| e["from"] == "hook:specs-reminder" && e["type"] == "enforces"));
}

#[test]
fn a_sourced_unregistered_hook_is_a_library() {
    let g = scan::scan(&fixture());
    let lib = node(&g, "hook:_lib");
    assert_eq!(lib["meta"]["registered"], false);
    assert_eq!(lib["meta"]["library"], true);
    // a registered hook is never a library, even when something sources it
    assert!(node(&g, "hook:protect-secrets")["meta"].get("library").is_none());
}

#[test]
fn shell_scripts_are_script_nodes() {
    let g = scan::scan(&fixture());
    assert_eq!(node(&g, "script:check-env")["label"], "check-env.sh");
    assert_eq!(node(&g, "script:check-env")["file"], ".claude/scripts/check-env.sh");
}

#[test]
fn paths_outside_the_harness_tree_are_not_harness_references() {
    let d = std::env::temp_dir().join(format!("hv-refs-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&d);
    for (p, body) in [
        (".claude/rules/style.md", "---\ndescription: x\n---\nx\n"),
        (".claude/skills/lint/SKILL.md", "---\nname: lint\n---\nx\n"),
        (".claude/scripts/build.py", "print()\n"),
        (".claude/agents/dev.md",
         "---\nname: dev\n---\nSee .cursor/rules/style.md and .claude/skills/other/scripts/build.py.\n\
          Run the lint step, then **lint**.\n"),
    ] {
        let f = d.join(p);
        std::fs::create_dir_all(f.parent().unwrap()).unwrap();
        std::fs::write(f, body).unwrap();
    }
    let g = scan::scan(&d);
    let from_dev: Vec<_> = g["edges"].as_array().unwrap().iter()
        .filter(|e| e["from"] == "agent:dev")
        .map(|e| (e["to"].as_str().unwrap().to_string(), e["type"].as_str().unwrap().to_string()))
        .collect();
    // only the bold span names the skill; the other tree's style.md and the
    // skill-private build.py are not this harness's rule and script
    assert_eq!(from_dev, vec![("skill:lint".to_string(), "uses".to_string())], "{from_dev:?}");
    let _ = std::fs::remove_dir_all(&d);
}
