---
description: Run the pinned deterministic scanner suite in Docker against the product repos and record new findings.
argument-hint: [repo-slug] (omit to scan every repo in the workspace)
allowed-tools: Bash(docker run --rm:*), Bash(docker images:*), Read, Grep, Glob, Write
---

Run the deterministic scanner layer against repo **$1**.

If $1 is empty, scan every product repo in the workspace. If $1 names a repo that does not exist in
the workspace, stop and list the repos that do.

1. Dispatch `sast-runner`. It runs every scanner in its pinned matrix (SAST, secrets, dependency
   and CVE, infrastructure-as-code policy) against the target repo or repos, using the read-only
   mount shape. The read-only mount is a guardrail, not a convenience: it is what makes it
   impossible for a scanner to write into product source.
2. Raw output goes to `docs/findings/raw/`, one file per scanner per repo, in a machine format
   (JSON or SARIF) wherever the scanner offers one.
3. `sast-runner` normalizes and dedupes each result against `docs/findings/<repo>/`. Secret matches
   are REDACTED to location plus pattern type before anything touches disk. A raw findings file
   that contains a live credential is a new incident, not a report.
4. For each NEW result, create a finding file from the finding template with `status: New` and
   `source:` set to the scanner that produced it.
5. For each regression of a previously fixed finding, set that finding back to `status: Confirmed`
   and note the reopening in its file. Do not create a duplicate.
6. Report counts per repo and per scanner: new, known, reopened, and fixed since the last run. Then
   report coverage gaps: a scanner that crashed or timed out is missing coverage, not a clean
   result. Never silently skip a failed scan.
7. Do NOT assign severity and do NOT anchor requirement IDs here. That is triage, and it needs a
   human-visible trail: run `/triage-findings` on the new findings.

Agents are read-only on product source. This command scans and records; the user applies the fixes.
