---
description: Scan the current changes for secrets and sensitive data before a commit or {{PR_OR_MR}}.
allowed-tools: Bash(git diff:*), Bash(git status), Grep, Read
---

Scan the current changes (`git diff` and `git diff --staged`) for:

- Credential patterns: `sk-`, `AKIA`, `AIza`, `ghp_`, `glpat-`, `xox`, JWT-shaped strings,
  `BEGIN PRIVATE KEY`, and hardcoded `password=`, `api_key=`, `secret=`, `token=` assignments.
- Forbidden files: `.env` and every `.env*` variant except `.env.example`, `*.pem`, `*.key`,
  `*.jks`, `*.p12`, `*.tfvars`, service-account JSON, and private key material of any kind.
- Real-looking personal or customer data in fixtures, seeds, snapshots, and test data. Synthetic
  data only.
- Secrets in places people forget: CI configuration, container files, committed lockfiles,
  documentation examples, and code comments.

Report `file:line` plus the pattern TYPE only. Never print the matched value, not even truncated,
and never write it into a task file, finding, or commit message.

Any hit is a blocker. The change does not proceed until the value is removed from the diff AND the
credential is rotated. A secret that reached a commit is compromised even after the commit is
amended: rotation is not optional.
