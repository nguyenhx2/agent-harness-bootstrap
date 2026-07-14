# Environment configuration (project-bootstrap)

Reference for the `project-bootstrap` skill: how to generate the `.env.example` from the intake
answers. The copyable scaffold lives in `templates/env-example.template`.

## Table of contents

- [Rules](#rules)
- [Sample shape](#sample-shape)
- [Cross-check and wiring](#cross-check-and-wiring)

## Rules

Generate a complete `.env.example` at the repo root from the Batch B / 6b answers - it is the single
source of truth for what configuration the system needs. Brownfield mode: derive the variable list
from the ACTUAL config reads found during codebase analysis (`process.env.*` / `os.environ` /
framework config, plus `docker-compose.yml` and CI files) and reconcile with any existing
`.env.example` - never guess variables and never read real `.env*` values.

- **Placeholder values only** (empty or `your-...-here`); the real files (`.env`, `.env.local`) are
  gitignored, hook-blocked from agent reads, and never committed. `.env.example` is the ONE env file
  agents may read.
- **Every variable documented**: a comment line above each var stating what it is for, which service
  consumes it, and where the real value lives per environment (e.g.
  "dev: .env.local / prod: platform variables" or "CI only: GitLab CI/CD masked variable").
- **Cover every case the stack answers imply** - one commented group per concern.

## Sample shape

A full placeholder scaffold (adapt the groups to the project's stack answers) is provided as
`templates/env-example.template`. It covers, as commented groups: app base URL + NODE_ENV; database
connection (and an optional separate test DB); queue (Redis); LLM gateway API key + default model;
optional vision/image-extraction model; KMS/RAG base URL + key; object storage endpoint/keys/bucket;
auth mode + SSO client IDs; and feature flags / logging. Remove groups the stack does not use and add
any the stack needs that are not listed.

## Cross-check and wiring

- Cross-check completeness: every integration named in the tech-stack rule and `system-overview.md`
  must have a group here, and vice versa (no orphan vars). Add a `docker-compose.yml` for the local
  services the vars point at (DB, Redis, ...) when the stack needs them.
- Wire it in: README "Getting started" copies `.env.example` -> `.env.local`;
  `rules/security-privacy.md` references it; CI never consumes `.env*` (platform variables only).
