---
description: Retract a source or correct information already in the spec set - traced through every section that absorbed it, versioned, with downstream agents and tasks told what they lost.
allowed-tools: Read, Grep, Glob, Write, Edit, AskUserQuestion, Bash(python:*), Bash(python3:*), Bash(git diff:*), Bash(git log:*)
---

Remove or correct information in `docs/specs/`. Usage:
`/spec-retract <source-name | ID | quoted-claim>` - a whole source that turned out unreliable, a
single requirement that is wrong, or a specific claim to correct.

Retraction is harder than ingestion because the spec has already metabolized the information. The
job is tracing what absorbed it, not deleting a paragraph.

Procedure:

1. **Trace the blast radius.** Find every place the retracted content landed: grep the sections
   (files and section folders alike - a split section keeps its content under `NN-<name>/`) for
   the source's name in source notes, the ID, or the claim's key terms; then check
   `.claude/state/docs-graph.json` for every document referencing the affected IDs, and the task
   board for tasks naming them. Show the full list BEFORE changing anything.
2. **Correct, do not vaporize:**
   - A wrong VALUE (a limit, a rate, a name): fix it in the defining section, one revision-history
     row, done.
   - A claim with no remaining source: the text does not vanish - it converts to the open-issue
     form (`OI-nn`: "was asserted by <source>, source retracted, needs confirmation"), because a
     silently deleted requirement looks identical to one that never existed, and someone built on
     it.
   - A whole retracted source: every statement that ONLY that source supported converts as above;
     statements corroborated by surviving sources lose one source note and stay.
3. **IDs never come back.** A retracted `FR-nn` keeps its number, marked Withdrawn with the reason
   and date in place. The next requirement takes a fresh number. Reusing a dead ID poisons every
   old reference to it.
4. **Version it**: one `13-revision-history.md` row - what was retracted, why, which IDs went
   Withdrawn or converted to `OI-nn`, who decided.
5. **Ripple outward** (where a harness exists): the owning dev agent's FR list drops the withdrawn
   IDs; Active tasks implementing them go `Blocked` with `human_gate: requirement withdrawn` -
   never silently deleted, a human decides whether the work stops; glossary terms that only the
   retracted source defined are marked disputed in `docs/context/glossary.md`. Rebuild
   traceability: `python .claude/scripts/docs-graph.py` then
   `python .claude/scripts/graph-html.py` - the new orphan list is the checklist of things the
   retraction orphaned.
6. **Report**: the blast radius, what converted vs corrected vs stayed, blocked tasks, orphans.
   Record in `docs/context/tool-changelog.md`.
