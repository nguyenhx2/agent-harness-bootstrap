// Command Steps: parsing only. No DOM, no fetch, no globals.
//
// This is a separate file from ui.js for one reason: it is the only part of the
// viewer with logic worth testing, and it can only be tested if it can be
// required by node. ui.js touches `document` on its first line, so requiring it
// throws; everything here is pure and runs anywhere. serve.rs splices both files
// into the page, and tests/steps_test.rs runs this one under node against the
// fixture commands. Rendering lives in ui.js (renderCommandSteps).
//
// The panel this feeds adds NOTHING to harness-graph.json. That schema is
// written by two scanners in two languages - src/scan.rs and
// harness-bootstrap/assets/scripts/harness-graph.py - which must produce
// byte-identical output on the same repo, and there is no automated parity test
// between them, so every field added to it is a field kept in step by hand. What
// this parses is a file the page already fetches through GET /file.
//
// EDITING. The panel is no longer read-only: steps can be reordered, retitled,
// and switched off, and `serializeCommandSteps` writes the result back through
// POST /command. Two rules make that safe to do to a file a human wrote:
//
//   1. SURGICAL, NOT REGENERATED. Serialization never rebuilds the document from
//      the parse tree. Every step records the line span it occupies in the
//      source, and only those spans are rewritten; frontmatter, headings, intros,
//      trailing prose and every byte between groups survive unread. A parser
//      that round-trips a file it does not fully model will eventually eat
//      someone's nested list, so this one is not asked to.
//   2. A DISABLED STEP IS COMMENTED, NOT DELETED. It stays in place wrapped in
//      `<!-- harness-view:disabled-step ... -->`, so re-enabling puts it back
//      exactly where it was, and a reviewer reading the raw file sees what was
//      switched off. Be honest about what that is: an HTML comment removes a
//      step from the RENDERED procedure and marks intent, it does not stop a
//      model that reads the raw file from seeing the text. It is a reversible
//      edit, not an enforcement boundary. The enforcement boundary is still
//      POST /toggle, which quarantines whole files.
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

// The quarantine wrapper for a switched-off step. Written at column zero so the
// open marker can never be mistaken for a step's continuation line.
const OFF_OPEN = "<!-- harness-view:disabled-step";
const OFF_CLOSE = "-->";
const OFF_OPEN_RE = /^<!--\s*harness-view:disabled-step\s*$/;
const OFF_CLOSE_RE = /^-->\s*$/;

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

/// How many leading lines the frontmatter occupies. Serialization addresses the
/// FULL file by line index, so the body's offset has to be a number, not an
/// implicit "whatever got sliced off".
function frontmatterLines(md) {
  if (!/^---\s*\n/.test(md)) return 0;
  const end = md.indexOf("\n---", 3);
  if (end === -1) return 0;
  const nl = md.indexOf("\n", end + 1);
  if (nl === -1) return md.split(/\r?\n/).length;
  return md.slice(0, nl + 1).split(/\r?\n/).length - 1;
}

/// -> { groups: [{heading, intro, steps}], hasSteps, body, lines, offset, eol }
/// Each step is { num, text, start, end, disabled, indent } where start/end are
/// INCLUSIVE line indices into `lines` (the whole file, frontmatter included).
function parseCommandSteps(md) {
  const lines = md.split(/\r?\n/);
  const eol = /\r\n/.test(md) ? "\r\n" : "\n";
  const offset = frontmatterLines(md);
  // joined with the file's OWN terminator: `body` is contracted to be the file
  // minus its frontmatter, byte for byte, and joining with "\n" silently
  // converted a CRLF checkout into LF
  const body = lines.slice(offset).join(eol);

  const groups = [];
  let group = { heading: null, intro: [], steps: [] };
  let step = null;
  const close = () => {
    // a section that is a heading and a blank line is not a group
    if (group.steps.length || group.intro.join("\n").trim()) groups.push(group);
  };
  const startStep = (m, i, disabled, blockStart) => {
    step = { num: m[1], text: m[2], start: blockStart === undefined ? i : blockStart,
             end: i, disabled: !!disabled, indent: null, edited: false, raw: null };
    group.steps.push(step);
    return step;
  };

  for (let i = offset; i < lines.length; i++) {
    const line = lines[i];

    // A quarantined step: consume the whole comment block here so its inner
    // lines never reach the heading/step rules below.
    if (OFF_OPEN_RE.test(line)) {
      let j = i + 1;
      const inner = [];
      while (j < lines.length && !OFF_CLOSE_RE.test(lines[j])) { inner.push(lines[j]); j++; }
      if (j < lines.length) {
        const m = STEP_RE.exec(inner[0] || "");
        if (m) {
          const st = startStep(m, j, true, i);
          st.text = [m[2]].concat(inner.slice(1)).join("\n");
          st.end = j;
          step = null;              // a disabled block never adopts what follows
          i = j;
          continue;
        }
      }
      // Not one of ours (or unterminated): fall through and treat it as prose.
    }

    const h = HEAD_RE.exec(line);
    if (h) { close(); group = { heading: h[1].trim(), intro: [], steps: [] }; step = null; continue; }
    const s = STEP_RE.exec(line);
    if (s) { startStep(s, i); continue; }
    // Continuation: an indented wrap, a blank line, or a following unnumbered
    // block. All of it belongs to the step above until the next numbered line
    // or the next heading.
    if (step) { step.text += "\n" + line; step.end = i; continue; }
    // Prose before the first numbered line in this section. Kept, not dropped:
    // it is usually the sentence that says what the list is for.
    group.intro.push(line);
  }
  close();
  for (const g of groups) {
    g.intro = g.intro.join("\n").trim();
    for (const st of g.steps) {
      st.indent = contIndent(st.text);
      // Trailing blank lines belong to the gap between steps, not to the step,
      // and a reorder that carries them along drifts the spacing every save.
      const trimmed = st.text.replace(/\s+$/, "");
      const dropped = st.text.slice(trimmed.length).split("\n").length - 1;
      st.end -= dropped;
      st.text = dedent(trimmed);
      // The step's own source lines, wrapper excluded. An unedited step is
      // written back from THESE, never re-rendered from `text`: `text` has been
      // dedented for display, and several shipped commands end a step with an
      // unindented paragraph that re-rendering would wrongly indent.
      st.raw = lines.slice(st.disabled ? st.start + 1 : st.start,
                           (st.disabled ? st.end - 1 : st.end) + 1);
    }
    // A section's closing prose - "On failure: roll back..." after deploy.md's
    // last step - is adopted by the step above it, deliberately: see the rule
    // above, and the fixture test that pins it. That is right for reading and
    // wrong for reordering, where dragging the section's conclusion up the page
    // behind step 3 is never what was meant. So it is identified here and
    // re-attached to the GROUP by the serializer, while `text` keeps it and the
    // display stays exactly as it was.
    const last = g.steps[g.steps.length - 1];
    if (last && !last.disabled) {
      last.tail = trailingBlock(last.raw);
      if (last.tail.length) {
        last.textBody = last.text.split("\n").slice(0, -last.tail.length).join("\n")
          .replace(/\s+$/, "");
      }
    }
    for (const st of g.steps) {
      if (!st.tail) st.tail = [];
      if (st.textBody === undefined) st.textBody = st.text;
    }
    // The whitespace between one step and the next, captured per SLOT rather
    // than per step. A group is not reliably all-tight or all-loose - shipped
    // board-audit.md runs steps 1-6 with no blank line and then puts one before
    // step 7 - so a single boolean cannot round-trip it. Holding the gap against
    // the position means an untouched group is rewritten byte-for-byte, and a
    // reordered one keeps the shape of the list rather than the shape of
    // whichever step moved.
    g.gaps = g.steps.map((st, i) =>
      i === 0 ? [] : lines.slice(g.steps[i - 1].end + 1, st.start));
    // Set by the editor when a step is reordered, switched off, or switched
    // back on. Only a dirty group is renumbered: `test.md` numbers its steps
    // 1, 2, 3, 5 on purpose, and a save that never touched it must not "fix"
    // that any more than it fixes the prose.
    g.dirty = false;
  }
  return { groups: groups, hasSteps: groups.some(g => g.steps.length > 0),
           body: body.trim(), lines: lines, offset: offset, eol: eol };
}

/// The trailing block of `lines` that reads as the section's closing prose: a
/// run of column-zero lines preceded by a blank line, with at least the step's
/// own first line left in front of it. Returns [] when there is no such block -
/// an indented continuation belongs to the step and stays with it.
///
/// The blank separator is part of what is returned. It is the boundary between
/// the step and the prose, so it has to travel with the prose; left behind, it
/// is trailing whitespace on a step that then butts straight up against the
/// paragraph on the next save.
function trailingBlock(lines) {
  let i = lines.length;
  while (i > 1 && lines[i - 1].trim() && !/^[ \t]/.test(lines[i - 1])) i--;
  if (i === lines.length) return [];              // no column-zero run at the end
  if (i <= 1) return [];                          // would swallow the whole step
  if (lines[i - 1].trim()) return [];             // not separated by a blank line
  while (i > 1 && !lines[i - 1].trim()) i--;      // take the blank run with it
  return lines.slice(i);
}

/// The indent a step's continuation lines actually use in this file, so a
/// rewritten step keeps the document's own convention instead of imposing one.
function contIndent(text) {
  for (const l of text.split("\n").slice(1)) {
    if (!l.trim()) continue;
    return l.length - l.replace(/^[ \t]+/, "").length;
  }
  return null;
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

/// Render one step back to source lines.
///
/// An unedited step is emitted as the bytes it arrived as. Only an edited one is
/// rebuilt from `text`, and then with the indent that step's own continuation
/// lines used, not a convention imposed on the file.
///
/// `n` is its position among the ENABLED steps of its group, applied only when
/// `renumber` is set; a disabled step consumes no number, because a procedure
/// that jumps from 2 to 4 reads as a step someone lost.
function renderStep(st, n, renumber) {
  const tail = (st.tail && st.tail.length) ? st.tail.length : 0;
  let out;
  if (st.edited) {
    const pad = " ".repeat(st.indent === null || st.indent === undefined ? 3 : st.indent);
    const body = (st.textBody === undefined ? st.text : st.textBody).split("\n");
    out = [`${st.num}. ${body[0]}`].concat(body.slice(1).map(l => (l.trim() ? pad + l : l)));
  } else {
    // minus the section's closing prose: the serializer re-attaches it to the
    // group so a reorder cannot carry it up the page
    out = tail ? st.raw.slice(0, st.raw.length - tail) : st.raw.slice();
  }
  // A disabled step keeps the number it had. It is not in the procedure, so it
  // has no position to renumber to - and `n` is the count of steps still
  // standing, which for a switched-off first step is zero: renumbering it wrote
  // `0.` into the file.
  if (renumber && out.length && !st.disabled) out[0] = out[0].replace(STEP_RE, `${n}. $2`);
  if (!st.disabled) return out;
  return [OFF_OPEN].concat(out, [OFF_CLOSE]);
}

/// The one sanctioned way to change a step's wording.
///
/// `text` and `textBody` differ only for the step that owns a section's closing
/// prose: `text` includes it (the panel shows the step as the parser read it),
/// `textBody` does not (the prose is the section's, and the editor must not
/// offer it as part of the step). Assigning to `.text` by hand would edit the
/// half that serialization ignores, so route every edit through here.
function setStepText(st, text) {
  st.textBody = text;
  st.text = st.tail && st.tail.length ? text + "\n" + st.tail.join("\n") : text;
  st.edited = true;
}

/// A step whose text already contains the comment terminator cannot be wrapped
/// in one: the block would close early and the tail would land in the document
/// as live prose. Callers check this BEFORE offering the control, so the refusal
/// is a disabled button rather than a failed save.
function canDisableStep(st) {
  return !st.text.includes(OFF_CLOSE);
}

/// Write an edited parse back to the file it came from.
///
/// Only the line spans the steps occupy are rewritten. Everything else - the
/// frontmatter, headings, intros, the prose between groups, the trailing text -
/// is passed through as the original bytes, so a construct this parser does not
/// model cannot be damaged by a save that never touched it.
///
/// -> the new file text.
function serializeCommandSteps(parsed) {
  const lines = parsed.lines.slice();
  // Groups are rewritten back-to-front so an earlier group's edit cannot shift
  // the line indices a later group still refers to.
  const groups = parsed.groups
    .filter(g => g.steps.length)
    .slice()
    .sort((a, b) => b.steps[0].start - a.steps[0].start);

  for (const g of groups) {
    const spanStart = Math.min(...g.steps.map(s => s.start));
    const spanEnd = Math.max(...g.steps.map(s => s.end));
    // The section's closing prose, taken off whichever step the parser attached
    // it to and held for the end of the group.
    const owner = g.steps.find(s => s.tail && s.tail.length);
    const tail = owner ? owner.tail : [];
    const out = [];
    let n = 0;
    g.steps.forEach((st, i) => {
      if (!st.disabled) n++;
      // The separator that sat in this slot in the source, whatever it was.
      if (i > 0) out.push(...(g.gaps[i] || []));
      out.push(...renderStep(st, n, g.dirty === true));
    });
    out.push(...tail);
    lines.splice(spanStart, spanEnd - spanStart + 1, ...out);
  }
  return lines.join(parsed.eol);
}

// Node requires this file; the browser does not have `module` and skips the
// line. There is no bundler here and there must not be one: the page is served
// as a single response with these sources spliced in.
if (typeof module !== "undefined" && module.exports) {
  module.exports = { parseCommandSteps, touches, serializeCommandSteps,
                     setStepText, canDisableStep, renderStep };
}
