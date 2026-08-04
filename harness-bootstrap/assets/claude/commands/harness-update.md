---
description: Re-run the harness bootstrap on this repo to pick up new assets, add or retire agents, or re-derive scopes after the codebase changed - reconciling, never clobbering.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(python:*), Bash(python3:*), Bash(git diff:*), Bash(git status), AskUserQuestion
---

Update an already-bootstrapped harness in place. Safe to run any number of times: the scaffolder
never overwrites a differing file, so everything you or your team edited survives as a `CONFLICT`
for you to merge deliberately.

Procedure:

1. **Re-read reality first.** If the codebase changed since bootstrap (new modules, renamed paths,
   new integrations), re-run the codebase analysis for the changed areas and update the module→agent
   mapping. A dev agent scoped to a path that no longer exists is a seat pointing at nothing.
2. **Re-run the scaffolder** with the existing `vars.json` (update variables first if intake answers
   changed):
   `python <skill>/scripts/scaffold.py --target . --vars vars.json`
   Read the report: `ADDED` are new assets from a newer skill version, `KEPT` are unchanged, and
   `CONFLICT` is the reconciliation queue - resolve each by hand (keep / adapt / take-new), never
   in bulk with `--force`.
3. **Roster changes.**
   - Adding an agent: instantiate `dev-agent.md` (or copy the closest seat), give it explicit
     `model`, `effort`, `tools`, `maxTurns`, and a real path scope, then add it to the
     orchestrator's routing table in the same change - a seat outside the routing table is
     unreachable, a routing row without a seat is a dispatch to nowhere.
   - Retiring an agent: remove the routing row first, confirm no Active task names it as owner
     (`/board-audit`), then delete the seat file.
4. **Re-port** if the repo is also used from Cursor or Codex:
   `python <skill>/scripts/port.py --target . --tool all`
5. **Verify**: the scaffolder's spawn-boundary lint passed (exit 0), the routing table covers every
   seat, and the hooks still fire (run one known-bad payload by hand). Record what changed in
   `docs/context/tool-changelog.md`.

What this never does: rewrite `tech-stack.md`, `coding-standards.md`, scopes, or any authored
content from a template. Those were derived from your code and your answers; the update touches
them only through the CONFLICT queue with you deciding.
