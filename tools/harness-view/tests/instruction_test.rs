//! Instruction files as graph nodes, and the write path that edits them.
//!
//! The containment half of this file talks to a REAL server over a real socket
//! rather than calling the resolver directly. That is deliberate: the refusals
//! that matter here are not "does `build()` reject `..`" - a unit test in
//! instruction.rs already proves that - but "does the running endpoint refuse a
//! cross-origin write and a traversal, with the file still untouched afterwards".
//! A gate is not trusted until it has been seen to fail, and the thing that has
//! to fail is the endpoint, not a function it happens to call.

use harness_view::{assess, instruction, scan, serve};
use serde_json::Value;
use std::fs;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

const AGENTS_MD: &str = "# AGENTS.md - fixture\n\
\n\
The enforceable rules live in `.claude/rules/agent-guardrails.md` and\n\
`.claude/rules/testing.md`.\n\
\n\
The roster: `orchestrator` dispatches, `app-dev` implements.\n\
\n\
### How much process a change gets\n\
\n\
| Tier | The change | Who runs it | What it adds |\n\
|------|------------|-------------|--------------|\n\
| **Direct** | one module, reversible | the owning agent, called straight | the agent proves each criterion itself |\n\
| **Standard** | one domain, several files | the owning agent | a hand check of every criterion |\n\
| **Guarded** | two or more domains, or schema, auth, money | `orchestrator` - one at a time | the full flow below |\n\
\n\
Choosing a heavier tier than the change needs is a defect, not caution.\n";

fn tmp(name: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!("hv-instr-{name}"));
    let _ = fs::remove_dir_all(&d);
    fs::create_dir_all(&d).unwrap();
    d
}

fn write(root: &Path, rel: &str, body: &str) {
    let p = root.join(rel);
    fs::create_dir_all(p.parent().unwrap()).unwrap();
    fs::write(p, body).unwrap();
}

/// A repository carrying one instruction file of every shape the table knows.
fn fixture(root: &Path) {
    write(root, "AGENTS.md", AGENTS_MD);
    write(root, "CLAUDE.md", "# CLAUDE.md\n\n@AGENTS.md\n\nThe Claude-only surface.\n");
    write(root, "GEMINI.md", "# GEMINI.md\n\nAntigravity reads this.\n");
    write(root, ".cursor/rules/agent-guardrails.mdc", "---\nalwaysApply: true\n---\n# ported\n");
    write(root, ".kiro/steering/product.md", "# product\n");
    write(root, ".agents/rules/style.md", "# style\n");
    write(root, ".agent/rules/legacy.md", "# legacy\n");
    // things that must NOT become instruction nodes
    write(root, "README.md", "not a contract\n");
    write(root, ".cursor/hooks.json", "{}\n");
    write(root, ".cursor/rules/notes.txt", "wrong extension\n");
    // enough harness for the rest of the graph to exist
    write(root, ".claude/settings.json", "{\n  \"permissions\": {}\n}\n");
    write(root, ".claude/rules/agent-guardrails.md", "# guardrails\n");
    write(root, ".claude/rules/testing.md", "---\npaths:\n  - \"tests/**\"\n---\n# testing\n");
    write(root, ".claude/agents/orchestrator.md",
          "---\nname: orchestrator\nmodel: opus\neffort: high\ntools: Read, Agent\n---\nbody\n");
    write(root, ".claude/agents/app-dev.md",
          "---\nname: app-dev\nmodel: sonnet\neffort: medium\ntools: Read, Write\n---\nbody\n");
}

fn nodes_of(g: &Value, t: &str) -> Vec<Value> {
    g["nodes"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|n| n["type"] == t)
        .cloned()
        .collect()
}

fn node(g: &Value, id: &str) -> Option<Value> {
    g["nodes"].as_array().unwrap().iter().find(|n| n["id"] == id).cloned()
}

fn has_edge(g: &Value, from: &str, to: &str, ty: &str) -> bool {
    g["edges"]
        .as_array()
        .unwrap()
        .iter()
        .any(|e| e["from"] == from && e["to"] == to && e["type"] == ty)
}

#[test]
fn every_shape_in_the_table_becomes_a_node_and_nothing_else_does() {
    let d = tmp("nodes");
    fixture(&d);
    let g = scan::scan(&d);

    let ids: Vec<String> = nodes_of(&g, "instruction")
        .iter()
        .map(|n| n["id"].as_str().unwrap().to_string())
        .collect();
    for want in [
        "instr:agents",
        "instr:claude",
        "instr:gemini",
        "instr:cursor-rules/agent-guardrails",
        "instr:kiro-steering/product",
        "instr:antigravity-rules/style",
        "instr:antigravity-rules-legacy/legacy",
    ] {
        assert!(ids.contains(&want.to_string()), "missing {want}: {ids:?}");
    }
    assert_eq!(ids.len(), 7, "something extra became an instruction node: {ids:?}");

    // The label is the path, because that is the identity of these: two tools
    // can read files whose names are identical in different directories.
    let a = node(&g, "instr:agents").unwrap();
    assert_eq!(a["label"], "AGENTS.md");
    assert_eq!(a["file"], "AGENTS.md");
    assert_eq!(a["disabled"], false);
    // the evidence travels with the node
    assert!(a["meta"]["tools"].as_array().unwrap().iter().any(|t| t == "Codex"));
    assert_eq!(a["meta"]["verified"], true);
    assert!(!a["meta"]["source"].as_str().unwrap().is_empty());
    // and the write path's key and name, never a path
    assert_eq!(a["edit"]["key"], "agents");
    assert_eq!(a["edit"]["name"], "");
    let c = node(&g, "instr:cursor-rules/agent-guardrails").unwrap();
    assert_eq!(c["edit"]["key"], "cursor-rules");
    assert_eq!(c["edit"]["name"], "agent-guardrails");

    // settings.json is not an instruction node, but it IS editable by the same
    // path - that is the whole reason it sits in the same table.
    let s = node(&g, "settings").unwrap();
    assert_eq!(s["type"], "settings");
    assert_eq!(s["edit"]["key"], "settings");

    let _ = fs::remove_dir_all(&d);
}

#[test]
fn the_tier_table_reaches_the_graph_and_routes_only_the_seat_it_names() {
    let d = tmp("tiers");
    fixture(&d);
    let g = scan::scan(&d);

    let a = node(&g, "instr:agents").unwrap();
    let tiers = a["tiers"].as_array().unwrap();
    assert_eq!(tiers.len(), 3, "{tiers:?}");
    assert_eq!(tiers[0]["tier"], "Direct");
    assert_eq!(tiers[2]["tier"], "Guarded");
    assert!(tiers[2]["adds"].as_str().unwrap().contains("full flow"));

    // The Guarded row names orchestrator, so orchestrator is badged Guarded and
    // the contract routes to it.
    let orch = node(&g, "agent:orchestrator").unwrap();
    assert_eq!(orch["meta"]["tier"], "Guarded");
    assert!(has_edge(&g, "instr:agents", "agent:orchestrator", "routes"));

    // The Direct and Standard rows say "the owning agent" and name nobody, so
    // app-dev gets no tier. Inventing one here would be exactly the guess the
    // table exists to replace.
    let app = node(&g, "agent:app-dev").unwrap();
    assert!(app["meta"].get("tier").is_none(), "app-dev must not be assigned a tier");
    assert!(!has_edge(&g, "instr:agents", "agent:app-dev", "routes"));

    // A file with no table carries no `tiers` key at all
    assert!(node(&g, "instr:gemini").unwrap().get("tiers").is_none());

    let _ = fs::remove_dir_all(&d);
}

#[test]
fn the_contract_is_wired_to_what_it_actually_cites() {
    let d = tmp("edges");
    fixture(&d);
    let g = scan::scan(&d);

    // CLAUDE.md says @AGENTS.md, so it imports it
    assert!(has_edge(&g, "instr:claude", "instr:agents", "imports"));
    assert!(!has_edge(&g, "instr:agents", "instr:claude", "imports"));
    // AGENTS.md cites two rules by path
    assert!(has_edge(&g, "instr:agents", "rule:agent-guardrails", "cites"));
    assert!(has_edge(&g, "instr:agents", "rule:testing", "cites"));
    // and briefs the two seats it names
    assert!(has_edge(&g, "instr:agents", "agent:orchestrator", "briefs"));
    assert!(has_edge(&g, "instr:agents", "agent:app-dev", "briefs"));
    // GEMINI.md names nobody, so it briefs nobody
    assert!(!has_edge(&g, "instr:gemini", "agent:app-dev", "briefs"));

    let _ = fs::remove_dir_all(&d);
}

/// Invariant 4: nothing generated carries a timestamp, and two scans of one tree
/// are byte-identical. Instruction nodes read files off disk, so they are the
/// obvious place for an mtime to sneak in.
#[test]
fn the_graph_stays_deterministic_with_instruction_nodes_in_it() {
    let d = tmp("determinism");
    fixture(&d);
    let one = scan::to_canonical_json(&scan::scan(&d));
    std::thread::sleep(Duration::from_millis(20));
    let two = scan::to_canonical_json(&scan::scan(&d));
    assert_eq!(one, two, "two scans of one tree disagreed");
    for bad in ["timestamp", "scanned_at", "generated", "mtime", "modified"] {
        assert!(!one.to_lowercase().contains(bad), "the graph carries `{bad}`");
    }
    let _ = fs::remove_dir_all(&d);
}

#[test]
fn a_repo_with_no_contract_and_a_repo_with_no_tiers_are_both_reported() {
    let d = tmp("assess");
    fixture(&d);
    let a = assess::assess(&d, &scan::scan(&d));
    let checks: Vec<&str> = a["findings"]
        .as_array()
        .unwrap()
        .iter()
        .map(|f| f["check"].as_str().unwrap_or(""))
        .collect();
    assert!(!checks.contains(&"instruction-contract"), "{checks:?}");
    assert!(!checks.contains(&"instruction-tiers"), "{checks:?}");

    // Mutation: take the tier table away and the info finding must appear. A
    // check that never fires is indistinguishable from a clean repository.
    fs::write(d.join("AGENTS.md"), "# AGENTS.md\n\nNo table here.\n").unwrap();
    let a = assess::assess(&d, &scan::scan(&d));
    let checks: Vec<&str> = a["findings"]
        .as_array()
        .unwrap()
        .iter()
        .map(|f| f["check"].as_str().unwrap_or(""))
        .collect();
    assert!(checks.contains(&"instruction-tiers"), "{checks:?}");

    // Mutation: take the contract away entirely and the medium finding appears.
    fs::remove_file(d.join("AGENTS.md")).unwrap();
    let a = assess::assess(&d, &scan::scan(&d));
    let f = a["findings"]
        .as_array()
        .unwrap()
        .iter()
        .find(|f| f["check"] == "instruction-contract")
        .cloned()
        .expect("a repo with no AGENTS.md must be reported");
    assert_eq!(f["severity"], "medium");

    let _ = fs::remove_dir_all(&d);
}

// --------------------------------------------------------------- the endpoint

/// A port nothing is listening on, found by binding and letting go.
fn free_port() -> u16 {
    let l = TcpListener::bind(("127.0.0.1", 0)).unwrap();
    let p = l.local_addr().unwrap().port();
    drop(l);
    p
}

struct Live {
    port: u16,
}

impl Live {
    /// Start a server and wait for it to accept.
    ///
    /// The retry is not defensive padding. `free_port` releases the port before
    /// `serve` claims it, and cargo runs these tests in parallel threads of one
    /// process, so two of them can be handed the same number in that window;
    /// the loser's `Server::http` fails, its thread ends silently, and the test
    /// then waits out its whole timeout for a server that was never going to
    /// come up. That is what it did - three tests, two ten-second timeouts - and
    /// the fix is to notice and take another port rather than to wait longer.
    fn start(root: &Path) -> Live {
        // One test at a time through the pick-and-bind window, which is what
        // makes the collision above rare enough that the retry almost never
        // runs. Both are here on purpose: the lock removes the races this
        // process causes, the retry survives whatever else on the machine
        // happens to take the port between the release and the bind.
        static GATE: std::sync::Mutex<()> = std::sync::Mutex::new(());
        let _held = GATE.lock().unwrap_or_else(|e| e.into_inner());
        for _ in 0..8 {
            let port = free_port();
            let r = root.to_path_buf();
            std::thread::spawn(move || {
                let _ = serve::serve(r, port);
            });
            // Wait for the listener rather than sleeping a guessed amount: a
            // fixed sleep is either slower than it needs to be or flaky on a
            // loaded box.
            let deadline = Instant::now() + Duration::from_secs(3);
            while Instant::now() < deadline {
                if TcpStream::connect(("127.0.0.1", port)).is_ok() {
                    return Live { port };
                }
                std::thread::sleep(Duration::from_millis(10));
            }
        }
        panic!("the test server never came up on any of eight ports");
    }

    /// One raw request, one raw response. Written by hand because the point is
    /// to control the exact headers a browser would or would not send.
    fn raw(&self, head: &str, body: &str) -> (u16, String) {
        let mut s = TcpStream::connect(("127.0.0.1", self.port)).unwrap();
        s.set_read_timeout(Some(Duration::from_secs(10))).unwrap();
        let req = format!(
            "{head}\r\nHost: 127.0.0.1:{}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
            self.port,
            body.len()
        );
        s.write_all(req.as_bytes()).unwrap();
        s.flush().unwrap();
        let mut out = String::new();
        let _ = s.read_to_string(&mut out);
        let status: u16 = out
            .split_whitespace()
            .nth(1)
            .and_then(|c| c.parse().ok())
            .unwrap_or(0);
        let text = out.split_once("\r\n\r\n").map(|(_, b)| b.to_string()).unwrap_or_default();
        (status, text)
    }

    fn post(&self, path: &str, extra: &str, body: &str) -> (u16, String) {
        let head = format!(
            "POST {path} HTTP/1.1\r\nContent-Type: application/json{extra}",
        );
        self.raw(&head, body)
    }

    fn get(&self, path: &str) -> (u16, String) {
        self.raw(&format!("GET {path} HTTP/1.1"), "")
    }
}

fn json_body(root: &Path, key: &str, name: &str, content: &str) -> String {
    serde_json::json!({
        "root": root.display().to_string(),
        "key": key,
        "name": name,
        "content": content,
    })
    .to_string()
}

#[test]
fn the_running_endpoint_refuses_a_traversal_and_a_cross_origin_write() {
    let d = tmp("live-refusals");
    fixture(&d);
    // The thing a traversal would want, one level above the repository - and
    // deliberately given the extension the write path appends, so that a
    // traversal which got through would REACH it. An outside file the resolver
    // could never have named is not a target, and a test that used one would
    // pass for the wrong reason: it would be asserting "no such file", not
    // "refused". That is exactly how this test was wrong on the first attempt,
    // and turning the character check off did not turn it red.
    let outside = d.parent().unwrap().join("hv-instr-outside-secret.mdc");
    fs::write(&outside, "# do not touch\n").unwrap();
    let outside_md = d.parent().unwrap().join("hv-instr-outside-secret.md");
    fs::write(&outside_md, "# do not touch\n").unwrap();
    let before_outside = fs::read(&outside).unwrap();
    let before_outside_md = fs::read(&outside_md).unwrap();
    let before_agents = fs::read(d.join("AGENTS.md")).unwrap();

    let live = Live::start(&d);

    // --- cross-origin, three ways a browser announces it ------------------
    let (code, txt) = live.post(
        "/instruction",
        "\r\nOrigin: http://evil.example",
        &json_body(&d, "agents", "", "# owned\n"),
    );
    assert_eq!(code, 403, "a foreign Origin must be refused: {txt}");
    assert!(txt.contains("cross-origin"), "{txt}");

    let (code, txt) = live.post(
        "/instruction",
        "\r\nSec-Fetch-Site: cross-site",
        &json_body(&d, "agents", "", "# owned\n"),
    );
    assert_eq!(code, 403, "a cross-site fetch must be refused: {txt}");

    // A form post carries no JSON content type, and a form is what a
    // cross-origin page can send without a preflight at all.
    let (code, _) = live.raw(
        "POST /instruction HTTP/1.1\r\nContent-Type: application/x-www-form-urlencoded",
        &json_body(&d, "agents", "", "# owned\n"),
    );
    assert_eq!(code, 403, "a non-JSON content type must be refused");

    // --- traversal, through every field that could carry one ---------------
    for (key, name) in [
        // each of these lands on a real file outside the repo if it gets through
        ("cursor-rules", "../../../hv-instr-outside-secret"),
        ("cursor-rules", "..\\..\\..\\hv-instr-outside-secret"),
        ("kiro-steering", "../../../hv-instr-outside-secret"),
        ("cursor-rules", ".."),
        ("kiro-steering", "/etc/passwd"),
        ("../../AGENTS", ""),
        ("agents/../../x", ""),
        ("nope", ""),
    ] {
        let (code, txt) = live.post("/instruction", "", &json_body(&d, key, name, "# owned\n"));
        assert_eq!(code, 400, "key={key:?} name={name:?} should be refused, got {txt}");
        // "refused", never "no such file": the second one means the shape got
        // past the check and was stopped only by what happened to be on disk.
        assert!(
            txt.starts_with("refused"),
            "key={key:?} name={name:?} was not refused by shape: {txt}"
        );
    }

    // Nothing moved. This is the assertion that actually matters: a refusal
    // that still wrote the file would report itself as a refusal.
    assert_eq!(fs::read(&outside).unwrap(), before_outside, "a file outside the repo was written");
    assert_eq!(fs::read(&outside_md).unwrap(), before_outside_md, "a file outside the repo was written");
    assert_eq!(fs::read(d.join("AGENTS.md")).unwrap(), before_agents, "AGENTS.md was written");

    // --- the reader is contained too --------------------------------------
    let enc = |p: &str| p.replace('/', "%2F").replace('\\', "%5C").replace(':', "%3A");
    let root_q = format!("&root={}", enc(&d.display().to_string()));
    for bad in ["README.md", "../hv-instr-outside-secret.md", ".cursor/hooks.json", ".cursor/rules/notes.txt"] {
        let (code, txt) = live.get(&format!("/file?path={}{root_q}", enc(bad)));
        assert_eq!(code, 400, "GET /file must refuse {bad}, got {code} {txt}");
    }
    // and it does read the instruction files, or the refusals above would be
    // proving nothing more than a broken endpoint
    let (code, txt) = live.get(&format!("/file?path=AGENTS.md{root_q}"));
    assert_eq!(code, 200, "{txt}");
    assert!(txt.contains("How much process"), "{txt}");

    let _ = fs::remove_file(&outside);
    let _ = fs::remove_file(&outside_md);
    let _ = fs::remove_dir_all(&d);
}

#[test]
fn a_real_edit_lands_and_leaves_the_rest_of_the_file_byte_identical() {
    let d = tmp("live-write");
    fixture(&d);
    let live = Live::start(&d);

    let before = fs::read_to_string(d.join("AGENTS.md")).unwrap();
    let after_want = before.replace("app-dev` implements", "app-dev` implements the work");
    assert_ne!(before, after_want, "the fixture edit changed nothing");

    let (code, txt) = live.post("/instruction", "", &json_body(&d, "agents", "", &after_want));
    assert_eq!(code, 200, "{txt}");
    assert!(txt.contains("wrote AGENTS.md"), "{txt}");

    let on_disk = fs::read_to_string(d.join("AGENTS.md")).unwrap();
    assert_eq!(on_disk, after_want, "the file is not what was sent");
    // Everything that was not the edited line is byte-identical, line for line.
    let a: Vec<&str> = before.split_inclusive('\n').collect();
    let b: Vec<&str> = on_disk.split_inclusive('\n').collect();
    assert_eq!(a.len(), b.len(), "the line count changed");
    let differing: Vec<usize> = (0..a.len()).filter(|i| a[*i] != b[*i]).collect();
    assert_eq!(differing.len(), 1, "more than one line changed: {differing:?}");

    // Saving the same bytes twice is a no-op, not a second write.
    let (code, txt) = live.post("/instruction", "", &json_body(&d, "agents", "", &after_want));
    assert_eq!(code, 200, "{txt}");
    assert!(txt.contains("unchanged"), "{txt}");

    // An empty save is a deletion wearing an edit's clothes, and is refused.
    let (code, txt) = live.post("/instruction", "", &json_body(&d, "agents", "", "   \n"));
    assert_eq!(code, 400, "{txt}");
    assert_eq!(fs::read_to_string(d.join("AGENTS.md")).unwrap(), after_want);

    // settings.json must still parse afterwards: a settings file that does not
    // unregisters every hook in it and says nothing.
    let (code, txt) = live.post("/instruction", "", &json_body(&d, "settings", "", "{ not json"));
    assert_eq!(code, 400, "{txt}");
    assert!(txt.contains("valid JSON"), "{txt}");
    assert_eq!(
        fs::read_to_string(d.join(".claude/settings.json")).unwrap(),
        "{\n  \"permissions\": {}\n}\n"
    );
    let (code, txt) = live.post(
        "/instruction",
        "",
        &json_body(&d, "settings", "", "{\n  \"permissions\": { \"deny\": [] }\n}\n"),
    );
    assert_eq!(code, 200, "{txt}");

    let _ = fs::remove_dir_all(&d);
}

/// A CRLF file edited through a browser textarea comes back LF, because that is
/// what the DOM does. Without the line-ending restore, a one-word edit to a
/// CRLF AGENTS.md would rewrite every line in it - the diff would be the whole
/// file and the promise "everything you did not change is untouched" would be
/// false on every Windows checkout.
#[test]
fn a_crlf_file_stays_crlf_through_a_write() {
    let d = tmp("live-crlf");
    fixture(&d);
    let crlf = AGENTS_MD.replace('\n', "\r\n");
    fs::write(d.join("AGENTS.md"), &crlf).unwrap();
    let live = Live::start(&d);

    // exactly what a textarea would post back after a one-word edit
    let posted = crlf.replace("\r\n", "\n").replace("a defect", "a defect here");
    let (code, txt) = live.post("/instruction", "", &json_body(&d, "agents", "", &posted));
    assert_eq!(code, 200, "{txt}");

    let on_disk = fs::read_to_string(d.join("AGENTS.md")).unwrap();
    assert!(on_disk.contains("a defect here"), "the edit did not land");
    assert_eq!(
        on_disk.matches("\r\n").count(),
        crlf.matches("\r\n").count(),
        "the line endings were rewritten"
    );
    assert!(!on_disk.contains("\n\n\r"), "a lone LF survived");
    // and the untouched lines are still byte-for-byte what they were
    let a: Vec<&str> = crlf.split_inclusive("\r\n").collect();
    let b: Vec<&str> = on_disk.split_inclusive("\r\n").collect();
    assert_eq!(a.len(), b.len());
    assert_eq!((0..a.len()).filter(|i| a[*i] != b[*i]).count(), 1);

    let _ = fs::remove_dir_all(&d);
}

/// The table is the documentation. If an entry ever loses its source, or claims
/// a tool with no evidence behind it, that is the failure this repo marks
/// explicitly rather than shipping quietly.
#[test]
fn every_entry_in_the_table_carries_its_evidence() {
    for s in instruction::FILES {
        assert!(!s.key.is_empty());
        assert!(!s.path.is_empty(), "{}", s.key);
        assert!(!s.tools.is_empty(), "{} names no tool", s.key);
        assert!(!s.source.is_empty(), "{} cites no source", s.key);
        // A path with no evidence must be MARKED, never merely present: the UI
        // reads this flag to say so.
        if !s.verified {
            assert!(
                !s.note.is_empty(),
                "{} is unverified and must say why in its note",
                s.key
            );
        }
        // No entry's path may nest inside another's, or `from_rel` would match
        // the wrong one and rebuild the wrong file.
        for other in instruction::FILES {
            if other.key == s.key {
                continue;
            }
            assert!(
                !s.path.starts_with(&format!("{}/", other.path)),
                "{} nests inside {}",
                s.key,
                other.key
            );
        }
    }
}
