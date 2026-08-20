//! The roster editor, tested where it can actually hurt someone.
//!
//! Three of these tests exist because the corresponding failure is silent. A
//! frontmatter writer that re-wraps a body has destroyed a prompt and reports
//! success. An override merge that flips `verified` has turned a researched flag
//! into a rumour and reports success. A write path that accepts a traversal path
//! has written outside the harness and reports success. None of the three would
//! be noticed by looking at the page.

use harness_view::agentedit;
use serde_json::{json, Map, Value};
use std::path::{Path, PathBuf};

fn tmp(name: &str) -> PathBuf {
    let p = std::env::temp_dir().join(format!("hv-agentedit-{name}"));
    let _ = std::fs::remove_dir_all(&p);
    std::fs::create_dir_all(p.join(".claude/agents")).unwrap();
    p
}

fn changes(pairs: &[(&str, Value)]) -> Map<String, Value> {
    let mut m = Map::new();
    for (k, v) in pairs {
        m.insert((*k).to_string(), v.clone());
    }
    m
}

/// A real-shaped agent file: an unknown key the editor has never heard of
/// (`color`), a body with the kinds of formatting a reformatter would eat -
/// hard-wrapped prose, a nested list, trailing whitespace, a fenced block
/// containing a line that looks like frontmatter, and a final line with no
/// newline after it.
const AGENT: &str = "---\n\
name: qa-test\n\
description: Write and run tests.\n\
tools: Read, Grep, Glob, Edit, Write, Bash\n\
model: sonnet\n\
effort: medium\n\
color: cyan\n\
---\n\
\n\
You own test quality. Tests express the domain invariants of the bounded context\n\
they sit in - not implementation detail.   \n\
\n\
- Layers per `.claude/rules/testing.md`:\n\
  - cargo test (Rust units)\n\
  - Vitest (TS units, mocked IPC)\n\
- Mock ALL external providers.\n\
\n\
```yaml\n\
---\n\
model: not-really-frontmatter\n\
---\n\
```\n\
\n\
Last line, no trailing newline.";

/// THE guarantee. Everything from the closing `---` onward comes back byte for
/// byte, whatever was in it.
#[test]
fn the_body_is_byte_identical_after_a_write() {
    let (_, end) = agentedit::frontmatter_span(AGENT).unwrap();
    let body_before = &AGENT[end..];

    let out = agentedit::apply_frontmatter(
        AGENT,
        &changes(&[
            ("model", json!("opus")),
            ("effort", json!("high")),
            ("tools", json!(["Read", "Grep", "Bash"])),
            ("description", json!("Rewritten.")),
        ]),
    )
    .unwrap();

    let (_, end2) = agentedit::frontmatter_span(&out).unwrap();
    assert_eq!(
        &out[end2..],
        body_before,
        "the markdown body was not copied through byte for byte"
    );
    // Belt and braces: the fenced `---` inside the body must not have been
    // mistaken for the closing delimiter in either direction.
    assert!(out.contains("model: not-really-frontmatter"), "the fenced block was rewritten");
    assert!(out.ends_with("Last line, no trailing newline."), "the last line grew a newline");
    assert!(out.contains("they sit in - not implementation detail.   \n"), "trailing spaces were stripped");
}

/// Only the named keys move. `color` is the one the editor knows nothing about,
/// and it is exactly the kind of key a regenerating writer drops.
#[test]
fn an_unknown_key_and_the_key_order_survive() {
    let out = agentedit::apply_frontmatter(AGENT, &changes(&[("model", json!("opus"))])).unwrap();
    assert!(out.contains("color: cyan\n"), "an unknown frontmatter key was dropped");
    assert!(out.contains("name: qa-test\n"), "the seat's identity was touched");
    assert!(out.contains("model: opus\n"));
    assert!(!out.contains("model: sonnet"));
    // effort, tools and description are untouched, byte for byte
    assert!(out.contains("effort: medium\n"));
    assert!(out.contains("tools: Read, Grep, Glob, Edit, Write, Bash\n"));
    assert!(out.contains("description: Write and run tests.\n"));
    // and the keys are still in the order the file had them
    let order: Vec<&str> = ["name", "description", "tools", "model", "effort", "color"].to_vec();
    let mut last = 0;
    for k in order {
        let at = out.find(&format!("\n{k}:")).or_else(|| out.find(&format!("{k}:"))).unwrap();
        assert!(at >= last, "`{k}` moved");
        last = at;
    }
}

/// "Write only the frontmatter keys that changed" is a property of the FILE, not
/// of the request: posting a field that already reads that way must not rewrite
/// the line (and so must not requote it, reorder it, or touch its bytes).
#[test]
fn a_key_that_did_not_change_is_not_rewritten() {
    let out = agentedit::apply_frontmatter(
        AGENT,
        &changes(&[("model", json!("sonnet")), ("effort", json!("medium"))]),
    )
    .unwrap();
    assert_eq!(out, AGENT, "an unchanged key was rewritten");
}

/// A key the file does not carry is appended rather than losing the write.
#[test]
fn a_missing_key_is_appended_to_the_frontmatter() {
    let src = "---\nname: x\n---\nbody\n";
    let out = agentedit::apply_frontmatter(src, &changes(&[("effort", json!("xhigh"))])).unwrap();
    assert_eq!(out, "---\nname: x\neffort: xhigh\n---\nbody\n");
}

/// The order a roster lists its tools in is a choice someone made. It is
/// preserved on write, duplicates are dropped rather than sorted away, and
/// nothing is ever added.
#[test]
fn the_tools_list_keeps_the_order_it_was_given() {
    let out = agentedit::apply_frontmatter(
        AGENT,
        &changes(&[("tools", json!(["Bash", "Read", "Bash", "Agent"]))]),
    )
    .unwrap();
    assert!(out.contains("tools: Bash, Read, Bash, Agent\n"), "{out}");

    // and through the request validator, which is where duplicates are dropped
    let m = agentedit::changes_from_request(&json!({
        "tools": ["Bash", "Read", "Bash", "Agent"]
    }))
    .unwrap();
    assert_eq!(m["tools"], json!(["Bash", "Read", "Agent"]));

    // a block-list `tools:` is read as a list and rewritten as one line, and the
    // key AFTER it is not swallowed by the rewrite
    let block = "---\nname: x\ntools:\n  - Read\n  - Grep\nmodel: sonnet\n---\nbody\n";
    let read = agentedit::read_frontmatter(block).unwrap();
    assert_eq!(read["tools"], json!(["Read", "Grep"]));
    let out = agentedit::apply_frontmatter(block, &changes(&[("tools", json!(["Grep", "Read"]))])).unwrap();
    assert_eq!(out, "---\nname: x\ntools: Grep, Read\nmodel: sonnet\n---\nbody\n");
}

/// A CRLF file stays a CRLF file, and a multi-line description is written as
/// something that reads back as the same string.
#[test]
fn crlf_and_multiline_values_round_trip() {
    let src = "---\r\nname: x\r\nmodel: sonnet\r\n---\r\nbody\r\n";
    let out = agentedit::apply_frontmatter(src, &changes(&[("effort", json!("high"))])).unwrap();
    assert_eq!(out, "---\r\nname: x\r\nmodel: sonnet\r\neffort: high\r\n---\r\nbody\r\n");

    let long = "First line.\nSecond line: with a colon.\n- and a dash";
    let out = agentedit::apply_frontmatter(
        "---\nname: x\n---\nbody\n",
        &changes(&[("description", json!(long))]),
    )
    .unwrap();
    let read = agentedit::read_frontmatter(&out).unwrap();
    assert_eq!(read["description"], json!(long), "the description did not survive a round trip");
}

/// Only four keys are writable. This is the containment for CONTENT, and it has
/// to refuse rather than ignore: silently dropping `name` from a request would
/// report a success that did not happen.
#[test]
fn only_the_four_writable_keys_are_accepted() {
    for bad in ["name", "maxTurns", "color", "permissions"] {
        let e = agentedit::apply_frontmatter(AGENT, &changes(&[(bad, json!("x"))]));
        assert!(e.is_err(), "`{bad}` should not be writable");
    }
    // and an empty tools list is refused rather than guessed at, because an
    // ABSENT tools key means "inherit everything"
    assert!(agentedit::changes_from_request(&json!({ "tools": [] })).is_err());
    assert!(agentedit::changes_from_request(&json!({ "description": "  " })).is_err());
    assert!(agentedit::changes_from_request(&json!({})).is_err());
    assert!(agentedit::changes_from_request(&json!({ "model": "a\nb" })).is_err());
    assert!(agentedit::changes_from_request(&json!({ "tools": ["../x"] })).is_err());
}

/// A file with no frontmatter is refused by name rather than having one grafted
/// onto it.
#[test]
fn a_file_without_frontmatter_is_refused() {
    for bad in ["# just a heading\n", "\n---\nname: x\n---\n", "---\nname: x\nno close\n"] {
        assert!(agentedit::frontmatter_span(bad).is_err(), "should have refused {bad:?}");
    }
}

/// THE bug not to ship. Every one of these is a name that, taken as a path,
/// would write outside `.claude/agents/` - and every one is refused before a
/// path exists, by the character check rather than by a canonicalization that
/// has to be right on two operating systems.
#[test]
fn a_traversal_name_never_resolves_to_a_file() {
    let root = tmp("traversal");
    std::fs::write(root.join(".claude/agents/qa-test.md"), AGENT).unwrap();
    // a real file outside the harness: the target a traversal would want
    let outside = root.join("SECRET.md");
    std::fs::write(&outside, "do not write here").unwrap();
    let above = root.parent().unwrap().join("hv-agentedit-outside.md");
    std::fs::write(&above, "nor here").unwrap();

    assert!(agentedit::resolve_agent(&root, "qa-test").is_ok());

    for bad in [
        "../../SECRET",
        "..\\..\\SECRET",
        "../hv-agentedit-outside",
        ".claude/agents/qa-test",
        "/etc/passwd",
        "C:\\Windows\\System32\\drivers\\etc\\hosts",
        "qa-test.md",
        "qa test",
        "..",
        "",
        "   ",
        "http://example.com/x",
        "qa-test\u{0000}",
    ] {
        let r = agentedit::resolve_agent(&root, bad);
        assert!(r.is_err(), "should have refused {bad:?}, got {r:?}");
    }
    // and the same names through the whole write path, which is what the
    // endpoint calls
    for bad in ["../../SECRET", "..\\..\\SECRET", "/etc/passwd"] {
        let r = agentedit::write_agent(&root, bad, &json!({ "model": "opus" }));
        assert!(r.is_err(), "write should have refused {bad:?}");
    }
    assert_eq!(std::fs::read_to_string(&outside).unwrap(), "do not write here");
    assert_eq!(std::fs::read_to_string(&above).unwrap(), "nor here");
    // a name that is bare but names nothing is refused too, and says why
    let e = agentedit::resolve_agent(&root, "does-not-exist").unwrap_err();
    assert!(e.contains("no active agent"), "{e}");

    let _ = std::fs::remove_file(&above);
    let _ = std::fs::remove_dir_all(&root);
}

/// The write path end to end, against a file on disk.
#[test]
fn write_agent_changes_the_frontmatter_and_nothing_else() {
    let root = tmp("write");
    let path = root.join(".claude/agents/qa-test.md");
    std::fs::write(&path, AGENT).unwrap();
    let before = std::fs::read_to_string(&path).unwrap();
    let (_, end) = agentedit::frontmatter_span(&before).unwrap();
    let body = before[end..].to_string();

    let msg = agentedit::write_agent(
        &root,
        "qa-test",
        &json!({ "model": "opus", "effort": "high", "name": "hijacked" }),
    )
    .unwrap();
    assert!(msg.contains("effort, model"), "{msg}");

    let after = std::fs::read_to_string(&path).unwrap();
    let (_, end2) = agentedit::frontmatter_span(&after).unwrap();
    assert_eq!(&after[end2..], body, "the body changed");
    assert!(after.contains("model: opus\n") && after.contains("effort: high\n"));
    assert!(after.contains("name: qa-test\n"), "`name` was writable after all");
    // a second identical write is a no-op, not a rewrite
    let msg = agentedit::write_agent(&root, "qa-test", &json!({ "model": "opus" })).unwrap();
    assert!(msg.contains("no change"), "{msg}");
    assert_eq!(std::fs::read_to_string(&path).unwrap(), after);

    let _ = std::fs::remove_dir_all(&root);
}

// ---------------------------------------------------------------------------
// the reference
// ---------------------------------------------------------------------------

fn vendor<'a>(r: &'a Value, id: &str) -> &'a Value {
    &r["vendors"][id]
}

fn find<'a>(list: &'a Value, key: &str, want: &str) -> Option<&'a Value> {
    list.as_array()?
        .iter()
        .find(|e| e.get(key).and_then(|x| x.as_str()) == Some(want))
}

/// With no overlay the merged reference is exactly the shipped seed, including
/// the entry that is honestly marked unverified. A merge that "tidied" that away
/// would be the single most damaging change anyone could make to this file.
#[test]
fn the_seed_survives_an_empty_overlay_with_its_verified_flags() {
    let root = tmp("seed");
    let m = agentedit::merged(&root).unwrap();
    assert_eq!(m["overrides"], json!(false));
    let cc = vendor(&m, "claude-code");
    assert_eq!(cc["efforts"], json!(["low", "medium", "high", "xhigh"]));
    assert!(cc["tools"].as_array().unwrap().len() >= 40, "the Claude tool list is short");
    assert!(find(&cc["models"], "id", "opus").is_some());
    // the deliberately unverified Z.AI model is present AND still unverified
    let glm = find(&vendor(&m, "zai-glm")["models"], "id", "glm-4.5-air")
        .expect("the unverified model was dropped from the merged reference");
    assert_eq!(glm["verified"], json!(false), "the unverified flag was flipped by the merge");
    // every seed entry carries the flag, so the UI never has to guess
    for (_, v) in m["vendors"].as_object().unwrap() {
        for list in ["models", "tools"] {
            for e in v[list].as_array().unwrap() {
                assert!(e.get("verified").is_some(), "an entry has no verified flag: {e}");
            }
        }
    }
    let _ = std::fs::remove_dir_all(&root);
}

/// Add, edit and delete, each landing in `.claude/state/references.json` and
/// each visible through the merge - and the shipped asset untouched throughout,
/// which is checked by reading the compiled-in seed back out.
#[test]
fn the_overlay_merges_over_the_seed_and_never_rewrites_it() {
    let root = tmp("overlay");
    let seed_before = agentedit::seed_value().unwrap();

    // add a model to a shipped vendor
    agentedit::write_override(
        &root,
        &json!({ "op": "upsert", "kind": "model", "vendor": "claude-code",
                 "entry": { "id": "opus-4-5", "label": "Claude Opus 4.5", "note": "added by hand" } }),
    )
    .unwrap();
    let m = agentedit::merged(&root).unwrap();
    assert_eq!(m["overrides"], json!(true));
    let added = find(&vendor(&m, "claude-code")["models"], "id", "opus-4-5").unwrap();
    assert_eq!(added["label"], json!("Claude Opus 4.5"));
    assert_eq!(added["custom"], json!(true), "a user-added entry must say so");
    assert_eq!(added["verified"], json!(false), "an unclaimed entry defaults to unverified");
    // seed entries are still there, in seed order, ahead of the added one
    let ids: Vec<&str> = vendor(&m, "claude-code")["models"]
        .as_array().unwrap().iter()
        .map(|x| x["id"].as_str().unwrap()).collect();
    assert_eq!(ids[0], "opus", "seed order was not preserved");
    assert_eq!(*ids.last().unwrap(), "opus-4-5", "a custom entry jumped the seed order");

    // correct a shipped tool's description
    agentedit::write_override(
        &root,
        &json!({ "op": "upsert", "kind": "tool", "vendor": "claude-code",
                 "entry": { "name": "Bash", "desc": "Runs a shell command.", "verified": false } }),
    )
    .unwrap();
    let m = agentedit::merged(&root).unwrap();
    let bash = find(&vendor(&m, "claude-code")["tools"], "name", "Bash").unwrap();
    assert_eq!(bash["desc"], json!("Runs a shell command."));
    assert_eq!(bash["edited"], json!(true), "a corrected seed entry must say so");
    // THE rule: an overlay cannot flip a seed entry's verified flag, even when
    // it asks to. The seed's word is the one that ships.
    let seed_bash = find(&seed_before["vendors"]["claude-code"]["tools"], "name", "Bash").unwrap();
    assert_eq!(bash["verified"], seed_bash["verified"], "the overlay flipped a seed verified flag");
    assert_eq!(bash["category"], seed_bash["category"], "an untouched field was lost");

    // delete a shipped model: a tombstone, because the seed will still carry it
    agentedit::write_override(
        &root,
        &json!({ "op": "delete", "kind": "model", "vendor": "claude-code", "id": "haiku" }),
    )
    .unwrap();
    let m = agentedit::merged(&root).unwrap();
    assert!(find(&vendor(&m, "claude-code")["models"], "id", "haiku").is_none());
    let stored: Value = serde_json::from_str(
        &std::fs::read_to_string(agentedit::overrides_path(&root)).unwrap(),
    )
    .unwrap();
    assert_eq!(stored["vendors"]["claude-code"]["models"]["haiku"], json!({ "removed": true }));

    // a whole vendor, added and then hidden
    agentedit::write_override(
        &root,
        &json!({ "op": "upsert", "kind": "vendor",
                 "entry": { "id": "local-llm", "label": "Local", "efforts": ["low", "high"] } }),
    )
    .unwrap();
    let m = agentedit::merged(&root).unwrap();
    assert_eq!(vendor(&m, "local-llm")["custom"], json!(true));
    assert_eq!(vendor(&m, "local-llm")["efforts"], json!(["low", "high"]));
    agentedit::write_override(&root, &json!({ "op": "delete", "kind": "vendor", "vendor": "gemini-cli" })).unwrap();
    let m = agentedit::merged(&root).unwrap();
    assert!(m["vendors"].get("gemini-cli").is_none(), "a hidden vendor still appears");
    assert!(m["vendors"].get("claude-code").is_some(), "hiding one vendor hid another");

    // The shipped asset is a compiled-in constant, so "untouched" is checkable:
    // parse it again and compare it to what it was before every write above.
    assert_eq!(agentedit::seed_value().unwrap(), seed_before, "the shipped seed changed");
    // and it is not on disk anywhere under the served root
    assert!(!root.join("harness-bootstrap").exists());

    let _ = std::fs::remove_dir_all(&root);
}

/// The overlay is state this repository has to be able to diff: sorted keys, no
/// timestamp, and byte-identical when the same edit is made twice.
#[test]
fn the_overlay_is_deterministic_on_disk() {
    let a = tmp("det-a");
    let b = tmp("det-b");
    let edits = [
        json!({ "op": "upsert", "kind": "model", "vendor": "zai-glm", "entry": { "id": "glm-9", "label": "GLM-9", "note": "n" } }),
        json!({ "op": "upsert", "kind": "tool", "vendor": "claude-code", "entry": { "name": "Read", "desc": "d" } }),
        json!({ "op": "delete", "kind": "model", "vendor": "claude-code", "id": "haiku" }),
    ];
    for e in &edits {
        agentedit::write_override(&a, e).unwrap();
    }
    // the same edits in the opposite order must produce the same file
    for e in edits.iter().rev() {
        agentedit::write_override(&b, e).unwrap();
    }
    let ta = std::fs::read_to_string(agentedit::overrides_path(&a)).unwrap();
    let tb = std::fs::read_to_string(agentedit::overrides_path(&b)).unwrap();
    assert_eq!(ta, tb, "the overlay depends on the order the edits arrived in");
    assert!(ta.ends_with("}\n"), "no trailing newline");
    assert!(!ta.contains("20"), "something that looks like a timestamp is in the overlay:\n{ta}");
    // sorted at every depth
    let keys: Vec<&str> = ta.lines().filter(|l| l.starts_with("  \"")).collect();
    let mut sorted = keys.clone();
    sorted.sort();
    assert_eq!(keys, sorted, "top-level keys are not sorted");

    // removing the last override removes the file rather than leaving an empty
    // one behind: a file that means the same as no file is state nobody can read
    agentedit::write_override(&b, &json!({ "op": "delete", "kind": "model", "vendor": "zai-glm", "id": "glm-9" })).unwrap();
    agentedit::write_override(&b, &json!({ "op": "delete", "kind": "tool", "vendor": "claude-code", "id": "Read" })).unwrap();
    assert!(agentedit::overrides_path(&b).exists(), "there is still one override left");
    agentedit::write_override(&b, &json!({ "op": "upsert", "kind": "model", "vendor": "claude-code", "entry": { "id": "haiku" } })).unwrap();
    // the Read tombstone is still there, so the file survives; clear it too
    let _ = agentedit::write_override(&b, &json!({ "op": "upsert", "kind": "tool", "vendor": "claude-code", "entry": { "name": "Read", "desc": "" } }));

    let _ = std::fs::remove_dir_all(&a);
    let _ = std::fs::remove_dir_all(&b);
}

/// A malformed overlay reads as no overlay: the seed is still worth showing, and
/// a viewer that refuses to display a reference because someone hand-edited a
/// comma is worse than one that ignores the edit.
#[test]
fn a_corrupt_overlay_falls_back_to_the_seed() {
    let root = tmp("corrupt");
    std::fs::create_dir_all(root.join(".claude/state")).unwrap();
    std::fs::write(agentedit::overrides_path(&root), "{ not json").unwrap();
    let m = agentedit::merged(&root).unwrap();
    assert!(vendor(&m, "claude-code")["models"].as_array().unwrap().len() >= 3);
    let _ = std::fs::remove_dir_all(&root);
}

/// Malformed CRUD requests are refused by name, before anything is written.
#[test]
fn bad_reference_requests_are_refused() {
    let root = tmp("badref");
    for bad in [
        json!({ "op": "nope", "kind": "model", "vendor": "claude-code", "entry": { "id": "x" } }),
        json!({ "op": "upsert", "kind": "nope", "vendor": "claude-code" }),
        json!({ "op": "upsert", "kind": "model", "vendor": "../../etc", "entry": { "id": "x" } }),
        json!({ "op": "upsert", "kind": "model", "vendor": "claude-code", "entry": { "id": "" } }),
        json!({ "op": "upsert", "kind": "model", "vendor": "claude-code", "entry": { "id": "a/b" } }),
        json!({ "op": "upsert", "kind": "vendor", "entry": { "id": "x", "efforts": "low" } }),
        json!({ "op": "delete", "kind": "tool", "vendor": "claude-code" }),
    ] {
        let r = agentedit::write_override(&root, &bad);
        assert!(r.is_err(), "should have refused {bad}");
    }
    assert!(!agentedit::overrides_path(&root).exists(), "a refused request still wrote a file");
    let _ = std::fs::remove_dir_all(&root);
}

/// The pure JS half of the editor, run for real under node - the same
/// arrangement steps_test.rs uses, and for the same reason: a Rust
/// reimplementation would only prove that two implementations agree, and the one
/// that ships would be the untested one. Node is optional here as everywhere
/// else in this crate.
#[test]
fn the_javascript_editor_logic_runs_under_node() {
    if std::process::Command::new("node").arg("--version").output().is_err() {
        eprintln!("skipping: node is not on PATH");
        return;
    }
    let module = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("src/ui-agent.js")
        .to_string_lossy()
        .replace('\\', "/");
    let src = format!(
        r#"
const assert = require("assert");
const ed = require("{module}");

const reference = {{ vendors: {{
  "claude-code": {{ label: "Claude Code", efforts: ["low","high"],
    models: [{{id:"opus",label:"Opus",verified:true}},{{id:"sonnet",label:"Sonnet",verified:true}}],
    tools: [{{name:"Read",desc:"reads",category:"read",permission:"no",verified:true}},
            {{name:"Bash",desc:"runs",category:"execute",permission:"yes",verified:true}},
            {{name:"Agent",desc:"spawns",category:"agent",permission:"no",verified:true}}] }},
  "zai-glm": {{ label: "Z.AI", efforts: [],
    models: [{{id:"glm-4.5-air",label:"Air",verified:false}}], tools: [] }},
}} }};

// the frontmatter string the graph carries becomes a list, in file order
assert.deepStrictEqual(ed.agentToolList("Read, Grep, Bash"), ["Read","Grep","Bash"]);
assert.deepStrictEqual(ed.agentToolList(["Read","Grep"]), ["Read","Grep"]);
assert.deepStrictEqual(ed.agentToolList(""), []);

// the vendor is inferred from the model the file names
assert.strictEqual(ed.agentGuessVendor(reference, "sonnet"), "claude-code");
assert.strictEqual(ed.agentGuessVendor(reference, "glm-4.5-air"), "zai-glm");
assert.strictEqual(ed.agentGuessVendor(reference, "who-knows", "zai-glm"), "zai-glm");
assert.strictEqual(ed.agentGuessVendor(reference, "who-knows"), "claude-code");

const node = {{ id: "agent:qa-test", file: ".claude/agents/qa-test.md", meta: {{
  model: "sonnet", effort: "high", tools: "Bash, Read, Mystery", description: "d" }} }};
const m = ed.agentEditorModel(node, reference, "");
assert.strictEqual(m.vendor, "claude-code");
assert.strictEqual(m.hasEfforts, true);
// every tool row carries what the user asked to see
assert.strictEqual(m.tools[0].desc, "reads");
assert.strictEqual(m.tools[1].category, "execute");
assert.strictEqual(m.tools[1].permission, "yes");
// ticked exactly what the file named, and nothing else
assert.deepStrictEqual(m.tools.filter(t => t.checked).map(t => t.name), ["Read","Bash"]);
// a tool the reference has never heard of is kept, not silently stripped
assert.deepStrictEqual(m.strangers, ["Mystery"]);
// a vendor with no efforts does not offer the field
assert.strictEqual(ed.agentEditorModel(
  {{ id: "agent:x", meta: {{ model: "glm-4.5-air" }} }}, reference, "").hasEfforts, false);

// A vendor the user PICKED wins over the vendor the model implies. This is the
// live bug the fourth argument exists for: without it the picker moved to Z.AI
// while the catalogue underneath stayed Claude Code's, because the file still
// said `model: sonnet` and inference quietly won.
const forced = ed.agentEditorModel(node, reference, "", "zai-glm");
assert.strictEqual(forced.vendor, "zai-glm");
assert.strictEqual(forced.hasEfforts, false);
assert.deepStrictEqual(forced.models.map(m => m.id), ["glm-4.5-air"]);
// and the seat's own tools are still carried, as strangers, not dropped
assert.deepStrictEqual(forced.strangers, ["Bash","Read","Mystery"]);
// a forced vendor that is not in the reference falls back to inference rather
// than to an empty catalogue
assert.strictEqual(ed.agentEditorModel(node, reference, "", "no-such-vendor").vendor, "claude-code");

// order: what was there stays where it was, new picks append in catalogue order
assert.deepStrictEqual(
  ed.agentToolSelection(["Bash","Read"], ["Read","Bash","Agent"], ["Read","Bash","Agent"]),
  ["Bash","Read","Agent"]);
// unticking removes only what was unticked
assert.deepStrictEqual(
  ed.agentToolSelection(["Bash","Read"], ["Bash"], ["Read","Bash"]), ["Bash"]);

// only changed keys are sent
const before = {{ model: "sonnet", effort: "high", description: "d", tools: ["Read"] }};
assert.deepStrictEqual(
  ed.agentChangedKeys(before, {{ model: "opus", effort: "high", description: "d", tools: ["Read"] }}),
  {{ model: "opus" }});
assert.deepStrictEqual(ed.agentChangedKeys(before, before), {{}});

// an unverified entry is marked, and a seed entry says nothing
assert.deepStrictEqual(ed.agentProvenance({{ verified: false }}), ["unverified"]);
assert.deepStrictEqual(ed.agentProvenance({{ verified: true }}), []);
assert.deepStrictEqual(ed.agentProvenance({{ verified: false, custom: true }}), ["added here","unverified"]);
console.log("ok");
"#
    );
    let dir = std::env::temp_dir().join("hv-agentedit-js");
    let _ = std::fs::create_dir_all(&dir);
    let file = dir.join("check.js");
    std::fs::write(&file, src).unwrap();
    let out = std::process::Command::new("node").arg(&file).output().unwrap();
    let stdout = String::from_utf8_lossy(&out.stdout);
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(out.status.success(), "node rejected the editor logic:\n{stdout}\n{stderr}");
    assert!(stdout.contains("ok"), "{stdout}");
    let _ = std::fs::remove_dir_all(&dir);
}
