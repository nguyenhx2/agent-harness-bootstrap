//! The rubric is published, and the published document is the rubric: these
//! tests keep RUBRIC.md / RUBRIC.ja.md equal to `src/rubric.rs`, prove every
//! score can be recomputed from the weights in it, and prove the action-oriented
//! parts of an assessment - evidence lines, fixes, one-click actions, the
//! worklist, the diff and purpose-aware rules - each fire when they should.

use harness_view::{agentedit, assess, rubric, scan};
use serde_json::Value;
use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};

fn tmp(name: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!("hv-rubric-{name}-{}", std::process::id()));
    let _ = fs::remove_dir_all(&d);
    fs::create_dir_all(&d).unwrap();
    d
}

fn write(root: &Path, rel: &str, body: &str) {
    let p = root.join(rel);
    fs::create_dir_all(p.parent().unwrap()).unwrap();
    fs::write(p, body).unwrap();
}

fn manifest() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn run(root: &Path) -> Value {
    let g = scan::scan(root);
    assess::assess(root, &g)
}

fn find<'a>(a: &'a Value, check: &str) -> Vec<&'a Value> {
    a["findings"].as_array().unwrap().iter().filter(|f| f["check"] == check).collect()
}

fn checks(a: &Value) -> BTreeSet<String> {
    a["findings"].as_array().unwrap().iter().map(|f| f["check"].as_str().unwrap().to_string()).collect()
}

/// A code harness that passes, plus one seat with every budget gap.
fn code_repo(name: &str) -> PathBuf {
    let d = tmp(name);
    write(&d, "AGENTS.md", "# AGENTS.md\n\n| Tier | The change | Who runs it | What it adds |\n|---|---|---|---|\n\
| **Direct** | a | the owning agent | b |\n| **Standard** | a | the owning agent | b |\n\
| **Guarded** | a | `orchestrator` | b |\n");
    write(&d, "CLAUDE.md", "@AGENTS.md\n");
    write(&d, ".claude/settings.json", r#"{
  "permissions": { "deny": ["Bash(git push --force:*)", "Bash(rm -rf:*)", "Read(./**/.env)"] },
  "hooks": { "PreToolUse": [ { "matcher": "Bash",
    "hooks": [ { "type": "command", "command": "bash .claude/hooks/protect-secrets.sh" } ] } ] }
}"#);
    write(&d, ".claude/hooks/protect-secrets.sh", "#!/bin/sh\nexit 0\n");
    write(&d, ".claude/rules/agent-guardrails.md", "# guardrails\n");
    write(&d, ".claude/commands/review-changes.md", "# review\n");
    write(&d, ".claude/agents/orchestrator.md",
          "---\nname: orchestrator\nmodel: opus\neffort: high\nmaxTurns: 40\ntools: Read, Agent\n---\nbody\n");
    write(&d, ".claude/agents/code-reviewer.md",
          "---\nname: code-reviewer\nmodel: opus\neffort: high\nmaxTurns: 25\ntools: Read, Grep\n\
           disallowedTools: Edit, Write\n---\nbody\n");
    d
}

#[test]
fn the_published_rubric_is_the_rubric() {
    for (lang, file) in [("en", "RUBRIC.md"), ("ja", "RUBRIC.ja.md")] {
        let on_disk = fs::read_to_string(manifest().join(file)).unwrap().replace("\r\n", "\n");
        assert_eq!(
            on_disk,
            rubric::markdown(lang),
            "{file} is stale - regenerate it with `harness-view rubric{}`",
            if lang == "ja" { " --lang ja" } else { "" }
        );
    }
}

#[test]
fn every_rule_is_complete_and_unique() {
    let mut ids = BTreeSet::new();
    let mut checks = BTreeSet::new();
    for r in rubric::RULES {
        assert!(ids.insert(r.id), "duplicate id {}", r.id);
        assert!(checks.insert(r.check), "duplicate check {}", r.check);
        assert!((1..=3).contains(&r.effort), "{}: effort", r.id);
        assert!(rubric::CATEGORIES.iter().any(|(c, _)| *c == r.category), "{}: category", r.id);
        for pair in [r.title, r.full, r.why, r.fix] {
            assert!(!pair[0].is_empty() && !pair[1].is_empty(), "{}: a text is empty", r.id);
            // the Japanese text is Japanese, not a copy of the English
            assert_ne!(pair[0], pair[1], "{}: untranslated", r.id);
            assert!(!pair[0].contains('\u{2014}') && !pair[1].contains('\u{2014}'), "{}: em dash", r.id);
        }
    }
    // the method names the number of categories it averages
    assert!(rubric::METHOD[0].contains("six categories") && rubric::CATEGORIES.len() == 6);
}

#[test]
fn the_score_is_reproducible_from_the_rubric() {
    let d = code_repo("repro");
    write(&d, ".claude/agents/app-dev.md", "---\nname: app-dev\n---\nbody\n");
    write(&d, ".claude/rules/frontend.md", "# frontend\n");
    write(&d, ".claude/hooks/orphan.sh", "#!/bin/sh\n");
    for a in [run(&d), run(&manifest().join("tests/kit-fixture")), run(&manifest().join("tests/fixture"))] {
        let mut sum = 0u32;
        for (cat, _) in rubric::CATEGORIES {
            let penalty: u32 = a["findings"]
                .as_array()
                .unwrap()
                .iter()
                .filter(|f| f["category"] == *cat)
                .map(|f| rubric::RULES.iter().find(|r| r.id == f["rubric"]).unwrap().sev.weight())
                .sum();
            let score = 100u32.saturating_sub(penalty.min(100));
            let c = &a["scores"]["categories"][*cat];
            assert_eq!(c["score"], score, "{cat}");
            let derived: u64 = c["derivation"].as_array().unwrap().iter().map(|x| x["points"].as_u64().unwrap()).sum();
            assert_eq!(derived, u64::from(penalty), "{cat}: derivation does not add up");
            sum += score;
        }
        assert_eq!(a["scores"]["overall"], sum / rubric::CATEGORIES.len() as u32);
    }
}

#[test]
fn a_finding_names_rule_evidence_and_fix_in_both_languages() {
    let d = code_repo("evidence");
    write(&d, ".claude/agents/app-dev.md", "---\nname: app-dev\nmodel: sonnet\n---\nbody\n");
    let a = run(&d);
    for f in a["findings"].as_array().unwrap() {
        for k in ["rubric", "title", "title_ja", "why", "why_ja", "fix", "fix_ja"] {
            assert!(f[k].as_str().map(|s| !s.is_empty()).unwrap_or(false), "{k} missing in {f}");
        }
        assert!(!f["fix"].as_str().unwrap().contains("{name}"), "unrendered template: {f}");
    }
    // a missing key is evidenced at the closing fence, where it would be added
    let e = find(&a, "agent-effort");
    assert_eq!(e[0]["evidence"], ".claude/agents/app-dev.md:4");
    assert_eq!(e[0]["rubric"], "COST-03");
    assert!(e[0]["fix"].as_str().unwrap().contains("effort: medium"));
    // a present key at its own line
    write(&d, ".claude/agents/code-reviewer.md",
          "---\nname: code-reviewer\nmodel: opus\neffort: high\nmaxTurns: 25\ntools: Read, Write\n\
           disallowedTools: Edit, Write\n---\nbody\n");
    let a = run(&d);
    assert_eq!(find(&a, "reviewer-readonly")[0]["evidence"], ".claude/agents/code-reviewer.md:6");
}

#[test]
fn a_one_click_fix_goes_through_the_agent_editor_and_the_diff_shows_it() {
    let d = code_repo("oneclick");
    write(&d, ".claude/agents/app-dev.md", "---\nname: app-dev\nmaxTurns: 9\n---\nbody text\n");
    let before = run(&d);
    let model = find(&before, "agent-model")[0].clone();
    let tools = find(&before, "agent-tools")[0].clone();
    for f in [&model, &tools] {
        let act = &f["action"];
        assert_eq!(act["endpoint"], "agent");
        agentedit::write_agent(&d, act["body"]["name"].as_str().unwrap(), &act["body"]).unwrap();
    }
    let after = run(&d);
    assert!(find(&after, "agent-model").is_empty() && find(&after, "agent-tools").is_empty());
    assert!(fs::read_to_string(d.join(".claude/agents/app-dev.md")).unwrap().ends_with("body text\n"));
    let diff = assess::diff(&before, &after);
    let fixed: BTreeSet<&str> = diff["fixed"].as_array().unwrap().iter().map(|f| f["check"].as_str().unwrap()).collect();
    assert_eq!(fixed, BTreeSet::from(["agent-model", "agent-tools"]));
    assert!(diff["new"].as_array().unwrap().is_empty());
    assert!(diff["overall"]["to"].as_u64() > diff["overall"]["from"].as_u64());
    assert!(diff["categories"]["Cost control"].is_object());
}

#[test]
fn no_one_click_fix_when_the_editor_would_refuse_it() {
    let d = code_repo("refuse");
    // a scoped Bash grant is not a tool name the editor accepts
    write(&d, ".claude/agents/code-reviewer.md",
          "---\nname: code-reviewer\nmodel: opus\neffort: high\nmaxTurns: 25\n\
           tools: Read, Write, Bash(git diff:*)\ndisallowedTools: Edit, Write\n---\nbody\n");
    let a = run(&d);
    let f = find(&a, "reviewer-readonly");
    assert_eq!(f.len(), 1);
    assert!(f[0].get("action").is_none(), "{}", f[0]);
}

#[test]
fn new_gate_checks_fire() {
    let d = code_repo("gate");
    write(&d, ".claude/agents/code-reviewer.md",
          "---\nname: code-reviewer\nmodel: opus\neffort: high\ntools: Read, Grep\nmemory: project\n---\nbody\n");
    write(&d, "AGENTS.md", &"line\n".repeat(150));
    write(&d, "CLAUDE.md", &"line\n".repeat(60));
    let found = checks(&run(&d));
    for c in ["agent-maxturns", "reviewer-disallowed", "reviewer-memory", "instruction-length"] {
        assert!(found.contains(c), "{c} not reported: {found:?}");
    }
    let clean = checks(&run(&code_repo("gate-clean")));
    assert!(clean.is_empty(), "{clean:?}");
}

#[test]
fn the_worklist_puts_cheap_heavy_fixes_first() {
    let d = code_repo("worklist");
    // three seats with no tools (high, effort 1) and one unscoped rule (medium, effort 2)
    for s in ["a-dev", "b-dev", "c-dev"] {
        write(&d, &format!(".claude/agents/{s}.md"),
              &format!("---\nname: {s}\nmodel: sonnet\neffort: low\nmaxTurns: 5\n---\nbody\n"));
    }
    write(&d, ".claude/rules/frontend.md", "# frontend\n");
    let a = run(&d);
    let w = a["worklist"].as_array().unwrap();
    assert_eq!(w[0]["rubric"], "COST-01");
    assert_eq!(w[0]["count"], 3);
    assert_eq!(w[0]["points"], 36);
    assert_eq!(w[0]["priority"], 216);
    assert_eq!(w[0]["one_click"], 3);
    let pos = |id: &str| w.iter().position(|x| x["rubric"] == id).unwrap();
    assert!(pos("COST-01") < pos("COST-05"));
    // fixing COST-01 would take Cost control from 59 to 95
    assert!(w[0]["overall_after"].as_u64().unwrap() > a["scores"]["overall"].as_u64().unwrap());
}

#[test]
fn purposes_decide_which_rules_apply() {
    // the kit fixture: researcher, writer, editor - read from the roster
    let kit = run(&manifest().join("tests/kit-fixture"));
    let p: Vec<&str> = kit["purposes"]["list"].as_array().unwrap().iter().map(|x| x.as_str().unwrap()).collect();
    assert_eq!(p, vec!["research", "docs"]);
    assert_eq!(kit["purposes"]["source"], "roster");
    let skipped = kit["purposes"]["rules_not_applied"].as_array().unwrap();
    assert!(skipped.iter().any(|x| x == "SAF-11") && skipped.iter().any(|x| x == "SAF-12"));

    // a research repo with no read-only checker is told so, and not told to add
    // a code review command
    let d = tmp("research");
    write(&d, ".claude/state/vars.json", r#"{"vars": {}, "flags": ["posix", "purpose_research"]}"#);
    write(&d, ".claude/agents/researcher.md",
          "---\nname: researcher\nmodel: sonnet\neffort: medium\nmaxTurns: 20\ntools: Read, Write\n---\n");
    let a = run(&d);
    assert_eq!(a["purposes"]["source"], "vars.json");
    let found = checks(&a);
    assert!(found.contains("noncode-checker"), "{found:?}");
    assert!(!found.contains("no-review-gate") && !found.contains("no-review-command"), "{found:?}");
    // a read-only checker satisfies it
    write(&d, ".claude/agents/checker.md",
          "---\nname: checker\nmodel: opus\neffort: high\nmaxTurns: 20\ntools: Read, Grep\n\
           disallowedTools: Edit, Write\n---\n");
    assert!(!checks(&run(&d)).contains("noncode-checker"));

    // a code repo is not asked for a deliverable checker
    let code = run(&code_repo("purpose-code"));
    assert_eq!(code["purposes"]["list"], serde_json::json!(["code"]));
    assert!(!checks(&code).contains("noncode-checker"));
    // and an explicit purpose overrides detection
    let g = scan::scan(&d);
    let forced = assess::assess_with(&d, &g, Some(vec!["code".into()]));
    assert_eq!(forced["purposes"]["source"], "given");
    assert!(!checks(&forced).contains("noncode-checker"));
}

#[test]
fn graph_diff_lists_added_and_removed_nodes() {
    let d = code_repo("gdiff");
    let g1 = scan::scan(&d);
    write(&d, ".claude/rules/new-rule.md", "---\npaths:\n  - \"x/**\"\n---\n# n\n");
    fs::remove_file(d.join(".claude/commands/review-changes.md")).unwrap();
    let g2 = scan::scan(&d);
    let gd = assess::graph_diff(&g1, &g2);
    assert_eq!(gd["nodes_added"], serde_json::json!(["rule:new-rule"]));
    assert_eq!(gd["nodes_removed"], serde_json::json!(["cmd:review-changes"]));
}

#[test]
fn only_a_nested_contract_is_held_to_saying_something() {
    // tests/fixture has short tool rule files (.cursor/rules, .kiro/steering,
    // .agents/rules) and one near-empty nested CLAUDE.md; only the last governs
    // a subtree.
    let a = run(&manifest().join("tests/fixture"));
    let stubs: Vec<&str> = find(&a, "instruction-nested-stub").iter().map(|f| f["file"].as_str().unwrap()).collect();
    assert_eq!(stubs, vec!["src/api/CLAUDE.md"]);
}

/// Every document here has a Japanese twin with the same structure: same
/// headings count, same code blocks, and a link each way. A section added in
/// one language and not the other fails here rather than drifting silently.
#[test]
fn the_japanese_docs_keep_pace_with_the_english() {
    for (en, ja) in [("README.md", "README.ja.md"), ("SCHEMA.md", "SCHEMA.ja.md"), ("RUBRIC.md", "RUBRIC.ja.md")] {
        let e = fs::read_to_string(manifest().join(en)).unwrap();
        let j = fs::read_to_string(manifest().join(ja)).unwrap_or_else(|_| panic!("{ja} is missing"));
        let headings = |t: &str| {
            let mut fenced = false;
            t.lines()
                .filter(|l| {
                    if l.starts_with("```") {
                        fenced = !fenced;
                    }
                    !fenced && l.starts_with('#')
                })
                .count()
        };
        let fences = |t: &str| t.lines().filter(|l| l.starts_with("```")).count();
        assert_eq!(headings(&e), headings(&j), "{ja}: heading count differs from {en}");
        assert_eq!(fences(&e), fences(&j), "{ja}: code block count differs from {en}");
        assert!(e.contains(&format!("({ja})")), "{en} does not link to {ja}");
        assert!(j.contains(&format!("({en})")), "{ja} does not link to {en}");
    }
}
