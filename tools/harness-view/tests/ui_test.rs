//! The served page is one file with an inline <script>. A syntax error in it
//! does not fail the build, does not fail any other test, and produces a page
//! whose chrome renders perfectly while the canvas stays blank - which is how
//! a broken string literal shipped once already.
//!
//! This shells out to `node --check` rather than pattern-matching the source.
//! A hand-written "does this look balanced" heuristic would have to reimplement
//! JavaScript string, template-literal, comment and regex-literal lexing to be
//! trustworthy, and a heuristic that is wrong in either direction is worse than
//! none: false greens hide real breakage, false reds train people to ignore it.
//! A real parser has neither failure mode. Node is optional here, so the test
//! skips (printing why) when it is absent.

use std::io::Write;
use std::process::Command;

const PAGE: &str = include_str!("../src/ui.html");

fn script_blocks(html: &str) -> Vec<&str> {
    let mut out = Vec::new();
    let mut rest = html;
    while let Some(open) = rest.find("<script") {
        let after = &rest[open..];
        let Some(gt) = after.find('>') else { break };
        let body_start = open + gt + 1;
        let Some(close) = rest[body_start..].find("</script>") else { break };
        let body = &rest[body_start..body_start + close];
        if !body.trim().is_empty() {
            out.push(body);
        }
        rest = &rest[body_start + close..];
    }
    out
}

#[test]
fn embedded_javascript_parses() {
    if Command::new("node").arg("--version").output().is_err() {
        eprintln!("SKIP embedded_javascript_parses: node is not on PATH");
        return;
    }
    let blocks = script_blocks(PAGE);
    assert!(!blocks.is_empty(), "ui.html has no <script> block to check");

    for (i, js) in blocks.iter().enumerate() {
        let mut path = std::env::temp_dir();
        path.push(format!("harness-view-ui-check-{i}.js"));
        {
            let mut f = std::fs::File::create(&path).expect("write temp js");
            f.write_all(js.as_bytes()).expect("write temp js");
        }
        let out = Command::new("node")
            .arg("--check")
            .arg(&path)
            .output()
            .expect("run node --check");
        let _ = std::fs::remove_file(&path);
        assert!(
            out.status.success(),
            "ui.html <script> block {i} is not valid JavaScript:\n{}",
            String::from_utf8_lossy(&out.stderr)
        );
    }
}

/// The page must stay self-contained: a strict offline viewer that silently
/// depends on a CDN is a viewer that breaks on the machine that needs it most.
#[test]
fn page_makes_no_external_requests() {
    for needle in ["http://", "https://", "//cdn", "integrity="] {
        assert!(
            !PAGE.contains(needle),
            "ui.html references an external resource ({needle}); the page must be self-contained"
        );
    }
}

/// The vendored libraries are inlined into the page at serve time by replacing a
/// placeholder. If the placeholder is renamed or a vendor file is truncated by a
/// bad download, the page still serves and still looks fine until someone opens
/// a preview and the renderer is not there. Catch that here instead.
#[test]
fn vendored_libraries_are_present_and_spliced() {
    const MARKED: &str = include_str!("../vendor/marked.min.js");
    const PURIFY: &str = include_str!("../vendor/purify.min.js");

    assert!(
        PAGE.contains("/*__VENDOR__*/"),
        "ui.html lost the /*__VENDOR__*/ placeholder, so the libraries would never be inlined"
    );
    // Enough of each file to prove it is the library and not an error page.
    assert!(MARKED.len() > 20_000, "vendor/marked.min.js looks truncated");
    assert!(PURIFY.len() > 10_000, "vendor/purify.min.js looks truncated");
    assert!(MARKED.contains("marked"), "vendor/marked.min.js is not marked");
    assert!(PURIFY.contains("DOMPurify"), "vendor/purify.min.js is not DOMPurify");

    // The page must actually call them, or the sanitiser could be silently skipped.
    assert!(PAGE.contains("DOMPurify.sanitize"), "the page does not sanitise rendered markdown");
    assert!(PAGE.contains("marked.parse"), "the page does not use the markdown library");
}
