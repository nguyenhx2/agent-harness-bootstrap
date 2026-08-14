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
    assert!(has_edge(&g, "cmd:review-changes", "script:code-graph", "runs"));
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
fn scan_is_deterministic() {
    let a = scan::to_canonical_json(&scan::scan(&fixture()));
    let b = scan::to_canonical_json(&scan::scan(&fixture()));
    assert_eq!(a, b, "two scans of the same tree must be byte-identical");
    assert!(!a.contains("generated"), "no timestamps or run metadata allowed");
}
