// Command Steps: parsing only. No DOM, no fetch, no globals.
//
// This is a separate file from ui.js for one reason: it is the only part of the
// viewer with logic worth testing, and it can only be tested if it can be
// required by node. ui.js touches `document` on its first line, so requiring it
// throws; everything here is pure and runs anywhere. serve.rs splices both files
// into the page, and tests/steps_test.rs runs this one under node against the
// fixture commands. Rendering lives in ui.js (renderCommandSteps).
//
// The panel this feeds is read-only and adds NOTHING to harness-graph.json. That
// schema is written by two scanners in two languages - src/scan.rs and
// harness-bootstrap/assets/scripts/harness-graph.py - which must produce
// byte-identical output on the same repo, and there is no automated parity test
// between them, so every field added to it is a field kept in step by hand. What
// this parses is a file the page already fetches through GET /file. No new
// endpoint, no write path: the only thing harness-view mutates is still
// POST /toggle.
//
// Three shapes in the shipped command set break a naive parser, and each one is
// why a rule below exists:
//   - deploy.md carries TWO numbered lists under separate headings
//     (Preconditions, then Steps). Merged into one list, precondition 1 becomes
//     step 1 and the reader is told to verify a state as if it were an action.
//   - three of the twenty-two shipped commands have no numbered list at all
//     (secret-scan, seed-db, sync-context). An empty panel would read as "this
//     command does nothing", which is the opposite of true.
//   - steps wrap, and the wrapped part is indented. A step is also often
//     followed by an unindented block that still belongs to it.
// Nothing is ever dropped: a line that fits no rule still comes back as text.
"use strict";

// Column zero only. An indented "1." is a nested list inside a step, and
// promoting it would invent steps the command does not have.
const STEP_RE = /^(\d+)\.\s+(.*)$/;
const HEAD_RE = /^#{1,6}\s+(.*)$/;

/// Remove the indentation a step's continuation lines carry only because they
/// sit under a "1. " marker in the source. The panel renders step text with
/// white-space: pre-wrap, so leaving it in makes the second half of a wrapped
/// sentence look like a nested block. Only the COMMON indent goes: a genuinely
/// nested list inside a step keeps its relative depth, which is the thing that
/// made it worth writing as a nested list.
function dedent(text) {
  const lines = text.split("\n");
  if (lines.length < 2) return text;
  let min = Infinity;
  for (const l of lines.slice(1)) {
    if (!l.trim()) continue;                 // a blank line indents nothing
    min = Math.min(min, l.length - l.replace(/^[ \t]+/, "").length);
  }
  if (!Number.isFinite(min) || min === 0) return text;
  return [lines[0]].concat(lines.slice(1).map(l => l.slice(min))).join("\n");
}

/// -> { groups: [{heading, intro, steps: [{num, text}]}], hasSteps, body }
function parseCommandSteps(md) {
  let body = md;
  // The frontmatter is metadata about the command, not an instruction in it,
  // and its `allowed-tools:` line is full of tokens that would otherwise be
  // annotated as things the first step touches.
  if (/^---\s*\n/.test(body)) {
    const end = body.indexOf("\n---", 3);
    if (end !== -1) {
      const nl = body.indexOf("\n", end + 1);
      body = nl === -1 ? "" : body.slice(nl + 1);
    }
  }
  const groups = [];
  let group = { heading: null, intro: [], steps: [] };
  let step = null;
  const close = () => {
    // a section that is a heading and a blank line is not a group
    if (group.steps.length || group.intro.join("\n").trim()) groups.push(group);
  };
  for (const line of body.split(/\r?\n/)) {
    const h = HEAD_RE.exec(line);
    if (h) { close(); group = { heading: h[1].trim(), intro: [], steps: [] }; step = null; continue; }
    const s = STEP_RE.exec(line);
    if (s) { step = { num: s[1], text: s[2] }; group.steps.push(step); continue; }
    // Continuation: an indented wrap, a blank line, or a following unnumbered
    // block. All of it belongs to the step above until the next numbered line
    // or the next heading.
    if (step) { step.text += "\n" + line; continue; }
    // Prose before the first numbered line in this section. Kept, not dropped:
    // it is usually the sentence that says what the list is for.
    group.intro.push(line);
  }
  close();
  for (const g of groups) {
    g.intro = g.intro.join("\n").trim();
    for (const st of g.steps) st.text = dedent(st.text.replace(/\s+$/, ""));
  }
  return { groups: groups, hasSteps: groups.some(g => g.steps.length > 0), body: body.trim() };
}

// What a step touches. `requireNode` is the difference between a reference and
// a coincidence: a backticked word is only an agent name if an agent node by
// that name exists, or every `git diff` in a command would sprout a dead chip.
// Paths are the other way round - `.claude/scripts/x.py` names a file whether
// or not the graph has a node for it, and a command pointing at a script that
// is not there is worth seeing, so those stay and simply do not link.
const TOUCH = [
  { re: /\.claude\/scripts\/([A-Za-z0-9._-]+)\.py/g,
    id: m => "script:" + m[1], text: m => m[0], requireNode: false },
  { re: /\.claude\/rules\/([A-Za-z0-9._-]+)\.md/g,
    id: m => "rule:" + m[1], text: m => m[0], requireNode: false },
  // A bare `.claude/rules/` is how most commands cite the rule set, and it names
  // a directory, so there is nothing to jump to. The lookahead keeps it from
  // also firing on the file form above and showing the same reference twice.
  { re: /\.claude\/rules\/(?![A-Za-z0-9._-]+\.md)/g,
    id: () => null, text: () => ".claude/rules/", requireNode: false },
  // No dot in either name class, deliberately. Command and agent names are file
  // basenames - lowercase, hyphens, no extension - and a dot in the class ate
  // the sentence-ending period of "then run /review-changes.", turning a real
  // reference into "cmd:review-changes." and silently dropping the chip.
  { re: /(?:^|[\s`(\[])\/([a-z0-9][a-z0-9_-]*)/g,
    id: m => "cmd:" + m[1], text: m => "/" + m[1], requireNode: true },
  { re: /`([A-Za-z0-9][A-Za-z0-9_-]*)`/g,
    id: m => "agent:" + m[1], text: m => m[1], requireNode: true },
];

/// `ids` is a Set of node ids from the loaded graph. Passing it in rather than
/// reading a global is what makes this testable without a browser.
/// -> [{label, id}] where id is null when there is no node to select.
function touches(text, ids) {
  const found = [];
  for (const t of TOUCH) {
    t.re.lastIndex = 0;
    let m;
    while ((m = t.re.exec(text)) !== null) {
      // a pattern that can match empty would loop here forever
      if (m.index === t.re.lastIndex) t.re.lastIndex++;
      const id = t.id(m);
      const known = !!id && ids.has(id);
      if (t.requireNode && !known) continue;
      found.push({ at: m.index, label: t.text(m), id: known ? id : null });
    }
  }
  // first mention wins, and the order is the order the step reads in
  found.sort((a, b) => a.at - b.at);
  const seen = new Set(), out = [];
  for (const f of found) {
    if (seen.has(f.label)) continue;
    seen.add(f.label);
    out.push({ label: f.label, id: f.id });
  }
  return out;
}

// Node requires this file; the browser does not have `module` and skips the
// line. There is no bundler here and there must not be one: the page is served
// as a single response with these sources spliced in.
if (typeof module !== "undefined" && module.exports) {
  module.exports = { parseCommandSteps, touches };
}
