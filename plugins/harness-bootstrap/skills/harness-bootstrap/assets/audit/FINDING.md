---
id: FND-NNN
repo: <repo slug>
title: <short title>
severity: <Critical | High | Medium | Low | Info>
standard: <standard name, or "none" for a pure performance or quality finding>
standard_version: <version, from the verified standards table - never from memory>
requirement_id: <requirement ID within THAT version - meaningless without standard_version>
source: <scanner name, or "manual review (<agent>)">
status: New # New | Confirmed | False-positive | Fixed | Verified
task: <TASK-NNN, filled at registration - the task itself starts at status Planned>
found: <YYYY-MM-DD>
verified: <YYYY-MM-DD, filled only when a clean re-check confirms the fix>
---

<!-- Finding files are written 100% in English. One finding is one file. -->

# FND-NNN: <short title>

## Evidence

<!-- Paths are workspace-root-relative so the repo is unambiguous. Never paste a secret value or
     real personal data: pattern type and location only. -->

- `<repo>/<path>:<line>` - <what is there, and why it is a problem rather than merely unusual>

## Impact

<Who can do what because of this, and under which preconditions. An impact statement that cannot
name an actor and an action is a code smell, not a finding.>

## Recommendation

<What the user should change. Written for the human who applies the fix; agents do not apply it.>

## Verification

- Re-check: <the exact scanner command, or the manual check to repeat>
- Expected: <what a clean result looks like>

<!-- Lifecycle: New -> Confirmed (or False-positive, with the reasoning kept) -> registered as a
     task, which enters the board at status Planned -> the user fixes it (Fixed) -> a clean
     re-check sets Verified. A finding never closes on a claim, only on a clean re-check. -->
