---
description: Ingest a new source (meeting notes, transcript, legacy doc, email thread) into an existing spec set - reconciled section by section, versioned in the revision history, and rippled to the agent files that depend on the changed content.
allowed-tools: Read, Grep, Glob, Write, Edit, AskUserQuestion, Bash(python:*), Bash(python3:*), Bash(git diff:*), Bash(git log:*)
---

Fold a new information source into `docs/specs/` without regenerating anything. Usage:
`/spec-ingest <path-or-pasted-source>`.

The rules that govern spec writing keep governing here: nothing is invented, every unknown is
written as `<unknown - OI-nn>` in its cell (never left blank), IDs are stable forever, and the
source of truth is the spec section - never the raw source being ingested.

Procedure:

1. **Read the source whole**, then map each extractable statement to its home section (03 glossary
   term, 05 FR or business rule, 07 NFR, 02 stakeholder, ...). A section may be a single file or a folder
   (`05-functional-requirements/` with `FR-nn-<slug>.md` files and a `README.md` index) - in folder
   form, an FR statement lands in its FR's own file and the index tables update in the same change.
   A statement mapping to a section that was not selected at creation is a finding: surface it and
   offer to add the section (re-run the scaffolder for that file), never force it elsewhere.
   **In module form** (`docs/specs/modules/<module>/` exists), map the statement to a MODULE too:
   the module's code is the ID segment, so `FR-BLG-02` belongs to the module whose code is `BLG`
   in the root `README.md` table, and its home is that module's folder. A statement that names no
   module and matches none of their scopes is an ambiguity, not a default: **refuse to place it**,
   name the candidate modules, and ask which owns it - a requirement filed into the wrong module
   gets the wrong owner, the wrong ID, and the wrong dev agent. Cross-cutting statements (glossary,
   assumptions, revision history) go to the root sections as always.
2. **Diff before writing.** For each mapped statement, compare against what the section already
   says:
   - New fact, no conflict: add it, with a source note.
   - Conflict with existing normative text: DO NOT silently overwrite. Show both versions, ask
     which wins (AskUserQuestion when it is a closed choice), and record the loser in the revision
     history row - a requirement that flips twice is a requirement someone must notice flipping.
   - Restates what exists: skip, note the corroboration in the row's source list.
3. **New IDs are appended, never renumbered.** A new requirement takes the next free `FR-nn`;
   retired meaning is handled by `/spec-retract`, not by reusing numbers. In folder form, a new FR
   is a new `FR-nn-<slug>.md` plus its row in the folder's `README.md` summary table. In module
   form the next free number is counted **within the module** (`FR-BLG-07` after `FR-BLG-06`,
   whatever `FR-CAT-` is up to), and the segment is never omitted - a bare ID inside a module
   folder collides silently with the other modules' in the traceability graph.
4. **Version it**: one row in `13-revision-history.md` per ingest - date, source name, sections
   touched, IDs added/changed, who approved the conflicts. This row is the undo map.
5. **Ripple to the harness** (only where the target repo has one):
   - Glossary changes -> `docs/context/glossary.md` (seeded copy) so the DDD ubiquitous language
     stays true; a renamed term is a conflict, not a merge.
   - FR added/changed -> the owning dev agent's `description:` FR list and the orchestrator's
     routing awareness; a new FR with no owning module goes to the board as a Pending task, not
     silently into a seat. In module form the owner is the dev agent that owns
     `docs/specs/modules/<module>/`.
   - Business rules -> `docs/context/business-rules.md` and note for `spec-guardian`.
   - Then rebuild traceability: `python .claude/scripts/docs-graph.py` and
     `python .claude/scripts/graph-html.py`. New orphan IDs are the ingest's loose ends - list
     them.
6. **Report**: sections touched, IDs added/changed, conflicts and their resolutions, ripples
   applied, orphans created. Record the ingest in `docs/context/tool-changelog.md`.

What this never does: regenerate a section from a template over hand-written content, renumber an
ID, or let the raw source become the reference - the spec absorbs the source; the source does not
replace the spec.
