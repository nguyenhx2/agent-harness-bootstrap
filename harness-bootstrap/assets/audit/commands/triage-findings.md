---
description: Walk untriaged findings through confirmation, severity, requirement anchoring, and task registration.
argument-hint: [repo-slug] (omit to triage every repo)
allowed-tools: Read, Grep, Glob, Edit, Write
---

Triage every finding with `status: New` under `docs/findings/`.

If $1 names a repo, restrict the triage to `docs/findings/$1/`. If $1 is empty, triage the findings
of every repo in the workspace.

1. Confirm or reject each finding. Dispatch `security-reviewer`, or `perf-reviewer` or
   `code-reviewer` according to the finding type. A rejected finding is set to
   `status: False-positive` and KEEPS the reasoning in its file. Nothing is deleted: the next scan
   will raise it again, and the recorded reasoning is what stops the team from re-triaging it.
2. Confirmed findings get a severity on the project scale, then `spec-guardian` anchors each one:
   `standard`, `standard_version`, and `requirement_id`, all taken from the verified standards
   table.

   REFUSE to anchor, leave the finding at `status: New`, and report it as blocked when the
   standards table row is missing, marked unverified, or carries no verification date. An
   unverified version means the requirement ID may cite the wrong control, which is worse than
   citing nothing at all.
3. Register each confirmed finding as work: run `/new-task`, one task per finding or one per
   coherent group. Link the two both ways: the `task:` field in the finding, the finding ID in the
   task. The task starts at `status: Planned` on the board, exactly like any other task. There is
   no separate "registered" state.
4. The user fixes. After their fix, re-run the originating check: `/security-scan <repo>` for a
   scanner finding, or the originating review for a manual one. Only a clean result sets the
   finding to `status: Verified` and fills its `verified:` field. A finding never closes on a claim
   that it was fixed, only on a clean re-check. Agents NEVER apply the fix themselves.
5. Summarize: triaged, rejected, registered, and blocked-on-baseline, broken down by repo and
   severity.
