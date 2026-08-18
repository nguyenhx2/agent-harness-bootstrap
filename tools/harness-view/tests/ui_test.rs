//! The served page is one HTML file plus one JavaScript file spliced into it at
//! serve time. A syntax error in that script does not fail the build, does not
//! fail any other test, and produces a page whose chrome renders perfectly while
//! the canvas stays blank - which is how a broken string literal shipped once
//! already.
//!
//! This shells out to `node --check` rather than pattern-matching the source.
//! A hand-written "does this look balanced" heuristic would have to reimplement
//! JavaScript string, template-literal, comment and regex-literal lexing to be
//! trustworthy, and a heuristic that is wrong in either direction is worse than
//! none: false greens hide real breakage, false reds train people to ignore it.
//! A real parser has neither failure mode. Node is optional here, so the test
//! skips (printing why) when it is absent.
//!
//! The UI script used to live inside a <script> block in ui.html. It now lives
//! in src/ui.js so GitHub detects JavaScript and CodeQL analyses it; the checks
//! below follow it there, because a test that kept scanning ui.html for script
//! blocks would still pass - it would just be checking the empty placeholder
//! block and reporting green on nothing.

use std::io::Write;
use std::process::Command;

const PAGE: &str = include_str!("../src/ui.html");
const UI_JS: &str = include_str!("../src/ui.js");
const UI_STEPS_JS: &str = include_str!("../src/ui-steps.js");

fn node_check(name: &str, js: &str) {
    let mut path = std::env::temp_dir();
    path.push(format!("harness-view-ui-check-{name}.js"));
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
        "{name} is not valid JavaScript:\n{}",
        String::from_utf8_lossy(&out.stderr)
    );
}

#[test]
fn ui_javascript_parses() {
    if Command::new("node").arg("--version").output().is_err() {
        eprintln!("SKIP ui_javascript_parses: node is not on PATH");
        return;
    }
    // A truncated or emptied ui.js parses perfectly. Size is the only thing that
    // separates "the UI parses" from "there is no UI left to parse".
    assert!(
        UI_JS.len() > 50_000,
        "src/ui.js is only {} bytes; the whole viewer UI lives there, so it has \
         been truncated or the wrong file is being checked",
        UI_JS.len()
    );
    node_check("ui-js", UI_JS);
    node_check("ui-steps-js", UI_STEPS_JS);
}

/// The page must stay self-contained: a strict offline viewer that silently
/// depends on a CDN is a viewer that breaks on the machine that needs it most.
/// Both halves are checked, because the script is where a fetch would be written.
#[test]
fn page_makes_no_external_requests() {
    for needle in ["http://", "https://", "//cdn", "integrity="] {
        assert!(
            !PAGE.contains(needle),
            "ui.html references an external resource ({needle}); the page must be self-contained"
        );
        assert!(
            !UI_JS.contains(needle),
            "ui.js references an external resource ({needle}); the page must be self-contained"
        );
        assert!(
            !UI_STEPS_JS.contains(needle),
            "ui-steps.js references an external resource ({needle}); the page must be self-contained"
        );
    }
    // A <script src=...> would serve the UI as a second request, which defeats
    // the single-file guarantee even when the URL is same-origin.
    assert!(
        !PAGE.contains("<script src") && !PAGE.contains("<script  src"),
        "ui.html must not load its script over a second request; it is spliced in at serve time"
    );
}

/// The vendored libraries and the UI script are inlined into the page at serve
/// time by replacing placeholders. If a placeholder is renamed or a file is
/// truncated by a bad download, the page still serves and still looks fine until
/// someone opens it and nothing is there. Catch that here instead.
#[test]
fn inlined_sources_are_present_and_spliced() {
    const MARKED: &str = include_str!("../vendor/marked.min.js");
    const PURIFY: &str = include_str!("../vendor/purify.min.js");

    assert!(
        PAGE.contains("/*__VENDOR__*/"),
        "ui.html lost the /*__VENDOR__*/ placeholder, so the libraries would never be inlined"
    );
    assert!(
        PAGE.contains("/*__UI_JS__*/"),
        "ui.html lost the /*__UI_JS__*/ placeholder, so the viewer would serve a page with no UI"
    );
    assert!(
        PAGE.contains("/*__UI_STEPS__*/"),
        "ui.html lost the /*__UI_STEPS__*/ placeholder, so the Command Steps panel would never load"
    );
    // The steps parser must be spliced in before the UI that calls it: a `const`
    // in an earlier classic script is what puts it in scope for a later one.
    assert!(
        PAGE.find("/*__UI_STEPS__*/").unwrap() < PAGE.find("/*__UI_JS__*/").unwrap(),
        "the steps-parser placeholder must come before the UI script placeholder"
    );
    // Enough of each file to prove it is the library and not an error page.
    assert!(MARKED.len() > 20_000, "vendor/marked.min.js looks truncated");
    assert!(PURIFY.len() > 10_000, "vendor/purify.min.js looks truncated");
    assert!(MARKED.contains("marked"), "vendor/marked.min.js is not marked");
    assert!(PURIFY.contains("DOMPurify"), "vendor/purify.min.js is not DOMPurify");

    // The script must actually call them, or the sanitiser could be silently skipped.
    assert!(UI_JS.contains("DOMPurify.sanitize"), "the page does not sanitise rendered markdown");
    assert!(UI_JS.contains("marked.parse"), "the page does not use the markdown library");

    // A literal `</script>` in the script would close the block early once the
    // splice happens, killing the rest of the UI with no build error at all.
    for (name, js) in [("ui.js", UI_JS), ("ui-steps.js", UI_STEPS_JS)] {
        assert!(
            !js.contains("</script"),
            "{name} contains a literal closing script tag, which would terminate the \
             inlined block early and silently delete everything after it"
        );
    }
}
