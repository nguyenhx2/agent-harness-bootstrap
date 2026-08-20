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
// LF, whatever the checkout did. `.gitattributes` marks *.md as `text`, so a
// Windows clone gets these fixtures with CRLF while a Linux one gets LF - and
// several assertions below pin a fixture excerpt as a "\n"-joined literal. Those
// tests were green on the machine they were written on and red on a fresh
// Windows checkout, which is the worst way for a test to be wrong: it looks like
// the code broke. The parser's own CRLF handling is asserted separately, by
// `serializing_an_untouched_parse_returns_the_file_unchanged`, which reads the
// bytes on disk however they arrived, through `readRaw`.
const readRaw = n => fs.readFileSync(cmdDir + "/" + n, "utf8");
const read = n => readRaw(n).replace(/\r\n/g, "\n");
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
// readRaw, not read: this is the one test that must see whatever line endings
// the checkout produced. A serializer that quietly converted a CRLF working copy
// to LF would rewrite every line of every command on the first save, and only a
// byte comparison against the file as it sits on disk catches that.
for (const name of fs.readdirSync(cmdDir).filter(f => f.endsWith(".md"))) {
  const raw = readRaw(name);
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

/// The property insertion has to satisfy to be allowed near a file a human
/// wrote: write a step, read the file back, get exactly the steps intended in
/// exactly the order intended. Asserted at three positions, because front, middle
/// and end are three different splices into the group's line span and its gaps.
#[test]
fn an_inserted_step_round_trips_at_any_position() {
    if !have_node() { eprintln!("SKIP an_inserted_step_round_trips_at_any_position: no node"); return; }
    run_js(r#"
const raw = read("review-changes.md");
const NEW = "Check `docs/architecture/decisions/` for an ADR that already answers this.";
// Compared on the words, not the leading spaces. A step's DISPLAY text is
// dedented against its own continuation block, and the last step of a section
// owns that section's closing prose - so appending a step legitimately changes
// which step owns the prose and therefore how the one before it dedents. The
// bytes are what must not move, and they are asserted separately below.
const norm = t => t.split("\n").map(l => l.replace(/^[ \t]+/, "")).join("\n");
// step 3's source lines, exactly as the fixture writes them
const KEPT = "3. Rebuild the code graph with python .claude/scripts/code-graph.py and refresh\n" +
             "   the HTML view with python .claude/scripts/graph-html.py.";
assert.ok(raw.includes(KEPT), "the fixture no longer has the wrapped step this pins");

for (const at of [0, 1, 3]) {
  const p = steps.parseCommandSteps(raw);
  const g = p.groups.find(x => x.steps.length);
  const before = g.steps.map(s => norm(s.textBody));
  steps.insertStep(g, at, NEW);
  const out = steps.serializeCommandSteps(p);

  const rg = steps.parseCommandSteps(out).groups.find(x => x.steps.length);
  assert.strictEqual(rg.steps.length, before.length + 1,
    "insert at " + at + " produced " + rg.steps.length + " steps");
  // the intended order, with the new step at the position asked for
  const want = before.slice(0, at).concat([NEW], before.slice(at));
  assert.deepStrictEqual(rg.steps.map(s => norm(s.textBody)), want,
    "insert at " + at + " did not round-trip to the intended order");
  // a list with two steps numbered 3 is worse than no insertion at all
  assert.deepStrictEqual(rg.steps.map(s => s.num),
    want.map((_, i) => String(i + 1)), "the list did not renumber after insert at " + at);
  // and the file grew by exactly the one line the step occupies
  assert.strictEqual(out.split("\n").length, raw.split("\n").length + 1,
    "insert at " + at + " moved lines it had no business moving");
  // the wrapped step's own bytes, indentation included, wherever it now sits
  const moved = KEPT.replace(/^3\./, String(at <= 2 ? 4 : 3) + ".");
  assert.ok(out.includes(moved),
    "insert at " + at + " rewrote the wrapped step:\n" + out);
  // the section's closing prose is still the last thing in the file
  assert.ok(/Reviewing is not approving\.\s*$/.test(out),
    "the closing prose moved on insert at " + at);
}
"#);
}

/// The regression the parser contract exists to prevent. deploy.md's second
/// precondition wraps onto an indented continuation line; adding a step
/// somewhere else in the file must leave that step's bytes exactly as they are -
/// not re-indented, not re-flowed, not promoted into a step of its own.
#[test]
fn inserting_a_step_leaves_a_multi_line_step_byte_identical() {
    if !have_node() { eprintln!("SKIP inserting_a_step_leaves_a_multi_line_step_byte_identical: no node"); return; }
    run_js(r#"
const raw = read("deploy.md");
const WRAPPED = "2. The pipeline on `main` is green and in a terminal state. Pending is not green,\n" +
                "   and presumed-green is not green.";
assert.ok(raw.includes(WRAPPED), "the fixture no longer has the wrapped step this pins");

const p = steps.parseCommandSteps(raw);
const groups = p.groups.filter(x => x.steps.length);
// an edit in the OTHER group entirely
steps.insertStep(groups[1], 1, "Announce the window in the release channel.");
const out = steps.serializeCommandSteps(p);

assert.ok(out.includes(WRAPPED),
  "the wrapped precondition was rewritten by an insert in another group:\n" + out);
// the continuation line is still a continuation, not a step
const rg = steps.parseCommandSteps(out).groups.filter(x => x.steps.length);
assert.strictEqual(rg[0].steps.length, 3, "the untouched group changed step count");
assert.ok(/\nand presumed-green is not green/.test(rg[0].steps[1].text),
  "the continuation line lost or gained indentation");
// the section's closing prose is still last
const lines = out.split("\n");
const proseAt = lines.findIndex(l => l.startsWith("On failure: roll back"));
const lastStep = lines.map((l, i) => (/^\d+\.\s/.test(l) ? i : -1)).filter(i => i >= 0).pop();
assert.ok(proseAt > lastStep, "the closing prose is no longer at the end");
"#);
}

/// A new step's continuation lines are indented, always, and that is a proof
/// rather than a preference: every rule that ENDS a step is anchored at column
/// zero, so text that would have invented a step, a heading or an unbalanced
/// quarantine marker comes back as one step containing those characters.
#[test]
fn an_inserted_step_cannot_invent_steps_out_of_its_own_text() {
    if !have_node() { eprintln!("SKIP an_inserted_step_cannot_invent_steps_out_of_its_own_text: no node"); return; }
    run_js(r#"
const raw = read("review-changes.md");
const p = steps.parseCommandSteps(raw);
const g = p.groups.find(x => x.steps.length);
const n = g.steps.length;
const NASTY = "Do these in order:\n1. first\n2. second\n# not a heading\n--> not a terminator";
steps.insertStep(g, 1, NASTY);
const out = steps.serializeCommandSteps(p);

const rg = steps.parseCommandSteps(out).groups.find(x => x.steps.length);
assert.strictEqual(rg.steps.length, n + 1,
  "the inserted text was read back as " + (rg.steps.length - n) + " steps");
assert.strictEqual(rg.steps[1].textBody, NASTY,
  "the step did not come back as written:\n" + JSON.stringify(rg.steps[1].textBody));
// no heading was invented either, so the group did not split
assert.strictEqual(steps.parseCommandSteps(out).groups.filter(x => x.steps.length).length, 1);

// and text that cannot be a step is refused before it is one
assert.ok(steps.stepTextIssue("   "), "empty text must be refused");
assert.ok(steps.stepTextIssue("\nstarts blank"), "a leading blank line must be refused");
assert.strictEqual(steps.stepTextIssue("ordinary step"), null);
assert.throws(() => steps.insertStep(g, 0, "  "), /needs some text/);
assert.throws(() => steps.insertStep({ steps: [] }, 0, "x"), /already has one/);
"#);
}

/// The separator between steps is the list's own, not a default. board-audit-style
/// lists are tight; a loose list has a blank line. Inserting into either must not
/// convert it to the other, or every save drifts the whole file's spacing.
#[test]
fn an_inserted_step_copies_the_lists_own_spacing() {
    if !have_node() { eprintln!("SKIP an_inserted_step_copies_the_lists_own_spacing: no node"); return; }
    run_js(r#"
const tight = "Intro.\n\n1. one\n2. two\n3. three\n";
const loose = "Intro.\n\n1. one\n\n2. two\n\n3. three\n";
for (const [name, raw, gap] of [["tight", tight, false], ["loose", loose, true]]) {
  const p = steps.parseCommandSteps(raw);
  const g = p.groups.find(x => x.steps.length);
  steps.insertStep(g, 1, "inserted");
  const out = steps.serializeCommandSteps(p);
  const rg = steps.parseCommandSteps(out).groups.find(x => x.steps.length);
  assert.deepStrictEqual(rg.steps.map(s => s.textBody), ["one", "inserted", "two", "three"],
    name + ": " + JSON.stringify(out));
  const blanks = out.split("\n").filter(l => l === "").length;
  const wantBlanks = raw.split("\n").filter(l => l === "").length + (gap ? 1 : 0);
  assert.strictEqual(blanks, wantBlanks,
    name + " list changed its spacing on insert:\n" + JSON.stringify(out));
}
"#);
}

/// The suggestions are what the harness HAS. A list of plausible-looking names
/// is a list of new typos, so every entry traces to a graph node or to a path
/// the server listed, and the contexts are kept apart: a command is offered for
/// `/`, a name for a backtick, a path for a path.
#[test]
fn suggestions_come_only_from_the_graph_and_the_path_list() {
    if !have_node() { eprintln!("SKIP suggestions_come_only_from_the_graph_and_the_path_list: no node"); return; }
    run_js(r#"
const nodes = [
  { id: "agent:code-reviewer", type: "agent", file: ".claude/agents/code-reviewer.md" },
  { id: "cmd:review-changes", type: "command", file: ".claude/commands/review-changes.md" },
  { id: "rule:testing", type: "rule", file: ".claude/rules/testing.md" },
  { id: "hook:guard-main-commit", type: "hook", file: ".claude/hooks/guard-main-commit.ps1" },
  { id: "human", type: "human" },
];
const items = steps.mergeSuggestions(
  steps.suggestionsFromGraph(nodes),
  steps.suggestionsFromPaths(["docs/", "docs/templates/", "docs/templates/ADR.md.template"]));

const offer = (text) => {
  const ctx = steps.completionContext(text, text.length);
  return ctx ? steps.rankSuggestions(items, ctx, 8).map(x => x.value) : null;
};
// a backtick offers names, and only names
assert.deepStrictEqual(offer("Dispatch `code"), ["code-reviewer"]);
assert.ok(!offer("ask `r").some(v => v.charAt(0) === "/"), "a command leaked into the name context");
// a slash offers commands
assert.deepStrictEqual(offer("then run /rev"), ["/review-changes"]);
// a path prefix offers paths, files and directories alike
assert.deepStrictEqual(offer("see docs/temp"),
  ["docs/templates/", "docs/templates/ADR.md.template"]);
assert.ok(offer("apply .claude/ru").includes(".claude/rules/testing.md"));
assert.ok(offer("run .claude/hoo").includes(".claude/hooks/guard-main-commit.ps1"));
// a node with no file and no name class contributes nothing to invent
assert.ok(!items.some(x => x.value === "human"), "a graph node became a name it is not");
// ordinary prose opens nothing at all
assert.strictEqual(steps.completionContext("Assign the special", 18), null);
assert.strictEqual(steps.completionContext("", 0), null);
// nor does a word that is already complete
assert.deepStrictEqual(offer("Dispatch `code-reviewer"), []);
"#);
}

/// A completion replaces the token under the caret and nothing else. This is the
/// difference between an editor and an autocorrect: the surrounding sentence, and
/// anything after the caret, comes back byte for byte.
#[test]
fn a_completion_replaces_only_the_token_at_the_caret() {
    if !have_node() { eprintln!("SKIP a_completion_replaces_only_the_token_at_the_caret: no node"); return; }
    run_js(r#"
const at = (text, caret) => steps.completionContext(text, caret);

// mid-sentence, with text on both sides
const t1 = "Dispatch `code to review, then stop.";
const r1 = steps.applyCompletion(t1, at(t1, 14), { value: "code-reviewer" });
assert.strictEqual(r1.text, "Dispatch `code-reviewer` to review, then stop.");
assert.strictEqual(r1.caret, "Dispatch `code-reviewer`".length);

// the author already closed the backtick: no second one is added
const t2 = "Dispatch `code` now.";
const r2 = steps.applyCompletion(t2, at(t2, 14), { value: "code-reviewer" });
assert.strictEqual(r2.text, "Dispatch `code-reviewer` now.");

// a directory keeps its slash and stays open, so no tick is closed over it
const t3 = "see `docs/temp";
const r3 = steps.applyCompletion(t3, at(t3, t3.length), { value: "docs/templates/" });
assert.strictEqual(r3.text, "see `docs/templates/");

// a command carries its own slash, and the one the author typed is replaced
const t4 = "then run /rev and stop";
const r4 = steps.applyCompletion(t4, at(t4, 13), { value: "/review-changes" });
assert.strictEqual(r4.text, "then run /review-changes and stop");
"#);
}

/// A step's body is sometimes real markdown - the case that motivated this is a
/// routing table, which as pre-wrap text is a wall of pipes. It renders, and
/// rendering is display only: the stored text is not touched by any of it.
#[test]
fn a_step_that_is_a_table_parses_as_a_table_and_the_source_is_untouched() {
    if !have_node() { eprintln!("SKIP a_step_that_is_a_table_parses_as_a_table_and_the_source_is_untouched: no node"); return; }
    run_js(r#"
const md = "Intro.\n\n1. Assign the specialist agent per the routing table:\n\n" +
  "| Work | Agent |\n|------|-------|\n" +
  "| Code review | `code-reviewer` |\n| Tests | `qa-test` |\n\n2. Then stop.\n";
const p = steps.parseCommandSteps(md);
const g = p.groups.find(x => x.steps.length);
assert.strictEqual(g.steps.length, 2, "the table was read as steps");

const blocks = steps.parseStepMarkdown(g.steps[0].textBody);
assert.deepStrictEqual(blocks.map(b => b.kind), ["text", "table"]);
assert.deepStrictEqual(blocks[1].head, ["Work", "Agent"]);
assert.deepStrictEqual(blocks[1].rows, [["Code review", "`code-reviewer`"], ["Tests", "`qa-test`"]]);
assert.strictEqual(steps.stepMarkdownIsRich(blocks), true);

// display only: parsing the step's markdown changed nothing that is written back
assert.strictEqual(steps.serializeCommandSteps(steps.parseCommandSteps(md)), md,
  "the file changed even though only its display was parsed");
// and the step still holds the pipe-delimited source, byte for byte, which is
// what the editor's textarea is filled from
assert.ok(g.steps[0].textBody.includes("|------|-------|"),
  "the stored step text was rewritten by the renderer");

// a plain paragraph is left as the pre-wrap text it has always been
assert.strictEqual(steps.stepMarkdownIsRich(steps.parseStepMarkdown("Run the deploy and stop.")),
                   false);
"#);
}

/// Fall back rather than mangle. A half-parsed table looks authoritative and is
/// wrong; the run comes back as text and renders exactly as it did before.
#[test]
fn markdown_that_is_only_nearly_markdown_falls_back_to_text() {
    if !have_node() { eprintln!("SKIP markdown_that_is_only_nearly_markdown_falls_back_to_text: no node"); return; }
    run_js(r#"
const kinds = t => steps.parseStepMarkdown(t).map(b => b.kind);
// no delimiter row
assert.deepStrictEqual(kinds("| Work | Agent |\n| Code review | x |"), ["text"]);
// delimiter row with the wrong number of columns
assert.deepStrictEqual(kinds("| a | b |\n|---|\n| 1 | 2 |"), ["text"]);
// a ragged body row: a pipe somewhere this reader does not model
assert.deepStrictEqual(kinds("| a | b |\n|---|---|\n| 1 | 2 | 3 |"), ["text"]);
// header and delimiter with no body is not a table
assert.deepStrictEqual(kinds("| a | b |\n|---|---|"), ["text"]);
// but a well-formed one is
assert.deepStrictEqual(kinds("| a | b |\n|---|---|\n| 1 | 2 |"), ["table"]);

// lists, and the boundary where one ends
assert.deepStrictEqual(kinds("Do this:\n- one\n- two\nand then stop."), ["text", "list", "text"]);
const ol = steps.parseStepMarkdown("   1. one\n   2. two")[0];
assert.strictEqual(ol.ordered, true);
assert.deepStrictEqual(ol.items.map(i => i.text), ["one", "two"]);

// underscores are never italics: these files are full of snake_case
const rich = t => steps.stepMarkdownIsRich(steps.parseStepMarkdown(t));
assert.strictEqual(rich("set MAX_RETRIES from the_config value"), false);
assert.strictEqual(rich("run `cargo test`"), true);
assert.strictEqual(rich("this is **required**"), true);

// a link's href is a closed set, because it is the one value a browser acts on
assert.strictEqual(steps.safeHref("https://example.com/x"), "https://example.com/x");
assert.strictEqual(steps.safeHref("http://127.0.0.1:7420/"), "http://127.0.0.1:7420/");
for (const bad of ["javascript:alert(1)", "JavaScript:alert(1)", "data:text/html,x",
                   "docs/specs/05.md", '#anchor', "", "vbscript:x"]) {
  assert.strictEqual(steps.safeHref(bad), null, bad + " was accepted as a link target");
}
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

/// The editor cuts a step into the pieces a person edits differently - prose in
/// a textarea, a table in a grid - and the cut has to be a PARTITION. Every line
/// lands in exactly one part, in order, as the bytes it arrived as, so opening a
/// step and changing nothing gives back the step.
///
/// This is the property the whole editor rests on: `joinStepParts` fills the
/// textarea ui.js's Apply reads, so if the split were lossy, merely LOOKING at a
/// step in the editor would rewrite it.
#[test]
fn splitting_a_step_into_parts_is_the_exact_inverse_of_joining_them() {
    if !have_node() { eprintln!("SKIP splitting_a_step_into_parts_is_the_exact_inverse_of_joining_them: no node"); return; }
    run_js(r#"
const round = t => steps.joinStepParts(steps.splitStepParts(t));
const cases = [
  "One plain sentence.",
  "",
  "Assign the agent:\n\n| Work | Agent |\n|------|-------|\n| Review | `x` |\n| Tests | `y` |",
  // trailing blank lines, ragged spacing, a table between two paragraphs
  "Before.\n\n| a | b |\n|:--|--:|\n| 1 | 2 |\n\nAfter, with   odd   spacing.\n",
  // a run that is only NEARLY a table stays prose and is edited as text
  "| a | b |\n| 1 | 2 |",
  // two tables, separated
  "| a |\n|---|\n| 1 |\n\n| b |\n|---|\n| 2 |",
];
for (const c of cases) {
  assert.strictEqual(round(c), c, "the split lost bytes for: " + JSON.stringify(c));
}

// and for every step of every fixture command, which is the real input
for (const name of ["deploy.md", "review-changes.md", "sync-context.md"]) {
  const p = steps.parseCommandSteps(read(name));
  for (const g of p.groups) for (const st of g.steps) {
    assert.strictEqual(round(st.textBody), st.textBody,
      name + " step " + st.num + " did not survive the split");
  }
}

// the shape the editor branches on
const withTable = steps.splitStepParts("Intro:\n\n| a | b |\n|---|---|\n| 1 | 2 |");
assert.deepStrictEqual(withTable.map(p => p.kind), ["prose", "table"]);
assert.strictEqual(steps.stepPartsHaveTable(withTable), true);
assert.strictEqual(steps.stepPartsHaveTable(steps.splitStepParts("Just prose.")), false);
"#);
}

/// A table nobody edited is written back as the bytes it arrived as, and a table
/// edited in ONE cell comes back with one line changed.
///
/// This is not cosmetic. Before the source lines were held beside the grid,
/// applying the grid re-rendered every line of the real routing table - the
/// header spacing, the delimiter row, every untouched row - so the diff of a
/// one-word correction was the whole table and a reviewer had nothing to look at.
#[test]
fn a_table_edit_rewrites_the_row_it_touched_and_no_other() {
    if !have_node() { eprintln!("SKIP a_table_edit_rewrites_the_row_it_touched_and_no_other: no node"); return; }
    run_js(r#"
const src = "Assign the agent:\n\n" +
  "| Work        | Agent |\n" +
  "|-------------|-------|\n" +
  "| Code review | `code-reviewer` |\n" +
  "| Tests       | `qa-test` |\n" +
  "| Deploy      | `devops` |";
const parts = steps.splitStepParts(src);
const t = parts.find(p => p.kind === "table");

// untouched: the same bytes, delimiter row and column padding included
assert.deepStrictEqual(steps.renderTablePart(t), t.lines,
  "an untouched table was rewritten");

// one cell, on the copy the dialog works on - Cancel must cost nothing
const work = steps.copyTablePart(t);
work.rows[1][1] = "`qa-test` and `debugger`";
steps.syncTablePart(work);
const changed = work.lines.filter((l, i) => l !== t.lines[i]);
assert.strictEqual(changed.length, 1,
  "a one-cell edit rewrote " + changed.length + " lines: " + work.lines.join(" / "));
assert.strictEqual(changed[0], "| Tests | `qa-test` and `debugger` |");
// the copy is a copy
assert.strictEqual(t.rows[1][1], "`qa-test`", "the dialog's grid wrote through to the page");

// and what comes out parses back as the table it claims to be
const back = steps.splitStepParts(steps.joinStepParts([parts[0], work])).find(p => p.kind === "table");
assert.deepStrictEqual(back.head, ["Work", "Agent"]);
assert.deepStrictEqual(back.rows.map(r => r[0]), ["Code review", "Tests", "Deploy"]);
assert.strictEqual(back.rows[1][1], "`qa-test` and `debugger`");
"#);
}

/// Add and remove, for rows and for columns, and the result still reads back as
/// a table. The two refusals are the ones that would turn the grid into pipes the
/// next time the step was opened: a table with no body row and a table with no
/// column both fail `readTable`, so the operation that would produce one is
/// refused rather than applied.
#[test]
fn the_grid_adds_and_removes_and_refuses_to_leave_nothing_behind() {
    if !have_node() { eprintln!("SKIP the_grid_adds_and_removes_and_refuses_to_leave_nothing_behind: no node"); return; }
    run_js(r#"
const reparse = p => steps.splitStepParts(p.lines.join("\n")).find(x => x.kind === "table");
const t = steps.splitStepParts("| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |")[0];

steps.tableAddRow(t, 1);
t.rows[1] = ["new", "row"];
steps.syncTablePart(t);
assert.deepStrictEqual(reparse(t).rows, [["1", "2"], ["new", "row"], ["3", "4"]]);

steps.tableAddColumn(t, 2);
t.head[2] = "c";
steps.syncTablePart(t);
const r = reparse(t);
assert.deepStrictEqual(r.head, ["a", "b", "c"]);
assert.strictEqual(r.rows.every(x => x.length === 3), true);

assert.ok(steps.tableRemoveColumn(t, 2), "removing a spare column was refused");
assert.deepStrictEqual(reparse(t).head, ["a", "b"]);
assert.ok(steps.tableRemoveRow(t, 1), "removing a spare row was refused");
assert.deepStrictEqual(reparse(t).rows, [["1", "2"], ["3", "4"]]);

// the refusals
const one = steps.splitStepParts("| a |\n|---|\n| 1 |")[0];
assert.strictEqual(steps.tableRemoveRow(one, 0), null, "the last row was removed");
assert.strictEqual(steps.tableRemoveColumn(one, 0), null, "the last column was removed");
assert.strictEqual(steps.tableRemoveRow(one, 7), null, "a row that does not exist was removed");

// a new table is a table
const fresh = steps.newTablePart();
const f = reparse(fresh);
assert.strictEqual(f.head.length, 2);
assert.strictEqual(f.rows.length, 1);

// and a table needs a sentence in front of it: a step whose first line is a
// table row serializes as "4. | Work |", which is neither a step nor a table
assert.strictEqual(steps.appendTablePart([]), null);
assert.strictEqual(steps.appendTablePart(steps.splitStepParts("")), null);
const after = steps.splitStepParts("Assign the agent:");
assert.ok(steps.appendTablePart(after), "a table was refused after real prose");
assert.deepStrictEqual(after.map(p => p.kind), ["prose", "table"]);
assert.strictEqual(steps.joinStepParts(after).indexOf("Assign the agent:\n\n|"), 0,
  "the new table did not get the blank line that makes it a block");
"#);
}

/// A pipe inside a cell. Before the grid there was no way to type one, and the
/// reader split on it - so a table with a pipe in a cell came back one column too
/// wide, failed the ragged check, and rendered as pipes. It is escaped on the way
/// out and unescaped on the way back, so the round trip is lossless and a cell can
/// hold `a | b` without ending the row.
#[test]
fn a_pipe_typed_into_a_cell_survives_the_round_trip() {
    if !have_node() { eprintln!("SKIP a_pipe_typed_into_a_cell_survives_the_round_trip: no node"); return; }
    run_js(r#"
const t = steps.splitStepParts("| a | b |\n|---|---|\n| 1 | 2 |")[0];
t.rows[0][0] = "cargo test | tee log";
steps.syncTablePart(t);
assert.strictEqual(t.lines[2], "| cargo test \\| tee log | 2 |");
const back = steps.splitStepParts(t.lines.join("\n")).find(x => x.kind === "table");
assert.deepStrictEqual(back.rows, [["cargo test | tee log", "2"]],
  "the escaped pipe did not read back as one cell");

// a newline pasted into a cell is flattened rather than allowed to end the row
assert.strictEqual(steps.cellSource("one\ntwo"), "one two");
assert.strictEqual(steps.cellSource("  padded  "), "padded");

// a row whose cell holds a pipe is still recognised as unchanged. The source
// spells it escaped and the grid holds it bare; comparing those two forms
// directly reported every such row as edited, so applying the grid rewrote rows
// nobody had touched.
// padded, so that a needless re-render is VISIBLE: re-rendering normalises the
// spacing, and without the padding the rewritten line happens to equal the
// original and the assertion passes while detecting nothing
const same = steps.splitStepParts("| a | b |\n|---|---|\n| x \\| y    |  2 |")[0];
assert.deepStrictEqual(steps.renderTablePart(same), same.lines,
  "a row holding an escaped pipe was rewritten though nothing changed");

// and the reader now handles an escape it did not write, which is what makes a
// hand-written table with a pipe in it drawable at all
const hand = steps.parseStepMarkdown("| cmd | note |\n|---|---|\n| `a \\| b` | pipes |");
assert.deepStrictEqual(hand.map(b => b.kind), ["table"]);
assert.deepStrictEqual(hand[0].rows, [["`a | b`", "pipes"]]);
"#);
}

/// The whole path, end to end: read a file, edit one cell of a step's table,
/// write it back. Everything the panel never showed - the frontmatter, the
/// headings, the prose between the groups, the trailing text - comes back byte
/// for byte, and the only line that moved is the row that was edited.
#[test]
fn editing_a_table_cell_leaves_every_other_line_of_the_file_alone() {
    if !have_node() { eprintln!("SKIP editing_a_table_cell_leaves_every_other_line_of_the_file_alone: no node"); return; }
    run_js(r###"
const md = [
  "---",
  "description: Implement a functional requirement.",
  "---",
  "",
  "Implement **$1**.",
  "",
  "## Steps",
  "",
  "1. Read the FR in `docs/specs/05-functional-requirements.md`.",
  "2. Assign the specialist agent per the routing table:",
  "",
  "| Work        | Agent |",
  "|-------------|-------|",
  "| Code review | `code-reviewer` |",
  "| Tests       | `qa-test` |",
  "",
  "3. Run `/review-changes`.",
  "",
  "On failure: stop and report which acceptance criteria are unmet.",
  "",
].join("\n");

const p = steps.parseCommandSteps(md);
const g = p.groups.find(x => x.steps.length);
const st = g.steps[1];

// exactly what the editor does: split, edit the grid on a copy, apply, join, and
// hand the text back through the one sanctioned setter
const parts = steps.splitStepParts(st.textBody);
const t = parts.find(x => x.kind === "table");
const work = steps.copyTablePart(t);
work.rows[1][1] = "`qa-test`, then `code-reviewer`";
steps.syncTablePart(work);
t.head = work.head; t.align = work.align; t.rows = work.rows; t.src = work.src;
steps.syncTablePart(t);
steps.setStepText(st, steps.joinStepParts(parts));

const out = steps.serializeCommandSteps(p);
const a = md.split("\n"), b = out.split("\n");
assert.strictEqual(a.length, b.length, "the file changed length: " + out);
const moved = a.map((l, i) => l === b[i] ? -1 : i).filter(i => i !== -1);
assert.deepStrictEqual(moved, [14],
  "lines other than the edited row changed: " + JSON.stringify(moved) + " " + out);
assert.strictEqual(b[14], "| Tests | `qa-test`, then `code-reviewer` |");

// the frontmatter, the heading, the intro and the closing prose are untouched
for (const keep of ["description: Implement a functional requirement.", "## Steps",
                    "Implement **$1**.",
                    "On failure: stop and report which acceptance criteria are unmet."]) {
  assert.notStrictEqual(out.indexOf(keep), -1, "the serializer dropped: " + keep);
}
// and the step still numbers 2, because nothing reordered
assert.ok(/^2\. Assign the specialist agent/m.test(out), "the step lost its number");

// opening the editor and changing NOTHING writes nothing
const p2 = steps.parseCommandSteps(md);
const st2 = p2.groups.find(x => x.steps.length).steps[1];
steps.setStepText(st2, steps.joinStepParts(steps.splitStepParts(st2.textBody)));
assert.strictEqual(steps.serializeCommandSteps(p2), md,
  "opening a step in the editor and applying it unchanged rewrote the file");
"###);
}
