//! The Command Steps parser, run for real against the fixture command files.
//!
//! The parser is JavaScript, so this shells out to node rather than restating
//! its rules in Rust. A Rust reimplementation asserted against would only prove
//! that two parsers agree, and the one that ships would be the untested one.
//!
//! src/ui-steps.js exists precisely so this is possible: it is pure, so node can
//! require it, while src/ui.js touches `document` on its first line and cannot
//! be required at all. Node is optional here, as everywhere else in this crate,
//! so these skip (printing why) when it is absent.
//!
//! The fixture carries one command of each shape that breaks a naive parser:
//!   deploy.md         two numbered lists under two headings
//!   review-changes.md one plain numbered list, no headings
//!   sync-context.md   no numbered list at all
//! Those three files are the point of the fixture. Do not "tidy" them into the
//! same shape.

use std::path::PathBuf;
use std::process::Command;

fn dir(rel: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(rel)
}

fn have_node() -> bool {
    Command::new("node").arg("--version").output().is_ok()
}

/// Runs `body` with `steps` bound to the module and `read(name)` reading a
/// fixture command. Prints nothing on success; the assertions are in the JS.
fn run_js(body: &str) -> String {
    let module = dir("src/ui-steps.js").to_string_lossy().replace('\\', "/");
    let cmds = dir("tests/fixture/.claude/commands").to_string_lossy().replace('\\', "/");
    let src = format!(
        r#"
const assert = require("assert");
const fs = require("fs");
const steps = require("{module}");
const cmdDir = "{cmds}";
const read = n => fs.readFileSync(cmdDir + "/" + n, "utf8");
{body}
console.log("OK");
"#
    );
    let out = Command::new("node").arg("-e").arg(&src).output().expect("run node");
    assert!(
        out.status.success(),
        "node rejected the assertion:\n{}\n{}",
        String::from_utf8_lossy(&out.stdout),
        String::from_utf8_lossy(&out.stderr)
    );
    String::from_utf8_lossy(&out.stdout).to_string()
}

/// deploy.md has Preconditions and Steps. Merging them renumbers the steps and
/// presents a check to verify as an action to take, which is the failure this
/// whole grouping exists to avoid.
#[test]
fn two_numbered_lists_stay_two_labelled_groups() {
    if !have_node() { eprintln!("SKIP two_numbered_lists_stay_two_labelled_groups: no node"); return; }
    run_js(r#"
const p = steps.parseCommandSteps(read("deploy.md"));
assert.ok(p.hasSteps, "deploy.md must parse as having steps");
const withSteps = p.groups.filter(g => g.steps.length);
assert.strictEqual(withSteps.length, 2, "expected two groups, got " + withSteps.length);
assert.strictEqual(withSteps[0].heading, "Preconditions");
assert.strictEqual(withSteps[1].heading, "Steps");
assert.strictEqual(withSteps[0].steps.length, 3);
assert.strictEqual(withSteps[1].steps.length, 3);
// each list keeps its own numbering rather than being recounted end to end
assert.deepStrictEqual(withSteps[0].steps.map(s => s.num), ["1", "2", "3"]);
assert.deepStrictEqual(withSteps[1].steps.map(s => s.num), ["1", "2", "3"]);
// the sentence introducing the preconditions is kept, not swallowed by a step
assert.ok(withSteps[0].intro.includes("REFUSE the deploy"), "group intro was dropped");
// an indented wrap belongs to the step above it, and loses the indentation it
// carried only because it sat under a "2. " marker - the panel renders step
// text pre-wrap, so keeping it would draw a wrapped sentence as a nested block
assert.ok(withSteps[0].steps[1].text.includes("presumed-green is not green"),
          "the wrapped continuation line was dropped");
assert.ok(/\nand presumed-green is not green/.test(withSteps[0].steps[1].text),
          "the continuation line kept its source indentation: " +
          JSON.stringify(withSteps[0].steps[1].text));
// trailing unnumbered prose attaches to the last step rather than vanishing
assert.ok(withSteps[1].steps[2].text.includes("roll back"),
          "the block after the last step was dropped");
"#);
}

/// Three of the twenty-two shipped commands have no numbered list. An empty
/// panel would read as "this command does nothing".
#[test]
fn a_command_with_no_numbered_list_keeps_its_prose() {
    if !have_node() { eprintln!("SKIP a_command_with_no_numbered_list_keeps_its_prose: no node"); return; }
    run_js(r#"
const raw = read("sync-context.md");
const p = steps.parseCommandSteps(raw);
assert.strictEqual(p.hasSteps, false, "sync-context.md has no numbered list");
assert.ok(p.body.length > 100, "the prose must survive, got " + p.body.length + " bytes");
assert.ok(p.body.includes("Re-read the dependency manifests"), "body content was lost");
// frontmatter is metadata about the command, not part of it
assert.ok(!p.body.includes("description:"), "frontmatter leaked into the body");
// every non-frontmatter line of the file is still there, in order
const want = raw.slice(raw.indexOf("---", 3) + 4).trim();
assert.strictEqual(p.body, want, "the prose was altered rather than shown as written");
"#);
}

/// The plain shape: one list, no headings, and a lead paragraph that is not a step.
#[test]
fn a_plain_numbered_list_parses_as_one_unlabelled_group() {
    if !have_node() { eprintln!("SKIP a_plain_numbered_list_parses_as_one_unlabelled_group: no node"); return; }
    run_js(r#"
const p = steps.parseCommandSteps(read("review-changes.md"));
const withSteps = p.groups.filter(g => g.steps.length);
assert.strictEqual(withSteps.length, 1);
assert.strictEqual(withSteps[0].heading, "/review-changes",
                   "the h1 is the only heading, so it labels the one group");
assert.strictEqual(withSteps[0].steps.length, 3);
assert.ok(withSteps[0].intro.includes("Run the reviewers"), "the lead paragraph was dropped");
"#);
}

/// The annotations. `requireNode` is what separates a reference from a
/// coincidence, and it is asserted in both directions: a backticked word that
/// names a real agent becomes a link, one that does not is left alone.
#[test]
fn steps_are_annotated_with_what_they_touch() {
    if !have_node() { eprintln!("SKIP steps_are_annotated_with_what_they_touch: no node"); return; }
    run_js(r#"
const ids = new Set([
  "agent:code-reviewer", "cmd:review-changes", "cmd:deploy",
  "script:code-graph", "script:graph-html", "rule:agent-guardrails",
]);
const labels = t => steps.touches(t, ids).map(x => x.label);
const linked = t => Object.fromEntries(steps.touches(t, ids).map(x => [x.label, x.id]));

const rc = steps.parseCommandSteps(read("review-changes.md")).groups.filter(g => g.steps.length)[0];
// `git diff` is backticked but names no agent, so it must not become a chip
assert.deepStrictEqual(labels(rc.steps[0].text), [], "a backticked non-agent was annotated");
assert.deepStrictEqual(labels(rc.steps[1].text), ["code-reviewer"]);
assert.strictEqual(linked(rc.steps[1].text)["code-reviewer"], "agent:code-reviewer");
assert.deepStrictEqual(labels(rc.steps[2].text),
  [".claude/scripts/code-graph.py", ".claude/scripts/graph-html.py"]);

const dep = steps.parseCommandSteps(read("deploy.md")).groups.filter(g => g.steps.length);
// `main` is backticked and is not an agent; the rule file is, and links
assert.deepStrictEqual(labels(dep[0].steps[0].text), []);
assert.deepStrictEqual(labels(dep[0].steps[2].text), [".claude/rules/agent-guardrails.md"]);
assert.strictEqual(linked(dep[0].steps[2].text)[".claude/rules/agent-guardrails.md"],
                   "rule:agent-guardrails");
"#);
}

/// A reference with no node behind it is still shown, just not as a control
/// that lies about where it would take you. Rules are the case that motivated
/// this: `.claude/rules/` names a directory and there is nothing to select.
#[test]
fn a_reference_with_no_node_is_kept_as_plain_text() {
    if !have_node() { eprintln!("SKIP a_reference_with_no_node_is_kept_as_plain_text: no node"); return; }
    run_js(r#"
const ids = new Set(["cmd:review-changes"]);
const t = "Apply .claude/rules/ and run .claude/scripts/gone.py, then /review-changes.";
const got = steps.touches(t, ids);
const byLabel = Object.fromEntries(got.map(x => [x.label, x.id]));
assert.strictEqual(byLabel[".claude/rules/"], null, "a directory has nothing to select");
assert.strictEqual(byLabel[".claude/scripts/gone.py"], null, "a missing script must not link");
assert.ok(".claude/scripts/gone.py" in byLabel, "a missing script must still be shown");
assert.strictEqual(byLabel["/review-changes"], "cmd:review-changes");
// the bare-directory pattern must not double-report a rule FILE
const two = steps.touches("see .claude/rules/testing.md", new Set());
assert.deepStrictEqual(two.map(x => x.label), [".claude/rules/testing.md"]);
"#);
}

/// Nothing is dropped. A line that fits no rule comes back as text somewhere,
/// because a step silently missing from a procedure is worse than an ugly one.
#[test]
fn an_unparseable_line_is_kept_rather_than_dropped() {
    if !have_node() { eprintln!("SKIP an_unparseable_line_is_kept_rather_than_dropped: no node"); return; }
    run_js(r#"
// "1)" is not a numbered step by the column-zero "N. " rule, and an indented
// "1." is a nested list inside the step above it. Neither may disappear.
const md = "Intro.\n\n1. First step.\n   1. nested, not a step\n1) also not a step\n\n2. Second step.\n";
const p = steps.parseCommandSteps(md);
const g = p.groups[0];
assert.strictEqual(g.steps.length, 2, "invented or lost a step: " + JSON.stringify(g.steps));
// the nested item keeps its depth relative to the line above it: only the
// COMMON indent of the continuation block is removed
assert.ok(g.steps[0].text.includes("1. nested, not a step"), "the nested item was dropped");
assert.ok(g.steps[0].text.includes("1) also not a step"), "the unparseable line was dropped");
assert.strictEqual(g.intro, "Intro.");
"#);
}

/// The property the whole editor rests on: parsing a command and serializing it
/// straight back must return the file unchanged, byte for byte, for every
/// command in the fixture. A serializer that drifts by one space per save
/// rewrites the repository's commands into its own house style over a few
/// sessions, and every one of those diffs looks deliberate in review.
#[test]
fn serializing_an_untouched_parse_returns_the_file_unchanged() {
    if !have_node() { eprintln!("SKIP serializing_an_untouched_parse_returns_the_file_unchanged: no node"); return; }
    run_js(r#"
for (const name of fs.readdirSync(cmdDir).filter(f => f.endsWith(".md"))) {
  const raw = read(name);
  const out = steps.serializeCommandSteps(steps.parseCommandSteps(raw));
  assert.strictEqual(out, raw, name + " changed when nothing was edited");
}
"#);
}

/// Switching a step off wraps it where it stands and switching it back on
/// restores the original bytes. Anything less makes "off" a one-way door.
#[test]
fn disabling_a_step_is_reversible() {
    if !have_node() { eprintln!("SKIP disabling_a_step_is_reversible: no node"); return; }
    run_js(r#"
const raw = read("review-changes.md");
const p = steps.parseCommandSteps(raw);
const g = p.groups.find(x => x.steps.length);
g.steps[1].disabled = true; g.dirty = true;
const off = steps.serializeCommandSteps(p);
assert.ok(off.includes("<!-- harness-view:disabled-step"), "no quarantine marker was written");

// the disabled step is still parsed, still in place, and marked
const rp = steps.parseCommandSteps(off);
const rg = rp.groups.find(x => x.steps.length);
assert.strictEqual(rg.steps.length, g.steps.length, "a disabled step vanished from the parse");
assert.strictEqual(rg.steps[1].disabled, true, "the disabled step lost its mark");
assert.strictEqual(rg.steps[1].text, g.steps[1].text, "the disabled step's text was altered");

// the steps still standing renumber around it rather than skipping a number
const live = rg.steps.filter(s => !s.disabled).map(s => s.num);
assert.deepStrictEqual(live, ["1", "2"], "live steps did not renumber: " + live);

rg.steps[1].disabled = false; rg.dirty = true;
assert.strictEqual(steps.serializeCommandSteps(rp), raw, "enabling did not restore the original");
"#);
}

/// A section's closing prose belongs to the section, not to whichever step the
/// parser attached it to. deploy.md ends with "On failure: roll back..." after
/// its last step; moving that step must not carry the conclusion up the page.
#[test]
fn reordering_leaves_the_closing_prose_at_the_end() {
    if !have_node() { eprintln!("SKIP reordering_leaves_the_closing_prose_at_the_end: no node"); return; }
    run_js(r#"
const raw = read("deploy.md");
const p = steps.parseCommandSteps(raw);
const g = p.groups.filter(x => x.steps.length).pop();
g.steps.unshift(g.steps.pop());          // last step to the front
g.dirty = true;
const out = steps.serializeCommandSteps(p);

const prose = "On failure: roll back";
assert.ok(out.includes(prose), "the closing prose was lost");
const lines = out.split(/\r?\n/);
const proseAt = lines.findIndex(l => l.startsWith(prose));
const lastStepAt = lines.map((l, i) => (/^\d+\.\s/.test(l) ? i : -1)).filter(i => i >= 0).pop();
assert.ok(proseAt > lastStepAt,
  "the closing prose moved above the last step (prose " + proseAt + ", step " + lastStepAt + ")");
// nothing was invented or dropped on the way
const before = raw.split(/\r?\n/).filter(l => l.trim()).sort();
const after = out.split(/\r?\n/).filter(l => l.trim()).sort();
assert.strictEqual(after.length, before.length, "a line was added or lost by the reorder");
"#);
}

/// A step containing the comment terminator cannot be wrapped in a comment, and
/// the editor has to know that BEFORE offering the control rather than writing a
/// file that ends its own quarantine block early.
#[test]
fn a_step_containing_the_terminator_refuses_to_be_disabled() {
    if !have_node() { eprintln!("SKIP a_step_containing_the_terminator_refuses_to_be_disabled: no node"); return; }
    run_js(r#"
assert.strictEqual(steps.canDisableStep({ text: "ordinary step" }), true);
assert.strictEqual(steps.canDisableStep({ text: "run `sed -e s/a/b/` --> done" }), false);
"#);
}

/// Switching off the FIRST step renumbers what is left starting at 1, and the
/// step that went away keeps the number it had. Renumbering it too wrote `0.`
/// into the file, because the counter names the position among the steps still
/// standing and a disabled first step has none.
#[test]
fn a_disabled_step_keeps_its_number_and_never_becomes_zero() {
    if !have_node() { eprintln!("SKIP a_disabled_step_keeps_its_number_and_never_becomes_zero: no node"); return; }
    run_js(r#"
const raw = read("review-changes.md");
const p = steps.parseCommandSteps(raw);
const g = p.groups.find(x => x.steps.length);
g.steps[0].disabled = true; g.dirty = true;
const out = steps.serializeCommandSteps(p);
assert.ok(!/^0\.\s/m.test(out), "a step was renumbered to 0:\n" + out);

const rg = steps.parseCommandSteps(out).groups.find(x => x.steps.length);
assert.strictEqual(rg.steps[0].num, "1", "the disabled step lost its original number");
assert.deepStrictEqual(rg.steps.filter(s => !s.disabled).map(s => s.num), ["1", "2"],
  "the steps still standing did not renumber from 1");
"#);
}
