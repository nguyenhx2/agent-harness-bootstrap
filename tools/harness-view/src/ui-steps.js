// Command Steps: the parser, and the editor layer built on it.
//
// NOTHING HERE TOUCHES THE DOM AT LOAD TIME. That is the property this file is
// for, and it survives the editor layer below: every function is pure until it
// is called, and the one line that reaches for `document` is the guarded
// `installStepEditor()` at the very bottom, which no-ops when there is no
// document. ui.js touches `document` on its FIRST line, so node cannot require
// it at all; node can require this, which is why the logic worth testing lives
// here and tests/steps_test.rs runs it against the fixture commands. serve.rs
// splices both files into the page, this one first.
//
// Three layers, in this order:
//   1. the parser and serializer - what a step is, and how it goes back;
//   2. pure editor logic - completion contexts, suggestion ranking, step
//      insertion, and the small markdown reader steps are rendered with;
//   3. the browser layer, which installs itself and owns no state ui.js owns.
//
// WHY LAYER 3 IS HERE AND NOT IN ui.js. The step panel's DOM is ui.js's
// (`renderCommandSteps`, `buildStepCard`). This file adds three things to it
// without editing it: an autocomplete popup, an "insert a step here" control
// between the cards, and markdown rendering inside a step's body. All three
// attach by delegation and by observing repaints, so ui.js needs no hook and
// the two files can be edited independently. The handshake is small and named
// in `panelState()` below - if ui.js ever renames it, the editor degrades to
// exactly the panel that shipped before, with a console warning, rather than
// throwing inside someone else's click handler.
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
    // The span is decided by the steps that ARE in the file. An INSERTED step
    // owns no source lines - `insertStep` anchors its start/end on a neighbour
    // precisely so a stray index cannot stretch this span - but excluding it
    // here is what makes that anchoring an optimisation rather than the rule.
    const placed = g.steps.filter(s => !s.inserted && typeof s.start === "number");
    if (!placed.length) continue;      // nothing anchored: nothing to rewrite
    const spanStart = Math.min(...placed.map(s => s.start));
    const spanEnd = Math.max(...placed.map(s => s.end));
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

// ===========================================================================
// LAYER 2: pure editor logic. Still no DOM, still requireable by node.
// ===========================================================================

/// A new step, spliced into a group that already has one.
///
/// The whole reason the panel is safe to point at a file a human wrote is that
/// what it writes parses back to what it meant. Insertion is the operation most
/// able to break that, so it is constrained in three ways:
///
///   1. IT NEVER OWNS SOURCE LINES. `start`/`end` are copied from the neighbour
///      it lands next to, so the line span the serializer rewrites is still the
///      span the file's own steps occupy. Combined with the `inserted` filter in
///      `serializeCommandSteps`, a new step cannot move a single byte outside
///      its group.
///   2. ITS CONTINUATION LINES ARE ALWAYS INDENTED. Every rule that ENDS a step
///      - a numbered line, a heading, both quarantine markers - is anchored at
///      column zero. `renderStep` pads an edited step's continuation lines by
///      `indent`, so an indent of at least one space is a proof that the step
///      comes back as one step no matter what was typed into it. The group's own
///      indent is used when it has one; three spaces when it does not, because a
///      new step has no original bytes to preserve and a file whose steps happen
///      to run unindented must not decide how a NEW one is written.
///   3. THE SEPARATOR IS THE GROUP'S, NOT A DEFAULT. `insertGap` copies the
///      blank-line convention the list already uses, so inserting into a tight
///      list does not loosen it and vice versa.
///
/// The group is marked dirty, which is what renumbers the list - a list with two
/// steps numbered 4 is worse than no insertion at all.
function insertStep(group, index, text) {
  if (!group || !group.steps || !group.steps.length) {
    throw new Error("a step can only be added to a list that already has one");
  }
  const body = String(text == null ? "" : text).replace(/\r\n/g, "\n").replace(/\s+$/, "");
  const issue = stepTextIssue(body);
  if (issue) throw new Error(issue);
  const at = Math.max(0, Math.min(Number(index) || 0, group.steps.length));
  const anchor = group.steps[Math.min(at, group.steps.length - 1)];
  const own = group.steps.map(s => s.indent).filter(x => typeof x === "number" && x > 0);
  const st = {
    num: String(at + 1),
    text: body,
    textBody: body,
    start: anchor.start,
    end: anchor.start,
    disabled: false,
    indent: own.length ? own[0] : 3,
    edited: true,          // there are no original bytes; render it from `text`
    raw: null,
    tail: [],              // the section's closing prose is never a new step's
    inserted: true,
  };
  group.steps.splice(at, 0, st);
  insertGap(group, at);
  group.dirty = true;
  return st;
}

/// Why a step's text cannot be written as typed, or null when it can.
///
/// Checked BEFORE the step exists rather than at save time, so the refusal is a
/// message under the box and not a file that came back wrong.
function stepTextIssue(text) {
  const t = String(text == null ? "" : text).replace(/\r\n/g, "\n");
  if (!t.trim()) return "a step needs some text";
  if (!t.split("\n")[0].trim()) return "a step cannot begin with a blank line";
  return null;
}

/// Give the new slot the separator this list already uses between steps.
///
/// `g.gaps` is indexed by SLOT, not by step (see the parser), so an insertion
/// has to splice one in or every step after the new one silently adopts its
/// neighbour's spacing. Slot 0 is never written: it is the space BEFORE the
/// first step, which belongs to whatever precedes the list. Inserting at the
/// front therefore hands the gap to the step being pushed down, which is the
/// separator that actually has to appear.
function insertGap(group, index) {
  if (!group.gaps) group.gaps = group.steps.map(() => []);
  const tally = {};
  let best = null, bestN = 0;
  for (const g of group.gaps.slice(1)) {
    const k = JSON.stringify(g);
    tally[k] = (tally[k] || 0) + 1;
    if (tally[k] > bestN) { bestN = tally[k]; best = k; }
  }
  // A one-step group has no convention to copy. A multi-line step next to a
  // tight neighbour reads as one run-on step, so that case gets a blank line.
  const gap = best === null
    ? (group.steps.some(s => String(s.text).indexOf("\n") !== -1) ? [""] : [])
    : JSON.parse(best);
  group.gaps.splice(Math.max(Number(index) || 0, 1), 0, gap.slice());
  while (group.gaps.length < group.steps.length) group.gaps.push(gap.slice());
  group.gaps.length = group.steps.length;
  group.gaps[0] = [];
  return group.gaps;
}

// ---------------------------------------------------------------------------
// Completion.
//
// What is offered comes from what the viewed harness actually HAS, which is the
// only version of this feature worth having: a list of plausible-looking names
// is a list of new typos. Five of the six classes come straight off the graph
// the page already loaded - agents, rules, hooks, commands, scripts and skills
// are all nodes, carrying an id and a repo-relative `file`. The sixth cannot:
// the commands quote `docs/specs/05-functional-requirements.md`,
// `docs/templates/ADR.md.template` and `docs/architecture/decisions/` constantly
// and none of those is a node, which is why serve.rs grew GET /paths and nothing
// else.
// ---------------------------------------------------------------------------

/// Node types whose NAME is worth offering inside backticks.
const NAME_KINDS = { agent: 1, hook: 1, skill: 1, script: 1, rule: 1 };

/// The character class a completion token is made of. `/` is in it so a path is
/// one token; the context rules below are what tell `/deploy` apart from
/// `docs/specs/`.
const TOKEN_CHAR = /[A-Za-z0-9._/-]/;

/// -> [{ctx, value, kind, detail}] where `ctx` is the completion context the
/// item may be offered in ("name", "cmd" or "path") and `value` is the exact
/// text inserted.
function suggestionsFromGraph(nodes) {
  const out = [];
  for (const n of (nodes || [])) {
    if (!n || !n.id) continue;
    const id = String(n.id);
    const type = n.type ? String(n.type) : "";
    const cut = id.indexOf(":");
    const name = cut === -1 ? id : id.slice(cut + 1);
    const file = n.file ? String(n.file) : "";
    // A command is cited as `/name`; the slash is part of what gets inserted,
    // because the trigger token includes it.
    if (type === "command" && name) {
      out.push({ ctx: "cmd", value: "/" + name, kind: "command", detail: file });
    } else if (NAME_KINDS[type] && name) {
      out.push({ ctx: "name", value: name, kind: type, detail: file });
    }
    if (file) out.push({ ctx: "path", value: file, kind: type, detail: "" });
  }
  return out;
}

/// The names GET /paths returned. Directories arrive with a trailing slash and
/// keep it: half the citations in a command name a directory, and the slash is
/// also what lets the user keep typing and get the next level.
function suggestionsFromPaths(paths) {
  const out = [];
  for (const p of (paths || [])) {
    if (!p) continue;
    const v = String(p);
    out.push({ ctx: "path", value: v, kind: v.charAt(v.length - 1) === "/" ? "dir" : "file",
               detail: "" });
  }
  return out;
}

/// First list wins a duplicate. Graph items come first, because their `kind` is
/// the node's own type and "agent" tells a reader more than "file".
function mergeSuggestions(a, b) {
  const seen = Object.create(null);
  const out = [];
  for (const it of (a || []).concat(b || [])) {
    const k = it.ctx + " " + it.value;
    if (seen[k]) continue;
    seen[k] = 1;
    out.push(it);
  }
  return out;
}

/// What the caret is sitting in the middle of, or null when it is in the middle
/// of ordinary prose.
///
/// Offering something on every word is how an editor becomes a nuisance, so
/// there are exactly three openings, each one a mark the author already uses to
/// mean "this is a reference":
///   `name    a backtick - the same mark `touches` reads as an agent reference
///   /name    a slash at a word boundary - a command
///   .claude/ or docs/ - a path, the shape every quoted file in these files has
/// -> {kind, start, end, word, tick} with start/end the slice to replace.
function completionContext(text, caret) {
  const s = String(text == null ? "" : text);
  const at = Number(caret);
  if (!(at >= 0) || at > s.length) return null;
  let i = at;
  while (i > 0 && TOKEN_CHAR.test(s.charAt(i - 1))) i--;
  const word = s.slice(i, at);

  // `@` - the mention, and the only opening that fires on its own.
  //
  // The three openings below all ask the author to already know which KIND of thing they are
  // citing: a backtick means a name, a slash means a command, `docs/` means a path. That is fine
  // once you know the harness and useless before you do - typing `@` and getting nothing is the
  // report that produced this. `@` opens on everything at once, with no word typed yet, and the
  // insertion is the markup the file actually uses for whatever gets chosen, so the author never
  // has to remember whether a rule is cited in backticks and a command with a slash.
  const atStart = i > 0 && s.charAt(i - 1) === "@" ? i - 1 : (at > 0 && s.charAt(at - 1) === "@" ? at - 1 : -1);
  if (atStart >= 0) {
    const pre = atStart > 0 ? s.charAt(atStart - 1) : "";
    // Not inside an email address or a decorator: `@` opens only at a word boundary.
    if (pre === "" || /[\s(\[`>|]/.test(pre)) {
      return { kind: "mention", start: atStart, end: at,
               word: atStart + 1 <= at ? s.slice(atStart + 1, at) : "", tick: false };
    }
  }

  if (!word) return null;
  const before = i > 0 ? s.charAt(i - 1) : "";
  const tick = before === "`";
  const ctx = { start: i, end: at, word: word, tick: tick };
  if (word.charAt(0) === "/" && word.indexOf("/", 1) === -1 &&
      (before === "" || /[\s`([]/.test(before))) {
    ctx.kind = "cmd";
    return ctx;
  }
  if (word.indexOf("/") !== -1 || word.charAt(0) === ".") { ctx.kind = "path"; return ctx; }
  if (tick) { ctx.kind = "name"; return ctx; }
  // `docs` with no slash yet is still unambiguous enough to open on; three
  // characters, so it cannot fire on "do".
  if (word.length >= 3 && "docs".indexOf(word) === 0) { ctx.kind = "path"; return ctx; }
  return null;
}

/// Prefix matches first, then substrings; shorter before longer, then
/// alphabetical, so the list is stable and the best guess is always row one.
/// An item the user has already typed in full is dropped - there is nothing to
/// complete, and leaving it there means Enter looks like it did nothing.
function rankSuggestions(items, ctx, limit) {
  if (!ctx || !ctx.kind) return [];
  const w = String(ctx.word).toLowerCase();
  const scored = [];
  // A mention draws from every context at once - that is the whole point of it.
  const anyCtx = ctx.kind === "mention";
  for (const it of (items || [])) {
    if (!anyCtx && it.ctx !== ctx.kind) continue;
    const v = String(it.value).toLowerCase();
    if (v === w) continue;
    let rank;
    if (w === "") rank = 0;                      // `@` alone offers everything
    else if (v.indexOf(w) === 0) rank = 0;
    else if (v.indexOf(w) > 0) rank = 1;
    else continue;
    // With no word typed the list would otherwise be alphabetical by accident. Seats and rules
    // are what a step usually names, so they come first and paths last.
    if (anyCtx) rank = rank * 4 + (it.ctx === "name" ? 0 : it.ctx === "cmd" ? 1 : 2);
    scored.push({ it: it, rank: rank, len: it.value.length });
  }
  scored.sort((a, b) => a.rank - b.rank || a.len - b.len ||
                        (a.it.value < b.it.value ? -1 : a.it.value > b.it.value ? 1 : 0));
  return scored.slice(0, limit === undefined ? 8 : limit).map(x => x.it);
}

/// Put the chosen item in at the caret, replacing only the token it completes.
///
/// Nothing else in the text is touched: this runs when the user picked a row,
/// never on its own, so there is no path here that changes a word the author did
/// not choose to change. The one addition is the closing backtick, and only when
/// the author opened one and the file has not already closed it - a backticked
/// reference is not a reference at all without it, and it is part of the token
/// being completed rather than a correction to something else.
/// -> {text, caret}
function applyCompletion(text, ctx, item) {
  const s = String(text == null ? "" : text);
  if (!ctx || !item) return { text: s, caret: ctx ? ctx.end : s.length };
  let ins = String(item.value);
  const after = s.slice(ctx.end);
  if (ctx.kind === "mention") {
    // The `@` and whatever was typed after it are replaced by the citation this repository
    // actually uses for that kind of thing: a command keeps its slash and stands bare, everything
    // else goes in backticks - which is also what `touches` reads back as a reference, so a step
    // written this way shows up on the graph.
    if (item.ctx !== "cmd") {
      const closed = after.charAt(0) === "`";
      ins = "`" + ins + (closed ? "" : "`");
    }
    return { text: s.slice(0, ctx.start) + ins + after, caret: ctx.start + ins.length };
  }
  if (ctx.tick && after.charAt(0) !== "`" && ins.charAt(ins.length - 1) !== "/") ins += "`";
  return { text: s.slice(0, ctx.start) + ins + after, caret: ctx.start + ins.length };
}

// ---------------------------------------------------------------------------
// The small markdown reader a step's body is displayed with.
//
// A step is mostly one paragraph of prose, and it stays rendered as one. But
// some steps are not: `/implement-fr` step 4 in a real harness IS a routing
// table, and as pre-wrap text it is a wall of pipes nobody reads. So exactly
// what turns up in these files is supported - tables, code spans, bold, italic,
// links, and bullet or numbered sub-lists - and nothing else.
//
// TWO RULES GOVERN THIS AND BOTH ARE LOAD-BEARING.
//
//   RENDERING IS DISPLAY ONLY. `st.text` and `st.textBody` are never touched by
//   any of it, Edit opens the ORIGINAL source byte for byte, and the serializer
//   still writes the bytes the file arrived with. Nothing below is reachable
//   from the write path at all: it takes a string and returns a description.
//
//   FALL BACK RATHER THAN MANGLE. A table whose delimiter row does not match its
//   header, or whose rows are ragged, is NOT a table half-drawn - the whole run
//   comes back as a text block and renders exactly as it does today. The same
//   for anything else that does not parse. A half-parsed table is worse than an
//   unparsed one because it looks authoritative.
//
// And the invariant the panel had before this: repository text still never
// reaches innerHTML. Every renderer below builds nodes with createElement and
// puts text in with textContent - there is no HTML string anywhere in this file
// - so a command file from a checkout the user did not write cannot inject
// markup by being displayed. The single value that a browser would ACT on
// rather than show is a link's href, and `safeHref` is why that is a closed set.
// ---------------------------------------------------------------------------

// Code first, so a pipe or an asterisk inside `backticks` is left alone.
// `_underscores_` are deliberately NOT italic: these files are full of
// snake_case identifiers and file names, and italicising half of one is the
// mangle this whole section is written to avoid.
const INLINE_RE = /`([^`\n]+)`|\[([^\]\n]+)\]\(([^)\s]+)\)|\*\*([^*\n]+)\*\*|\*([^\s*][^*\n]*?)\*/g;
const MD_ROW_RE = /^\s*\|.*\|\s*$/;
const MD_DELIM_RE = /^\s*\|(?:\s*:?-+:?\s*\|)+\s*$/;
const MD_LIST_RE = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;

/// -> [{kind:"text"|"table"|"list", ...}], covering every line of the input.
function parseStepMarkdown(text) {
  const lines = String(text == null ? "" : text).replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let buf = [];
  const flush = () => {
    while (buf.length && !buf[buf.length - 1].trim()) buf.pop();
    while (buf.length && !buf[0].trim()) buf.shift();
    if (buf.length) blocks.push({ kind: "text", text: buf.join("\n") });
    buf = [];
  };
  let i = 0;
  while (i < lines.length) {
    const t = readTable(lines, i);
    if (t) { flush(); blocks.push(t.block); i = t.next; continue; }
    const l = readList(lines, i);
    if (l) { flush(); blocks.push(l.block); i = l.next; continue; }
    buf.push(lines[i]);
    i++;
  }
  flush();
  return blocks;
}

/// A GFM table, or null - and null for anything that is only nearly one.
function readTable(lines, i) {
  if (!MD_ROW_RE.test(lines[i] || "")) return null;
  if (!MD_DELIM_RE.test(lines[i + 1] || "")) return null;
  const head = rowCells(lines[i]);
  const align = rowCells(lines[i + 1]).map(c =>
    /^:-+:$/.test(c) ? "center" : /^-+:$/.test(c) ? "right" : /^:-+$/.test(c) ? "left" : "");
  if (align.length !== head.length) return null;
  const rows = [];
  let j = i + 2;
  while (j < lines.length && MD_ROW_RE.test(lines[j])) {
    const cells = rowCells(lines[j]);
    // Ragged, so something in a cell is not what this reader thinks it is - an
    // escaped pipe, a pipe inside a construct it does not model. Show the run as
    // written rather than draw a table with a column silently shifted.
    if (cells.length !== head.length) return null;
    rows.push(cells);
    j++;
  }
  if (!rows.length) return null;
  return { block: { kind: "table", head: head, align: align, rows: rows }, next: j };
}

function rowCells(line) {
  let s = String(line).trim();
  if (s.charAt(0) === "|") s = s.slice(1);
  // `\|` is an escaped pipe INSIDE a cell, not the end of the row. Splitting on
  // it is what made a cell containing a pipe come back with one column too many,
  // which sent the whole run to the fallback text block - so the one table that
  // legitimately wanted a pipe in a cell was the one table that could never be
  // drawn. It matters more now that cells are typed into: the grid editor writes
  // this escape, and a reader that could not read it back would turn a table
  // into pipes the moment someone typed one.
  if (s.charAt(s.length - 1) === "|" && s.charAt(s.length - 2) !== "\\") s = s.slice(0, -1);
  return splitCells(s).map(c => c.trim());
}

/// Split on the pipes that separate cells, unescaping the ones that do not.
function splitCells(s) {
  const out = [];
  let cur = "";
  for (let i = 0; i < s.length; i++) {
    const c = s.charAt(i);
    if (c === "\\" && s.charAt(i + 1) === "|") { cur += "|"; i++; continue; }
    if (c === "|") { out.push(cur); cur = ""; continue; }
    cur += c;
  }
  out.push(cur);
  return out;
}

/// A run of bullets or a run of numbers, never a mix: switching marker ends the
/// list, because a step that goes from bullets to numbers is two lists and
/// merging them renumbers something the author wrote on purpose.
function readList(lines, i) {
  const m = MD_LIST_RE.exec(lines[i] || "");
  if (!m) return null;
  const ordered = /\d/.test(m[2]);
  const base = m[1].length;
  const items = [];
  let j = i;
  while (j < lines.length) {
    const mm = MD_LIST_RE.exec(lines[j]);
    if (mm && /\d/.test(mm[2]) === ordered) {
      items.push({ depth: Math.max(0, Math.round((mm[1].length - base) / 2)),
                   marker: mm[2], text: mm[3] });
      j++;
      continue;
    }
    // An indented line under an item is that item's wrapped tail.
    if (items.length && lines[j].trim() && /^\s\s+\S/.test(lines[j])) {
      items[items.length - 1].text += " " + lines[j].trim();
      j++;
      continue;
    }
    break;
  }
  if (!items.length) return null;
  return { block: { kind: "list", ordered: ordered, items: items }, next: j };
}

/// Whether rendering would show the reader anything a pre-wrap div does not.
/// A step that is one plain paragraph is left exactly as the panel drew it
/// before, which keeps this from being a redesign of every step in the file.
function stepMarkdownIsRich(blocks) {
  for (const b of (blocks || [])) {
    if (b.kind !== "text") return true;
    INLINE_RE.lastIndex = 0;
    if (INLINE_RE.test(b.text)) return true;
  }
  return false;
}

/// The only value on this path a browser would ACT on rather than display.
/// http(s) opens; every other shape - `javascript:`, `data:`, a bare relative
/// path this viewer has nothing to open with - renders as the literal markdown
/// the author wrote, which is honest and inert.
function safeHref(raw) {
  const u = String(raw == null ? "" : raw).trim();
  return /^https?:\/\/[^\s]+$/i.test(u) ? u : null;
}

// ---------------------------------------------------------------------------
// EDITABLE PARTS. The same source, cut into the pieces a person edits with
// different hands.
//
// The panel used to hand a step's whole body to one <textarea>, which is right
// for the common case - a step is one sentence - and useless for the case that
// prompted this: `/implement-fr` step 4 in a real harness is a sentence followed
// by a seventeen-row routing table, and a textarea full of `| Work | Agent |`
// is not something anyone edits, it is something they avoid.
//
// So a step is split into prose runs and table runs. Prose stays a textarea. A
// table becomes a grid. Two properties make that safe to point at a file
// somebody wrote by hand:
//
//   THE SPLIT IS A PARTITION, NOT A PARSE. Every line of the input lands in
//   exactly one part, in order, as the bytes it arrived as. `joinStepParts` is
//   therefore the exact inverse of `splitStepParts` - open the editor, change
//   nothing, and what comes back out is what went in, blank lines and trailing
//   spaces included. Nothing is normalised on the way through, because a step
//   nobody edited must not come back reformatted.
//
//   A TABLE IS REWRITTEN ONLY WHEN IT IS TOUCHED. `part.lines` holds the source
//   rows; the grid operations below replace them by re-rendering, and nothing
//   else does. An untouched table is emitted from its original bytes even when
//   the prose above it was rewritten.
//
// `splitStepParts` reuses `readTable`, which is deliberately strict: a run that
// is only nearly a table stays prose and is edited as text. That is the same
// fall-back-rather-than-mangle rule the reader above follows, and it is what
// keeps a ragged table out of a grid that would silently shift a column.
// ---------------------------------------------------------------------------

/// -> [{kind:"prose"|"table", lines:[...]}] covering every line of `text` once.
/// Table parts additionally carry {head, align, rows} - the grid.
function splitStepParts(text) {
  const lines = String(text == null ? "" : text).replace(/\r\n/g, "\n").split("\n");
  const parts = [];
  let buf = [];
  // An empty prose run is not a part: it would draw an empty textarea between
  // two tables. It carries no lines either, so dropping it is still a partition.
  const flush = () => { if (buf.length) parts.push({ kind: "prose", lines: buf }); buf = []; };
  let i = 0;
  while (i < lines.length) {
    const t = readTable(lines, i);
    if (t) {
      flush();
      parts.push({ kind: "table", lines: lines.slice(i, t.next), head: t.block.head,
                   align: t.block.align, rows: t.block.rows,
                   // The file's own spelling of each row, held beside the grid so
                   // a row nobody edited is written back as the bytes it arrived
                   // as. See `renderTablePart`.
                   src: { head: lines[i], delim: lines[i + 1],
                          rows: lines.slice(i + 2, t.next) } });
      i = t.next;
      continue;
    }
    buf.push(lines[i]);
    i++;
  }
  flush();
  return parts;
}

/// The markdown the parts describe. Byte-identical to what `splitStepParts` was
/// given whenever no part has been rewritten.
function joinStepParts(parts) {
  const out = [];
  for (const p of (parts || [])) {
    for (const l of (p.lines || [])) out.push(l);
  }
  return out.join("\n");
}

function stepPartsHaveTable(parts) {
  return (parts || []).some(p => p.kind === "table");
}

/// A cell as it must be WRITTEN. A pipe is escaped rather than dropped - the
/// reader above unescapes it, so the round trip is lossless - and a newline is
/// flattened, because a row is one line and a pasted paragraph would otherwise
/// end the table mid-way.
function cellSource(s) {
  return cellText(s).replace(/\|/g, "\\|");
}

/// A cell as it READS: flattened and trimmed, but not escaped. This is the form
/// `rowCells` gives back, so it is the form two cells have to be compared in - a
/// cell holding a pipe is escaped in the source and bare in the grid, and
/// comparing those two directly reported "changed" about a row nobody touched.
function cellText(s) {
  return String(s == null ? "" : s).replace(/\r?\n/g, " ").trim();
}

const ALIGN_DELIM = { left: ":---", right: "---:", center: ":---:" };

/// A table part's grid, back as markdown rows.
///
/// A ROW NOBODY CHANGED KEEPS ITS OWN BYTES. `part.src` holds the line each row
/// arrived as, and a row whose cells still read the same is written back from
/// that line rather than re-rendered. Without it, correcting one cell of the
/// seventeen-row routing table rewrote all nineteen lines - the header spacing,
/// the `|------|-------|` delimiter, every untouched row - and the diff of a
/// one-word fix was the whole table. What a reviewer sees should be what changed.
///
/// Columns are NOT padded to a common width when a row IS re-rendered, for the
/// same reason: a table whose widest cell is a sentence would come back with
/// seventeen lines of trailing spaces.
function renderTablePart(part) {
  const cols = part.head.length;
  const src = part.src || {};
  const render = cells => "| " + cells.map(cellSource).join(" | ") + " |";
  const keep = (line, cells) =>
    (typeof line === "string" && sameCells(rowCells(line), cells)) ? line : render(cells);
  const out = [keep(src.head, part.head)];
  out.push(keepDelim(src.delim, part.align));
  part.rows.forEach((r, i) => {
    const cells = r.slice(0, cols);
    while (cells.length < cols) cells.push("");
    out.push(keep(src.rows ? src.rows[i] : null, cells));
  });
  return out;
}

/// Two rows of cells that would render the same. Compared trimmed, because that
/// is how `rowCells` reads them back and a cell is not changed by the spaces
/// around it in the source.
function sameCells(a, b) {
  if (!a || !b || a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (cellText(a[i]) !== cellText(b[i])) return false;
  }
  return true;
}

function keepDelim(line, align) {
  if (typeof line === "string" && MD_DELIM_RE.test(line)) {
    const had = rowCells(line).map(c =>
      /^:-+:$/.test(c) ? "center" : /^-+:$/.test(c) ? "right" : /^:-+$/.test(c) ? "left" : "");
    if (had.length === align.length && had.every((a, i) => a === align[i])) return line;
  }
  return "|" + align.map(a => " " + (ALIGN_DELIM[a] || "---") + " ").join("|") + "|";
}

/// Re-render a table part's source from its grid. Every mutation below ends
/// here, so `lines` can never disagree with the grid it is supposed to describe.
function syncTablePart(part) {
  if (!part.src) part.src = { head: null, delim: null, rows: part.rows.map(() => null) };
  part.lines = renderTablePart(part);
  return part;
}

/// The source lines held beside the grid, kept in step with it. A row that moved
/// keeps its bytes; a row whose SHAPE changed - a column added or removed -
/// cannot, so the whole table drops back to being re-rendered.
function srcRows(part) {
  if (!part.src) part.src = { head: null, delim: null, rows: [] };
  if (!part.src.rows) part.src.rows = [];
  while (part.src.rows.length < part.rows.length) part.src.rows.push(null);
  return part.src.rows;
}

function tableAddRow(part, at) {
  const i = Math.max(0, Math.min(Number(at), part.rows.length));
  srcRows(part).splice(i, 0, null);
  part.rows.splice(i, 0, part.head.map(() => ""));
  return syncTablePart(part);
}

/// -> null when the table has one body row left. A table with a header and no
/// rows does not parse back as a table, so removing the last one would turn the
/// grid into pipes the next time the step was opened.
function tableRemoveRow(part, at) {
  if (part.rows.length <= 1) return null;
  if (!(at >= 0) || at >= part.rows.length) return null;
  srcRows(part).splice(at, 1);
  part.rows.splice(at, 1);
  return syncTablePart(part);
}

function tableAddColumn(part, at) {
  const i = Math.max(0, Math.min(Number(at), part.head.length));
  part.head.splice(i, 0, "");
  part.align.splice(i, 0, "");
  for (const r of part.rows) r.splice(i, 0, "");
  part.src = { head: null, delim: null, rows: part.rows.map(() => null) };
  return syncTablePart(part);
}

/// -> null when there is one column left, for the same reason as the last row.
function tableRemoveColumn(part, at) {
  if (part.head.length <= 1) return null;
  if (!(at >= 0) || at >= part.head.length) return null;
  part.head.splice(at, 1);
  part.align.splice(at, 1);
  for (const r of part.rows) r.splice(at, 1);
  part.src = { head: null, delim: null, rows: part.rows.map(() => null) };
  return syncTablePart(part);
}

/// A new two-by-two table, ready to be typed into. It has no source lines to
/// keep, so every row of it is rendered.
function newTablePart() {
  return syncTablePart({ kind: "table", lines: [], head: ["Column", "Column"],
                         align: ["", ""], rows: [["", ""]],
                         src: { head: null, delim: null, rows: [null] } });
}

/// The grid a dialog can work on without touching the one on the page. Deep
/// enough that Cancel is free: nothing the dialog does reaches `part`.
function copyTablePart(part) {
  const src = part.src || {};
  return { kind: "table", lines: part.lines.slice(), head: part.head.slice(),
           align: part.align.slice(), rows: part.rows.map(r => r.slice()),
           src: { head: src.head, delim: src.delim,
                  rows: (src.rows || []).slice() } };
}

/// Append a table to a set of parts, with the blank line that makes it a block
/// of its own. -> the new part, or null when there is no prose for it to follow:
/// a step whose FIRST line is a table row would be written as `4. | Work |`,
/// which is a step nobody can read and a table that does not parse.
function appendTablePart(parts) {
  if (!parts || !parts.length) return null;
  const last = parts[parts.length - 1];
  if (last.kind !== "prose") return null;
  if (!last.lines.join("\n").trim()) return null;
  if (last.lines[last.lines.length - 1] !== "") last.lines.push("");
  const part = newTablePart();
  parts.push(part);
  return part;
}

// ===========================================================================
// LAYER 3: the browser. Nothing below runs under node.
// ===========================================================================

/// How the editor reaches the panel state ui.js holds.
///
/// `stepEdit` is a top-level `let` in ui.js and `paintCommandSteps` a top-level
/// function, both in the same classic-script global scope this file is spliced
/// into, so they resolve by name. That is the whole handshake, and it is read
/// LAZILY - inside handlers, never at load - because at the moment this file is
/// evaluated ui.js has not run and `stepEdit` is still in its temporal dead
/// zone. If ui.js is ever rewritten past this, every caller below falls back to
/// doing nothing and says so once.
let handshakeWarned = false;
function panelState() {
  try {
    if (typeof stepEdit !== "undefined" && stepEdit && stepEdit.parsed) return stepEdit;
  } catch (e) { /* still in the TDZ: the panel is not up yet */ }
  return null;
}
function repaintPanel() {
  if (typeof paintCommandSteps === "function") { paintCommandSteps(); return true; }
  if (!handshakeWarned) {
    handshakeWarned = true;
    console.warn("harness-view: ui.js no longer exposes paintCommandSteps; " +
                 "the step editor's extra controls are inert");
  }
  return false;
}

/// A toast if the page has one, the console if it does not. The modal/toast API
/// is ui.js's and may not be there yet; nothing here waits on it.
function say(kind, title, body) {
  if (window.ui && typeof window.ui.toast === "function") {
    window.ui.toast({ kind: kind, title: title, body: body });
  } else {
    console.warn("harness-view: " + title + (body ? " - " + body : ""));
  }
}

/// The page's own button component, used rather than re-implemented: `setBtn`
/// puts a sprite icon in front of the label and `setIconBtn` gives an icon-only
/// control the accessible name it would otherwise not have. Both are ui.js's and
/// are resolved at CALL time - this file is spliced in first, so a load-time
/// reference would be a dead one - and a button with no icon beats a thrown
/// exception inside someone else's click handler, which is what the fallback is.
function stepBtn(btn, iconKey, text, iconOnly) {
  try {
    if (iconOnly && typeof setIconBtn === "function") { setIconBtn(btn, iconKey, text); return btn; }
    if (!iconOnly && typeof setBtn === "function") { setBtn(btn, iconKey, text); return btn; }
  } catch (e) { /* a name this sprite does not carry: text is still a button */ }
  btn.textContent = text;
  btn.setAttribute("aria-label", text);
  return btn;
}

// The styles for the three things this file draws. They live here rather than in
// ui.html because ui.html has no idea these elements exist - they are injected
// into someone else's DOM by this file, so the rule that describes them belongs
// next to the code that creates them and cannot drift away from it.
//
// The one it REPLACES is ui.html's `.steptext`, whose comment says "pre-wrap,
// not markdown ... every byte lands via textContent so a scanned repository's
// own text can never reach innerHTML on this path." Half of that is now false
// and half is still the point. What is true after this change: a step's body is
// rendered as markdown, and it is still built with createElement and textContent
// only - there is no HTML string on this path - so a command file from a
// checkout nobody vetted still cannot inject markup by being displayed. Plain
// steps keep the pre-wrap paragraph they always had, which is why `.stepmd-p`
// carries the same white-space rule.
const STEP_CSS = `
.stepmd-p { white-space: pre-wrap; word-break: break-word; margin: 0 0 4px; }
.stepmd-p:last-child { margin-bottom: 0; }
.steptext code, .stepins code { font: inherit; background: #f1f5f9; border: 1px solid var(--line);
  border-radius: 4px; padding: 0 3px; word-break: break-all; }
.steptext a { color: #1d4ed8; }
.steptext ul, .steptext ol { margin: 3px 0 4px 16px; padding: 0; }
.steptext li { margin: 2px 0; word-break: break-word; }
.stepmd-tw { overflow-x: auto; margin: 5px 0; }
.stepmd-tw table { border-collapse: collapse; font-size: 11px; }
.stepmd-tw th, .stepmd-tw td { border: 1px solid var(--line); padding: 2px 5px;
  text-align: left; vertical-align: top; white-space: nowrap; }
.stepmd-tw th { background: #f1f5f9; font-weight: bold; }
.stepins { list-style: none; margin: -12px 0 6px; text-align: left; }
/* The panel draws the chain's connector on every <li> that is not the last. An
   insert row is an <li> too, so without these it grows an arrow of its own and
   the final card - no longer :last-child - starts pointing at the "+" below it.
   Both are suppressed; :has() is a progressive nicety and its absence costs a
   stray arrow, not a broken control. */
ol.steps.flow > li.stepins::before, ol.steps.flow > li.stepins::after,
ol.steps.flow > li.stepins-open::before, ol.steps.flow > li.stepins-open::after {
  content: none; }
ol.steps.flow > li:has(+ li.stepins:last-child)::before,
ol.steps.flow > li:has(+ li.stepins:last-child)::after { content: none; }
.stepins > button { padding: 1px 7px; gap: 4px; font-size: 11px; line-height: 1.5;
  color: var(--dim); border-style: dashed; background: transparent; }
.stepins > button svg.ico { width: 12px; height: 12px; }
.stepins > button:hover, .stepins > button:focus { color: #1d4ed8; border-color: #93c5fd;
  background: #f8fbff; }
.stepins-open { border: 1px dashed #93c5fd; border-radius: 8px; padding: 6px 7px;
  background: #f8fbff; margin: -10px 0 8px; }
.stepins-open .lbl { font-size: 11px; color: var(--dim); margin-bottom: 3px; }
.stepins-bad { font-size: 11px; color: #b91c1c; margin-top: 3px; }
.stepins-open .stepacts button { padding: 1px 6px; font-size: 11px; line-height: 1.5; gap: 4px; }
.stepins-open .stepacts svg.ico { width: 12px; height: 12px; }
.stepac { position: fixed; z-index: 60; min-width: 190px; max-width: 380px;
  max-height: 208px; overflow-y: auto; background: var(--panel); color: var(--ink);
  border: 1px solid var(--line); border-radius: 7px; box-shadow: 0 6px 18px rgba(15,23,42,.18);
  font: inherit; font-size: 12px; padding: 3px; }
.stepac-row { display: flex; gap: 8px; align-items: baseline; padding: 3px 6px;
  border-radius: 5px; cursor: default; }
.stepac-row .v { flex: 1 1 auto; word-break: break-all; }
.stepac-row .k { flex: 0 0 auto; font-size: 10px; color: var(--dim); }
.stepac-row.on { background: #eef2ff; color: #1e1b4b; }
.stepac-hint { padding: 3px 6px; font-size: 10px; color: var(--dim);
  border-top: 1px solid var(--line); margin-top: 2px; }
.stepac-row .k.k-agent { color: #4338ca; } .stepac-row .k.k-rule { color: #b45309; }
.stepac-row .k.k-command { color: #047857; } .stepac-row .k.k-skill { color: #7e22ce; }
.stepac-row .k.k-hook { color: #a16207; } .stepac-row .k.k-script { color: #0f766e; }

/* ---- the step editor ------------------------------------------------------
   A plain step shows exactly what it showed before: ui.js's own textarea, with
   one thin bar above it and a row of tags below. A step that CONTAINS a table
   is split into parts and the textarea is kept in the tree but hidden - ui.js's
   Apply closes over that element, so it stays the one source of truth and every
   part writes back into it. */
.stepe { display: block; }
.stepe-bar { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; margin-bottom: 4px; }
.stepe-bar button { padding: 1px 6px; font-size: 11px; line-height: 1.5; gap: 4px; }
.stepe-bar svg.ico { width: 12px; height: 12px; }
.stepe-bar .sp { flex: 1 1 auto; }
.stepe-hidden { display: none !important; }
.stepe-parts { display: flex; flex-direction: column; gap: 5px; }
.stepe-prose { min-height: 30px; resize: vertical; }
.stepe-tbl { border: 1px solid #93c5fd; border-radius: 6px; background: #f8fbff; padding: 5px 6px; }
.stepe-tbl-h { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; margin-bottom: 4px; }
.stepe-tbl-n { flex: 1 1 auto; font-size: 11px; color: var(--dim); }
.stepe-tbl-h button { padding: 1px 6px; font-size: 11px; line-height: 1.5; gap: 4px; }
.stepe-tbl-h svg.ico { width: 12px; height: 12px; }
.stepe-tbl .stepmd-tw { max-height: 140px; overflow: auto; margin: 0; background: #fff;
  border-radius: 4px; }
/* A routing table cites eighteen seats, and eighteen chips push Apply off the
   bottom of a 320px panel. The row scrolls instead. */
.stepe-chips { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; margin-top: 5px;
  max-height: 74px; overflow-y: auto; }
.stepe-chips .l { font-size: 10px; color: var(--dim); }
.stepe-chip { font-size: 10px; padding: 0 6px; border-radius: 9px; border: 1px solid var(--line);
  background: #f8fafc; color: #475569; word-break: break-all; }
.stepe-chip.k-agent { background: #eef2ff; border-color: #c7d2fe; color: #3730a3; }
.stepe-chip.k-rule { background: #fff7ed; border-color: #fed7aa; color: #b45309; }
.stepe-chip.k-cmd { background: #ecfdf5; border-color: #a7f3d0; color: #047857; }
.stepe-chip.k-script { background: #f0fdfa; border-color: #99f6e4; color: #0f766e; }
.stepe-chip.k-none { border-style: dashed; }

/* ---- the grid, inside a wide dialog ---------------------------------------
   Seventeen rows of two columns do not fit a 320px sidebar at any font size, so
   the grid is the one part of this editor that gets a dialog. The wide dialog is
   1040px, which is where a routing table stops being pipes and starts being a
   table.
   NOTE: no backtick may appear anywhere in this block. It is a template literal,
   and a stray one ends the stylesheet mid-rule and takes the rest of the file
   with it - which is exactly how this comment came to say so. */
.stepe-grid { display: flex; flex-direction: column; gap: 8px; }
.stepe-gbar { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.stepe-gbar .n { flex: 1 1 auto; font-size: 11px; color: var(--dim); text-align: right; }
.stepe-gwrap { overflow: auto; max-height: min(56vh, 520px); border: 1px solid var(--line);
  border-radius: 6px; }
.stepe-grid table { border-collapse: collapse; width: 100%; }
.stepe-grid th, .stepe-grid td { border: 1px solid var(--line); padding: 2px; vertical-align: top; }
.stepe-grid thead th { background: #f1f5f9; position: sticky; top: 0; z-index: 1; }
.stepe-grid .rowh { background: #f8fafc; width: 58px; white-space: nowrap; text-align: center;
  font-size: 10px; color: var(--dim); }
.stepe-grid .rowh button { padding: 0 4px; line-height: 1.4; }
.stepe-grid .colh { display: flex; gap: 3px; align-items: center; }
.stepe-grid .colh button { padding: 0 4px; line-height: 1.4; }
.stepe-grid svg.ico { width: 11px; height: 11px; }
.stepe-cell { width: 100%; box-sizing: border-box; font: inherit; font-size: 12px;
  border: 1px solid transparent; border-radius: 4px; padding: 2px 4px; background: transparent;
  color: inherit; resize: none; overflow: hidden; white-space: pre-wrap;
  word-break: break-word; line-height: 1.45; display: block; }
.stepe-cell:focus { border-color: #93c5fd; background: #f8fbff; outline: none; }
.stepe-grid thead .stepe-cell { font-weight: bold; }
.stepe-ghint { font-size: 11px; color: var(--dim); }
`;

function ensureStepCss(doc) {
  if (doc.getElementById("hv-step-css")) return;
  const el = doc.createElement("style");
  el.id = "hv-step-css";
  el.textContent = STEP_CSS;    // our own constant, not repository content
  (doc.head || doc.documentElement).appendChild(el);
}

// ---- markdown into an element ---------------------------------------------

/// Draw `text` into `el` as markdown. -> false when there was nothing markdown
/// about it, in which case `el` is left exactly as it was found.
function renderStepMarkdown(el, text) {
  const blocks = parseStepMarkdown(text);
  if (!stepMarkdownIsRich(blocks)) return false;
  const doc = el.ownerDocument;
  el.textContent = "";
  for (const b of blocks) el.appendChild(buildBlock(doc, b));
  return true;
}

function buildBlock(doc, b) {
  if (b.kind === "table") return buildTable(doc, b);
  if (b.kind === "list") return buildList(doc, b);
  const p = doc.createElement("div");
  p.className = "stepmd-p";
  appendInline(doc, p, b.text);
  return p;
}

function buildTable(doc, b) {
  // The wrapper scrolls and the table keeps its natural widths: forcing
  // width:100% inside a 320px panel is what shreds a real table into
  // one-character columns, which ui.html's own `.md table` rule already learned.
  const wrap = doc.createElement("div");
  wrap.className = "stepmd-tw";
  const table = doc.createElement("table");
  const thead = doc.createElement("thead");
  const hr = doc.createElement("tr");
  b.head.forEach((c, i) => {
    const th = doc.createElement("th");
    if (b.align[i]) th.style.textAlign = b.align[i];
    appendInline(doc, th, c);
    hr.appendChild(th);
  });
  thead.appendChild(hr);
  table.appendChild(thead);
  const tbody = doc.createElement("tbody");
  for (const row of b.rows) {
    const tr = doc.createElement("tr");
    row.forEach((c, i) => {
      const td = doc.createElement("td");
      if (b.align[i]) td.style.textAlign = b.align[i];
      appendInline(doc, td, c);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  wrap.appendChild(table);
  return wrap;
}

function buildList(doc, b) {
  const list = doc.createElement(b.ordered ? "ol" : "ul");
  for (const it of b.items) {
    const li = doc.createElement("li");
    // Depth by indent rather than by nesting real lists: a step's sub-list is
    // one or two levels at most, and a nesting bug that loses an item is a step
    // that lost an instruction.
    if (it.depth) li.style.marginLeft = (it.depth * 14) + "px";
    appendInline(doc, li, it.text);
    list.appendChild(li);
  }
  return list;
}

/// Every piece of repository text on this path goes in as a text node or via
/// textContent. There is no branch here that produces markup from a string.
function appendInline(doc, parent, s) {
  const str = String(s == null ? "" : s);
  INLINE_RE.lastIndex = 0;
  let last = 0, m;
  while ((m = INLINE_RE.exec(str)) !== null) {
    if (m.index === INLINE_RE.lastIndex) INLINE_RE.lastIndex++;
    if (m.index > last) parent.appendChild(doc.createTextNode(str.slice(last, m.index)));
    parent.appendChild(inlineNode(doc, m));
    last = INLINE_RE.lastIndex;
  }
  if (last < str.length) parent.appendChild(doc.createTextNode(str.slice(last)));
  return parent;
}

function inlineNode(doc, m) {
  if (m[1] !== undefined) {
    const e = doc.createElement("code"); e.textContent = m[1]; return e;
  }
  if (m[2] !== undefined) {
    const href = safeHref(m[3]);
    if (!href) return doc.createTextNode(m[0]);
    const a = doc.createElement("a");
    a.href = href; a.target = "_blank"; a.rel = "noreferrer noopener";
    a.textContent = m[2];
    return a;
  }
  if (m[4] !== undefined) {
    const e = doc.createElement("strong"); e.textContent = m[4]; return e;
  }
  if (m[5] !== undefined) {
    const e = doc.createElement("em"); e.textContent = m[5]; return e;
  }
  return doc.createTextNode(m[0]);
}

// ---- suggestions, loaded once per root ------------------------------------

let suggestState = { key: null, items: [], loading: false };

/// The graph half is free - it is already in the page. The path half is one GET
/// per root, cached, and a failure is not fatal: the graph-derived names still
/// work, so a server that refuses /paths degrades to five of the six classes.
function loadSuggestions() {
  const g = (typeof graph !== "undefined" && graph) ? graph : null;
  const root = (typeof currentRoot !== "undefined" && currentRoot) ? String(currentRoot) : "";
  const nodes = g && g.nodes ? g.nodes : [];
  const key = root + "|" + nodes.length;
  if (suggestState.key === key) return suggestState.items;
  suggestState.key = key;
  suggestState.items = suggestionsFromGraph(nodes);
  if (!suggestState.loading) {
    suggestState.loading = true;
    fetch("paths" + (root ? "?root=" + encodeURIComponent(root) : ""))
      .then(r => (r.ok ? r.json() : null))
      .then(j => {
        suggestState.loading = false;
        if (!j || !j.paths) return;
        if (suggestState.key !== key) return;      // the root changed under us
        suggestState.items = mergeSuggestions(suggestState.items,
                                              suggestionsFromPaths(j.paths));
      })
      .catch(() => { suggestState.loading = false; });
  }
  return suggestState.items;
}

// ---- the popup -------------------------------------------------------------

let ac = null;   // { box, ta, ctx, items, at }

function closeAc() {
  if (!ac) return;
  if (ac.box.parentNode) ac.box.parentNode.removeChild(ac.box);
  ac = null;
}

function refreshAc(ta) {
  const ctx = completionContext(ta.value, ta.selectionStart);
  if (!ctx || ta.selectionStart !== ta.selectionEnd) { closeAc(); return; }
  const items = rankSuggestions(loadSuggestions(), ctx, 8);
  if (!items.length) { closeAc(); return; }
  const doc = ta.ownerDocument;
  ensureStepCss(doc);
  if (!ac || ac.ta !== ta) {
    closeAc();
    const box = doc.createElement("div");
    box.className = "stepac";
    doc.body.appendChild(box);
    ac = { box: box, ta: ta, ctx: ctx, items: items, at: 0 };
  } else {
    ac.ctx = ctx; ac.items = items;
    if (ac.at >= items.length) ac.at = 0;
  }
  paintAc();
  placeAc();
}

function paintAc() {
  const doc = ac.box.ownerDocument;
  ac.box.textContent = "";
  ac.items.forEach((it, i) => {
    const row = doc.createElement("div");
    row.className = "stepac-row" + (i === ac.at ? " on" : "");
    const v = doc.createElement("span");
    v.className = "v";
    v.textContent = it.value;        // repository text, as text
    const k = doc.createElement("span");
    k.className = "k";
    // The kind carries a colour as well as a word: with `@` the list mixes six
    // classes, and picking the agent out of twenty rows should not mean reading
    // twenty labels. The class comes from our own suggestion record, never from
    // repository text - the VALUE is the repository's, and it goes in as text.
    k.className = "k k-" + String(it.kind).replace(/[^a-z]/gi, "");
    k.textContent = it.kind;
    row.append(v, k);
    // Clicking is a convenience; the keyboard is the contract. mousedown, not
    // click, so the textarea never loses focus and closes the list first.
    row.addEventListener("mousedown", ev => { ev.preventDefault(); ac.at = i; acceptAc(); });
    ac.box.appendChild(row);
  });
  const hint = doc.createElement("div");
  hint.className = "stepac-hint";
  hint.textContent = "up/down to choose - enter or tab to insert - esc to dismiss";
  ac.box.appendChild(hint);
}

/// Anchored to the textarea, not to the caret's pixel position: a mirror-div
/// caret measurement is a second copy of the box's own styling, and it goes
/// wrong silently the moment either copy changes. Below when there is room,
/// above when there is not.
function placeAc() {
  const r = ac.ta.getBoundingClientRect();
  const box = ac.box;
  box.style.left = "0px"; box.style.top = "0px";
  const h = box.offsetHeight, w = box.offsetWidth;
  const below = window.innerHeight - r.bottom;
  box.style.top = (below >= h + 6 || r.top < h + 6 ? r.bottom + 4 : r.top - h - 4) + "px";
  box.style.left = Math.max(4, Math.min(r.left, window.innerWidth - w - 6)) + "px";
}

function moveAc(delta) {
  ac.at = (ac.at + delta + ac.items.length) % ac.items.length;
  paintAc();
  const on = ac.box.querySelector(".stepac-row.on");
  if (on && on.scrollIntoView) on.scrollIntoView({ block: "nearest" });
}

function acceptAc() {
  const ta = ac.ta, item = ac.items[ac.at], ctx = ac.ctx;
  const out = applyCompletion(ta.value, ctx, item);
  ta.value = out.text;
  ta.selectionStart = ta.selectionEnd = out.caret;
  closeAc();
  // The editor below keeps ui.js's textarea as the step's one source of truth
  // and mirrors every field into it on `input`. A value assigned from script
  // fires no such event, so without this an accepted completion would land in
  // the field the reader is looking at and never reach the step being saved.
  ta.dispatchEvent(new Event("input", { bubbles: true }));
  // A directory keeps the list open on the level below it, which is how a path
  // gets typed one segment at a time instead of guessed whole.
  if (String(item.value).charAt(String(item.value).length - 1) === "/") refreshAc(ta);
  ta.focus();
}

// ---- the step editor -------------------------------------------------------
//
// ui.js draws one <textarea class="stepedit"> when a step is being edited and
// closes over that element in its Apply handler. This upgrades that textarea in
// place rather than replacing it, which is what lets a real editor exist without
// ui.js knowing: the element stays in the tree and stays the one value Apply
// reads, and everything added here writes back into it.
//
// TWO CASES, DELIBERATELY DIFFERENT.
//
//   A PLAIN STEP IS NOT MADE HEAVIER. A step is usually one sentence, and that
//   edit is as fast as it was: the same textarea, in the same place, at the same
//   size. It gains one thin bar above it and a row of tags below, and nothing
//   moves.
//
//   A STEP WITH A TABLE IS SPLIT. Prose stays prose; the table becomes a grid
//   with add and remove for rows and columns. That is the case this exists for -
//   `/implement-fr` step 4 is a seventeen-row routing table and a textarea full
//   of pipes is not an editor, it is a reason not to edit.
//
// The bytes are never in doubt. Every field mirrors into the textarea through
// `joinStepParts`, which is a line-for-line inverse of the split, and a table is
// re-rendered ONLY when the grid was applied. Open a step, change nothing, press
// Apply: the text is the text the file had.
//
// Repository text reaches these fields as `input.value` and `textarea.value` -
// properties, not markup - and reaches the preview through `buildTable`, which
// is createElement and textContent throughout. There is no HTML string here.

let editorSeq = 0;

/// The node ids the loaded graph carries, or an empty set when the page has not
/// got one yet. Read lazily for the same reason `panelState` is.
function editorIds() {
  try {
    if (typeof graph !== "undefined" && graph && graph.nodes) {
      return new Set(graph.nodes.map(x => x.id));
    }
  } catch (e) { /* the graph has not loaded yet */ }
  return new Set();
}

/// Fields the completion popup opens in. Table cells are <input>, not
/// <textarea>, and the popup only ever reads `.value` and the selection, so both
/// work; this is the one place that has to know both class names.
function isCompletionField(el) {
  return !!(el && el.classList &&
            (el.classList.contains("stepedit") || el.classList.contains("stepe-cell")));
}

function autoSize(ta) {
  ta.style.height = "auto";
  ta.style.height = Math.max(30, Math.min(ta.scrollHeight + 2, 420)) + "px";
}

/// Upgrade one of ui.js's step textareas into the editor. Idempotent: the
/// element carries a marker, so the repaint observer cannot mount twice.
function mountStepEditor(ta) {
  if (!ta || ta.dataset.hvEd) return null;
  // A prose part carries `stepedit` too - it wants ui.html's styling and this
  // file's completion delegation - which made the repaint sweep mount an editor
  // INSIDE an editor: a second toolbar, a second tag row, and the step's tags
  // counted twice. The part is not a step; it is a piece of one.
  if (ta.classList.contains("stepe-prose")) return null;
  const doc = ta.ownerDocument;
  if (!ta.parentNode) return null;
  ta.dataset.hvEd = "1";
  ensureStepCss(doc);

  const wrap = doc.createElement("div");
  wrap.className = "stepe";
  ta.parentNode.insertBefore(wrap, ta);
  const bar = doc.createElement("div");
  bar.className = "stepe-bar";
  const host = doc.createElement("div");
  host.className = "stepe-parts";
  const chips = doc.createElement("div");
  chips.className = "stepe-chips";
  wrap.append(bar, host);
  // MOVED, never removed: ui.js's Apply handler holds this exact element.
  wrap.appendChild(ta);
  wrap.appendChild(chips);

  const ed = { ta: ta, wrap: wrap, bar: bar, host: host, chips: chips,
               parts: splitStepParts(ta.value), mode: "rich", last: ta, id: ++editorSeq };
  wrap.addEventListener("focusin", ev => {
    if (isCompletionField(ev.target)) ed.last = ev.target;
  });
  // Typing in the textarea itself - the plain case, and source mode - still has
  // to keep the tags honest and the parts current.
  ta.addEventListener("input", () => {
    if (!editorIsSplit(ed)) ed.parts = splitStepParts(ta.value);
    paintChips(ed);
  });
  paintEditor(ed);
  return ed;
}

/// Whether the parts view is the one on screen. Source mode and a step with no
/// table both show ui.js's textarea, which is the same thing from here.
function editorIsSplit(ed) {
  return ed.mode === "rich" && stepPartsHaveTable(ed.parts);
}

function syncEditor(ed) {
  ed.ta.value = joinStepParts(ed.parts);
  paintChips(ed);
}

function paintEditor(ed) {
  const doc = ed.ta.ownerDocument;
  const split = editorIsSplit(ed);
  ed.host.textContent = "";
  ed.ta.classList.toggle("stepe-hidden", split);
  if (split) {
    ed.parts.forEach(p => ed.host.appendChild(p.kind === "table"
      ? buildTablePart(doc, ed, p) : buildProsePart(doc, ed, p)));
  }
  paintEditorBar(ed);
  paintChips(ed);
}

function paintEditorBar(ed) {
  const doc = ed.ta.ownerDocument;
  ed.bar.textContent = "";
  // Colour by what the control DOES, using the page's own six kinds: blue for
  // the reference picker (it inserts a citation), green for adding a table,
  // grey for the view toggle, which changes nothing at all.
  const ref = stepBtn(doc.createElement("button"), "link", "Reference");
  ref.type = "button";
  ref.className = "ui-info";
  ref.title = "insert a reference to an agent, rule, skill, command or file";
  ref.addEventListener("click", () => insertMention(ed));
  const tbl = stepBtn(doc.createElement("button"), "plus", "Table");
  tbl.type = "button";
  tbl.className = "ui-accent";
  tbl.title = "add a markdown table to this step";
  tbl.addEventListener("click", () => addTableToEditor(ed));
  ed.bar.append(ref, tbl);
  if (stepPartsHaveTable(ed.parts)) {
    const sp = doc.createElement("span");
    sp.className = "sp";
    const rich = ed.mode === "rich";
    const sw = stepBtn(doc.createElement("button"), rich ? "code" : "doc",
                       rich ? "Source" : "Editor");
    sw.type = "button";
    sw.className = "ui-quiet";
    sw.title = rich ? "edit the raw markdown instead" : "back to the split editor";
    sw.addEventListener("click", () => {
      closeAc();
      if (ed.mode === "rich") { ed.mode = "source"; }
      else { ed.mode = "rich"; ed.parts = splitStepParts(ed.ta.value); }
      paintEditor(ed);
      if (ed.mode === "source") { autoSize(ed.ta); ed.ta.focus(); }
    });
    ed.bar.append(sp, sw);
  }
}

function buildProsePart(doc, ed, part) {
  const t = doc.createElement("textarea");
  // The panel's own editor class, so this picks up ui.html's styling and this
  // file's completion delegation without a second rule for either.
  t.className = "stepedit stepe-prose";
  t.spellcheck = false;
  t.value = part.lines.join("\n");    // repository text, as a value
  t.addEventListener("input", () => {
    part.lines = t.value.replace(/\r\n/g, "\n").split("\n");
    syncEditor(ed);
    autoSize(t);
  });
  // The height is only known once it is in the document, and this runs before
  // the append; a frame later it is measurable.
  requestAnimationFrame(() => autoSize(t));
  return t;
}

function buildTablePart(doc, ed, part) {
  const box = doc.createElement("div");
  box.className = "stepe-tbl";
  const head = doc.createElement("div");
  head.className = "stepe-tbl-h";
  const n = doc.createElement("span");
  n.className = "stepe-tbl-n";
  n.textContent = "table - " + part.rows.length + " " +
                  (part.rows.length === 1 ? "row" : "rows") + ", " +
                  part.head.length + " " +
                  (part.head.length === 1 ? "column" : "columns");
  const open = stepBtn(doc.createElement("button"), "edit", "Edit table");
  open.type = "button";
  open.className = "ui-info";
  open.addEventListener("click", () => openTableEditor(ed, part));
  const drop = stepBtn(doc.createElement("button"), "trash", "Remove this table", true);
  drop.type = "button";
  drop.className = "ui-danger";
  drop.addEventListener("click", () => {
    const at = ed.parts.indexOf(part);
    if (at === -1) return;
    ed.parts.splice(at, 1);
    syncEditor(ed);
    paintEditor(ed);
    say("info", "table removed from this step",
        "nothing is written until Apply, then Save - Cancel puts it back");
  });
  head.append(n, open, drop);
  box.append(head, buildTable(doc, part));
  return box;
}

/// The `@` picker, opened deliberately rather than by remembering to type a
/// mark. It puts the `@` in for you at the caret of whichever field was last
/// focused, which is what makes tagging a button and not a convention.
function insertMention(ed) {
  const f = (ed.last && ed.last.isConnected && !ed.last.classList.contains("stepe-hidden"))
    ? ed.last
    : (ed.host.querySelector("textarea.stepe-prose") || ed.ta);
  f.focus();
  const at = typeof f.selectionStart === "number" ? f.selectionStart : f.value.length;
  const to = typeof f.selectionEnd === "number" ? f.selectionEnd : at;
  const before = f.value.slice(0, at);
  const after = f.value.slice(to);
  // `@` opens on a word boundary only, so give it one rather than have the
  // button silently do nothing in the middle of a word.
  const pad = before && !/[\s(\[`>|]$/.test(before) ? " " : "";
  f.value = before + pad + "@" + after;
  const caret = before.length + pad.length + 1;
  f.selectionStart = f.selectionEnd = caret;
  f.dispatchEvent(new Event("input", { bubbles: true }));
  refreshAc(f);
}

function addTableToEditor(ed) {
  if (!editorIsSplit(ed)) ed.parts = splitStepParts(ed.ta.value);
  const part = appendTablePart(ed.parts);
  if (!part) {
    say("warn", "a table needs a sentence in front of it",
        "write what the table is for first; a step whose first line is a table row " +
        "does not read as a step");
    ed.parts = splitStepParts(ed.ta.value);
    return;
  }
  ed.mode = "rich";
  syncEditor(ed);
  paintEditor(ed);
  openTableEditor(ed, part);
}

// ---- the grid --------------------------------------------------------------

/// The table, in a dialog wide enough to hold one.
///
/// The grid works on a COPY. Cancel therefore costs nothing and Apply is the
/// only thing that changes a byte, which matters more here than anywhere else in
/// the panel: this is the one control that can delete a row of somebody's file.
function openTableEditor(ed, part) {
  const doc = ed.ta.ownerDocument;
  if (!window.ui || typeof window.ui.modal !== "function") {
    say("error", "this build has no dialog component", "the table cannot be edited here");
    return;
  }
  const work = copyTablePart(part);
  const host = doc.createElement("div");
  host.className = "stepe-grid";
  const paint = () => paintGrid(doc, host, work, paint);
  paint();
  window.ui.modal({
    title: "Edit the table",
    icon: "state",
    wide: true,
    body: [
      "Cells are plain markdown. Type `@` in a cell for the reference picker, or a " +
      "backtick for an agent, rule or skill by name. A pipe is written escaped, so " +
      "a cell can contain one.",
      host,
    ],
    actions: [
      { id: "apply", label: "Apply table", icon: "check", kind: "primary", default: true },
      { id: "cancel", label: "Cancel", icon: "x", kind: "cancel" },
    ],
  }).then(res => {
    closeAc();
    if (!res || res.action !== "apply") return;
    part.head = work.head;
    part.align = work.align;
    part.rows = work.rows;
    part.src = work.src;
    syncTablePart(part);
    syncEditor(ed);
    paintEditor(ed);
    say("success", "table updated",
        "the step is not written until Apply, and the file not until Save");
  });
}

function paintGrid(doc, host, work, repaint) {
  host.textContent = "";
  const bar = doc.createElement("div");
  bar.className = "stepe-gbar";
  const addR = stepBtn(doc.createElement("button"), "plus", "Add row");
  addR.type = "button";
  addR.className = "ui-accent";
  addR.addEventListener("click", () => { tableAddRow(work, work.rows.length); repaint(); });
  const addC = stepBtn(doc.createElement("button"), "plus", "Add column");
  addC.type = "button";
  addC.className = "ui-accent";
  addC.addEventListener("click", () => { tableAddColumn(work, work.head.length); repaint(); });
  const n = doc.createElement("span");
  n.className = "n";
  n.textContent = work.rows.length + " x " + work.head.length;
  bar.append(addR, addC, n);

  const wrapEl = doc.createElement("div");
  wrapEl.className = "stepe-gwrap";
  const table = doc.createElement("table");

  const thead = doc.createElement("thead");
  const hr = doc.createElement("tr");
  const corner = doc.createElement("th");
  corner.className = "rowh";
  corner.textContent = "row";
  hr.appendChild(corner);
  work.head.forEach((cell, c) => {
    const th = doc.createElement("th");
    const holder = doc.createElement("div");
    holder.className = "colh";
    holder.appendChild(gridCell(doc, work, -1, c, cell));
    const rm = stepBtn(doc.createElement("button"), "trash", "Remove this column", true);
    rm.type = "button";
    rm.className = "ui-danger";
    rm.addEventListener("click", () => {
      if (!tableRemoveColumn(work, c)) {
        say("warn", "a table needs a column", "remove the whole table instead");
        return;
      }
      repaint();
    });
    holder.appendChild(rm);
    th.appendChild(holder);
    hr.appendChild(th);
  });
  thead.appendChild(hr);
  table.appendChild(thead);

  const tbody = doc.createElement("tbody");
  work.rows.forEach((row, r) => {
    const tr = doc.createElement("tr");
    const h = doc.createElement("th");
    h.className = "rowh";
    const num = doc.createElement("span");
    num.textContent = String(r + 1) + " ";
    const ins = stepBtn(doc.createElement("button"), "plus", "Insert a row below this one", true);
    ins.type = "button";
    ins.className = "ui-info";
    ins.addEventListener("click", () => { tableAddRow(work, r + 1); repaint(); });
    const rm = stepBtn(doc.createElement("button"), "trash", "Remove this row", true);
    rm.type = "button";
    rm.className = "ui-danger";
    rm.addEventListener("click", () => {
      if (!tableRemoveRow(work, r)) {
        say("warn", "a table needs a row", "remove the whole table instead");
        return;
      }
      repaint();
    });
    h.append(num, ins, rm);
    tr.appendChild(h);
    row.forEach((cell, c) => {
      const td = doc.createElement("td");
      td.appendChild(gridCell(doc, work, r, c, cell));
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  wrapEl.appendChild(table);

  const hint = doc.createElement("div");
  hint.className = "stepe-ghint";
  hint.textContent = "Apply writes this table back into the step. Nothing reaches the " +
                     "file until Save.";
  host.append(bar, wrapEl, hint);
}

/// One cell. `r` is -1 for a header cell, which is the only difference between
/// the two rows of the grid that hold text.
///
/// A textarea, not an <input>, and that is not a detail. The cells in a real
/// routing table are long - one of them names seven directories - and in a
/// single-line input everything past the column width is simply not there: you
/// cannot read the value you are editing. This wraps and grows to fit. It is
/// still ONE line of markdown: Enter is refused, and `cellSource` flattens a
/// pasted newline, so a cell can never end its own row.
function gridCell(doc, work, r, c, value) {
  const inp = doc.createElement("textarea");
  inp.rows = 1;
  inp.className = "stepe-cell";
  inp.spellcheck = false;
  inp.value = String(value == null ? "" : value);   // repository text, as a value
  inp.setAttribute("aria-label", r === -1
    ? "column " + (c + 1) + " heading"
    : "row " + (r + 1) + ", column " + (c + 1));
  const fit = () => {
    inp.style.height = "auto";
    inp.style.height = Math.max(20, inp.scrollHeight) + "px";
  };
  inp.addEventListener("input", () => {
    if (r === -1) work.head[c] = inp.value;
    else work.rows[r][c] = inp.value;
    fit();
  });
  inp.addEventListener("keydown", ev => {
    // The completion popup takes Enter first and stops it there; this is the
    // case where no popup is open, and a row is one line.
    if (ev.key === "Enter") ev.preventDefault();
  });
  requestAnimationFrame(fit);
  return inp;
}

// ---- the tags a step carries ------------------------------------------------

/// What this step currently cites, read back out of the text as it is typed.
///
/// It is the same `touches` the card shows when the step is not being edited, so
/// what appears here is exactly what will appear on the card and on the graph.
/// That is the point: a reference typed by hand and a reference chosen from the
/// picker are the same bytes, and this is where you find out whether the one you
/// typed actually landed.
function paintChips(ed) {
  const doc = ed.ta.ownerDocument;
  ed.chips.textContent = "";
  const found = touches(ed.ta.value, editorIds());
  const l = doc.createElement("span");
  l.className = "l";
  l.textContent = found.length ? "tags:" : "no references yet - Reference adds one";
  ed.chips.appendChild(l);
  for (const t of found) {
    const chip = doc.createElement("span");
    // The class comes from the node id's TYPE, which this file produced; the
    // label is repository text and goes in as text.
    const kind = t.id ? String(t.id).split(":")[0].replace(/[^a-z]/gi, "") : "none";
    chip.className = "stepe-chip k-" + kind;
    chip.textContent = t.label;
    chip.title = t.id ? t.id : "nothing in this graph carries this name";
    ed.chips.appendChild(chip);
  }
}

// ---- colour on the panel's own buttons --------------------------------------

/// ui.js draws the card's Edit/Off pair, the Apply/Cancel pair and the save bar
/// as plain buttons. They are told apart here by the sprite they carry, which is
/// the only stable thing about someone else's DOM, and given one of the page's
/// six button kinds. A sprite this does not recognise keeps the plain button it
/// had, so a rename in ui.js costs colour and nothing else.
const BTN_KIND = {
  "#i-edit": "ui-info", "#i-off": "ui-warn", "#i-on": "ui-accent",
  "#i-check": "ui-primary", "#i-undo": "ui-warn", "#i-trash": "ui-danger",
};

function colourPanelButtons(host) {
  const sel = ".stepcard > .stepacts > button, .stepbody > .stepacts > button, " +
              ".stepsave > button";
  for (const b of host.querySelectorAll(sel)) {
    if (b.dataset.hvKind) continue;
    b.dataset.hvKind = "1";
    const use = b.querySelector("use");
    const id = use ? String(use.getAttribute("href") || "") : "";
    const cls = BTN_KIND[id];
    // Save already carries ui-primary from ui.js; adding it twice is a no-op,
    // and classList.add is what keeps this from clobbering a class it did not
    // put there.
    if (cls) b.classList.add(cls);
  }
}

// ---- insert-a-step controls ------------------------------------------------

/// Which group each rendered list belongs to.
///
/// The panel draws one `<ol class="steps">` per group that HAS steps, in order,
/// so the Nth list is the Nth such group. If those two ever stop agreeing the
/// controls are not drawn at all: attaching an insert button to the wrong list
/// writes a step into the wrong procedure, which is worse than not offering it.
function listsAndGroups(host) {
  const lists = host.querySelectorAll("ol.steps");
  const state = panelState();
  const groups = state ? state.parsed.groups.filter(g => g.steps.length) : [];
  if (!state || lists.length !== groups.length) return null;
  return { lists: lists, groups: groups };
}

function insertRow(doc, g, index) {
  const li = doc.createElement("li");
  li.className = "stepins";
  const b = doc.createElement("button");
  b.type = "button";
  // A crosshair, because this control marks a POSITION rather than an object -
  // it is the one place in the panel that means "here". The sprite has no plus.
  stepBtn(b, "plus", "step here");
  b.title = "add a new step at position " + (index + 1);
  b.addEventListener("click", () => openInsert(li, g, index));
  li.appendChild(b);
  return li;
}

/// Turn the "+" into a box to type the step in. Inline rather than a modal on
/// purpose: this is a multi-line text field with an autocomplete list under it,
/// and a dialog would put both behind a layer and take the position the step is
/// going into off the screen.
function openInsert(row, g, index) {
  const doc = row.ownerDocument;
  row.className = "stepins-open";
  row.textContent = "";
  const lbl = doc.createElement("div");
  lbl.className = "lbl";
  lbl.textContent = "New step at position " + (index + 1) +
                    " - Reference tags an object, Table adds one";
  const ta = doc.createElement("textarea");
  // the same class the panel's own editor uses, so it picks up ui.html's
  // styling and this file's completion delegation without a second rule
  ta.className = "stepedit";
  ta.spellcheck = false;
  const bad = doc.createElement("div");
  bad.className = "stepins-bad";
  const bar = doc.createElement("div");
  bar.className = "stepacts";
  bar.style.marginTop = "4px";
  // The same two glyphs the card's own editor uses for Apply and Cancel, so the
  // confirm/dismiss pair reads the same wherever it appears in the panel.
  const add = stepBtn(doc.createElement("button"), "check", "Add");
  add.type = "button";
  add.className = "ui-primary";
  const no = stepBtn(doc.createElement("button"), "x", "Cancel");
  no.type = "button";
  add.addEventListener("click", () => {
    const issue = stepTextIssue(ta.value);
    if (issue) { bad.textContent = issue; return; }
    try {
      insertStep(g, index, ta.value);
    } catch (e) {
      bad.textContent = String(e && e.message ? e.message : e);
      say("error", "the step was not added", bad.textContent);
      return;
    }
    closeAc();
    // Local, exactly like Edit and drag: the group is dirty, ui.js's save bar
    // appears, and the file is written by ITS Save through POST /command. There
    // is no second write path here.
    repaintPanel();
  });
  no.addEventListener("click", () => { closeAc(); repaintPanel(); });
  bar.append(add, no);
  row.append(lbl, ta, bad, bar);
  // The same editor the cards get: a new step is as likely to want a table as an
  // existing one, and there is no reason for the two boxes to behave differently.
  mountStepEditor(ta);
  ta.focus();
}

// ---- the repaint hook ------------------------------------------------------

let decorating = false;

/// Run after every repaint of the panel. Idempotent by construction: a step body
/// that has been rendered carries a marker and is skipped, and the insert rows
/// are only added to a list that has none, so the MutationObserver that triggers
/// this cannot drive itself.
function decorate() {
  const state = panelState();
  if (!state || !state.host || !state.host.isConnected) return;
  const doc = state.host.ownerDocument;
  ensureStepCss(doc);
  decorating = true;
  try {
    for (const el of state.host.querySelectorAll(".steptext")) {
      if (el.dataset.hvmd) continue;
      // The element's own text IS the step's source, put there by ui.js with
      // textContent. Read it before touching anything, and mark the element
      // whether or not it rendered, so a plain step is examined once.
      const raw = el.textContent;
      el.dataset.hvmd = "1";
      renderStepMarkdown(el, raw);
    }
    // ui.js has just drawn a bare textarea for whichever step is being edited.
    // Upgrade it in place - the element stays, and stays the value Apply reads.
    for (const ta of state.host.querySelectorAll("textarea.stepedit:not(.stepe-prose)")) {
      mountStepEditor(ta);
    }
    colourPanelButtons(state.host);
    const pair = listsAndGroups(state.host);
    if (!pair) return;
    pair.groups.forEach((g, gi) => {
      const ol = pair.lists[gi];
      if (ol.querySelector(":scope > li.stepins, :scope > li.stepins-open")) return;
      const cards = [];
      for (const li of ol.children) if (!li.classList.contains("stepins")) cards.push(li);
      if (cards.length !== g.steps.length) return;
      cards.forEach((li, i) => ol.insertBefore(insertRow(doc, g, i), li));
      ol.appendChild(insertRow(doc, g, g.steps.length));
    });
  } finally {
    decorating = false;
  }
}

/// The panel is repainted by ui.js on every local change, which throws away
/// everything this file added. Watching for that is the whole subscription: no
/// hook in ui.js, no callback to register, and nothing to keep in step.
function installStepEditor() {
  const doc = typeof document !== "undefined" ? document : null;
  if (!doc || !doc.body) return false;
  ensureStepCss(doc);

  let queued = false;
  const obs = new MutationObserver(() => {
    if (decorating || queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; decorate(); });
  });
  obs.observe(doc.body, { childList: true, subtree: true });

  doc.addEventListener("input", ev => {
    if (isCompletionField(ev.target)) refreshAc(ev.target);
  }, true);

  doc.addEventListener("keydown", ev => {
    if (!ac || ev.target !== ac.ta) return;
    // Capture phase, so these never reach the page's own Escape handler or put
    // a newline in the box first. Nothing else is intercepted: every other key
    // types normally and the `input` handler re-ranks the list.
    if (ev.key === "ArrowDown") { ev.preventDefault(); ev.stopPropagation(); moveAc(1); }
    else if (ev.key === "ArrowUp") { ev.preventDefault(); ev.stopPropagation(); moveAc(-1); }
    else if (ev.key === "Enter" || ev.key === "Tab") {
      ev.preventDefault(); ev.stopPropagation(); acceptAc();
    } else if (ev.key === "Escape") {
      ev.preventDefault(); ev.stopPropagation(); closeAc();
    }
  }, true);

  doc.addEventListener("focusout", ev => { if (ac && ev.target === ac.ta) closeAc(); }, true);
  doc.addEventListener("mousedown", ev => {
    if (ac && !ac.box.contains(ev.target) && ev.target !== ac.ta) closeAc();
  }, true);
  doc.addEventListener("scroll", () => { if (ac) placeAc(); }, true);
  window.addEventListener("resize", () => { if (ac) placeAc(); });

  decorate();
  return true;
}

// Node requires this file; the browser does not have `module` and skips the
// line. There is no bundler here and there must not be one: the page is served
// as a single response with these sources spliced in.
if (typeof module !== "undefined" && module.exports) {
  module.exports = { parseCommandSteps, touches, serializeCommandSteps,
                     setStepText, canDisableStep, renderStep,
                     insertStep, insertGap, stepTextIssue,
                     suggestionsFromGraph, suggestionsFromPaths, mergeSuggestions,
                     completionContext, rankSuggestions, applyCompletion,
                     parseStepMarkdown, stepMarkdownIsRich, safeHref,
                     splitStepParts, joinStepParts, stepPartsHaveTable,
                     renderTablePart, syncTablePart, cellSource, copyTablePart,
                     tableAddRow, tableRemoveRow, tableAddColumn, tableRemoveColumn,
                     newTablePart, appendTablePart };
}

// The one line in this file that reaches for a browser, and it is the last one.
// Under node the condition is false and requiring this file stays free of side
// effects, which is the property tests/steps_test.rs depends on.
if (typeof document !== "undefined" && typeof window !== "undefined") {
  if (document.body) installStepEditor();
  else document.addEventListener("DOMContentLoaded", installStepEditor);
}
