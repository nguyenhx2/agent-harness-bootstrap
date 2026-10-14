---
description: Check DOCS traceability - which documents define which IDs, who references them, and which IDs are orphaned. Traceability, not dependency.
allowed-tools: Read, Grep, Glob, Bash(python:*), Bash(python3:*), Bash(git diff:*)
---

Maintain the documentation twin of `/harness-bootstrap:code-graph` in the repo you are currently
in. The two graphs answer different questions and neither substitutes for the other:

- **Code graph**: module boundaries - which module may import which.
- **Docs graph** (this command): traceability - which spec section, requirement, ADR, and task
  talk about the same thing, and which IDs are orphaned.

**Preflight.** Needs `.claude/scripts/docs-graph.py` and a `docs/` tree. If either is missing, say
which one and stop.

What a run produces:

- stdout - the doc/ID/edge counts and the orphan-ID list. That list is the result; nothing is drawn.
- `.claude/state/docs-graph.json` - machine-readable: every ID (FR-, NFR-, BR-, ADR-, TASK-, ...),
  the document that defines it, every document that references it. Query it for "which documents
  mention FR-12" - or grep the ID, which gives the same answer for one ID.

Procedure:

1. Run: `python .claude/scripts/docs-graph.py --check`. It is not rebuilt automatically; run it
   after editing documents that define or cite IDs.
2. Report each orphan by name and say which it is: unstarted work (a requirement no task or other
   document references yet) or a dead reference (an ID cited once, defined nowhere). An ID whose
   defining document changed usually means a requirement got rewritten in place - check the
   revision history caught it.

How agents use it:

- **spec-guardian** checks a diff's claimed requirement IDs against the graph: an implementation
  naming an FR the graph does not know is implementing an invented requirement.
- The **orchestrator** uses orphan IDs as a backlog signal: a requirement no task ever references
  is work nobody scheduled.
- **ba-analyst** runs `--check` after editing specs: exit 1 means the edit broke traceability.
