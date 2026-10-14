# Codebase analysis - deriving the harness from the source that exists

Brownfield and audit mode, BEFORE intake. Produce an evidence-based **Inventory Report** whose
mapping tables parameterize the bootstrap. Generate nothing until the report is confirmed.

## Phase A - discover

Sweep read-only (Glob/Grep/Read). Every finding carries a file path as proof.

**Parallel sweep.** The passes are independent: past ~50 source files, dispatch THREE `Explore`
agents in ONE message and merge their reports -
- agent 1: passes 1, 2, 7 (stack, layout and modules, conventions in force);
- agent 2: passes 3, 4, 5, 6 (data layer, async and infra, integrations, configuration surface);
- agent 3: passes 8, 9, 10 (risky operations, existing agent surface, git reality).

Each prompt names its passes verbatim and requires evidence paths. A smaller repo is cheaper
inline.

0. **Purpose** - what the repo produces, which sets the purpose flags intake Q0 confirms. Source
   files and a build manifest → `purpose_code`. A tree that is mostly prose, with a docs-site
   config (`mkdocs.yml`, `docusaurus.config.*`, `conf.py`, `_config.yml`) and no product source →
   `purpose_docs`. Notes, literature, datasets and citations with no build → `purpose_research`.
   Decision memos, option papers, plans and analyses → `purpose_strategy`. Two at once is common -
   a product with its own docs site is `purpose_code` + `purpose_docs`. Without `purpose_code`, skip
   the code-only passes (3, 4 and the stack half of 1) and say so in the report.
1. **Stack** - manifests → language, framework, test runner, lint/format tools, pinned versions.
   Lockfile → package manager. The scripts block → the real test/lint/build/deploy commands.
   Installed reality beats any preset ([`tech-presets.md`](tech-presets.md)).

   Glob for all of these - a project is often two at once. Add a row only with an answer in the
   third column.

   | Ecosystem | Manifests and lockfiles | What the finding drives |
   |---|---|---|
   | JS/TS | `package.json`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb` | Framework and test runner; the `scripts` block IS `{{TEST_CMD}}`/`{{LINT_CMD}}`/`{{BUILD_CMD}}`; lockfile names the package manager |
   | Python | `pyproject.toml`, `requirements*.txt`, `Pipfile`, `Pipfile.lock`, `poetry.lock`, `uv.lock`, `setup.cfg`, `tox.ini` | Runner (pytest vs unittest) for Q13; `uv.lock`/`poetry.lock`/`Pipfile` each name a different package manager, so the install and test commands differ |
   | Ruby | `Gemfile`, `Gemfile.lock`, `*.gemspec` | Rails vs plain Ruby; `rspec` vs `minitest`; `*.gemspec` means the repo SHIPS a library, which changes the licence question in Q26 |
   | .NET | `*.csproj`, `*.fsproj`, `Directory.Packages.props`, `packages.lock.json`, `nuget.config` | Target framework and test project layout; `Directory.Packages.props` means central version management, so versions are NOT in the individual project files; `nuget.config` can name a private feed, which is a supply-chain fact for `ip-compliance` |
   | Java/Kotlin | `pom.xml`, `build.gradle`, `build.gradle.kts`, `settings.gradle`, `settings.gradle.kts` | Maven vs Gradle drives the real build/test command; `settings.gradle*` enumerates the modules, which is the module map for Phase D |
   | Go / Rust / PHP | `go.mod`, `Cargo.toml`, `Cargo.lock`, `composer.json`, `composer.lock` | Toolchain and test command |
   | Monorepo | `pnpm-workspace.yaml`, `turbo.json`, `nx.json`, `lerna.json`, `settings.gradle*`, Cargo `[workspace]` | The repo is MULTI-package: glob sets take the union across packages (see Phase C), and the module map comes from the workspace member list, not from a guess at `src/` |

   Check for a monorepo marker before writing any glob. Every manifest found goes into
   `{{DEP_MANIFEST_GLOBS}}`, which path-scopes `rules/ip-compliance.md` - miss one and the licence
   gate silently never loads.
2. **Layout and modules** - source dirs one and two levels deep (`src/*`, `app/*`, `lib/*`,
   `packages/*`). Per module: purpose, rough size, and the dependencies visible cheaply.
3. **Data layer** - ORM and schema files (`schema.prisma`, `models/`, `migrations/`, `*.sql`); the DB
   engine from connection-string *names* in `.env.example`, compose, or CI - never read `.env*`
   values. Entities from the schema.
4. **Async and infra** - queue/worker code, docker/compose, IaC, hosting config, CI pipelines.
5. **External integrations** - SDK imports and HTTP clients (LLM gateways, storage, auth/SSO, email,
   payment, search). For each: which module calls it, and whether it is wrapped or scattered.
6. **Configuration surface** - grep `process.env.` / `os.environ` / `getenv` → the real variable list
   for `.env.example`. Diff against any existing one.
7. **Conventions in force** (observed, not aspirational) - naming, type strictness, error handling, UI
   primitives and design tokens (is there a `components/ui/`? a token file?), i18n and the language of
   user-facing strings, comment language, test layout, commit-subject style from
   `git log --format=%s -40`.
8. **Risky operations present** - scripts or docs mentioning force push, DB reset, mass delete, prod
   deploy; secret files on disk. These drive the deny rules and the hooks.
9. **Existing agent surface** - `.claude/`, `CLAUDE.md`, `AGENTS.md`, other tools' instruction files,
   the docs tree. What exists, what is stale (references to files that no longer exist), what conflicts
   with the standard.

   Which agentic tool drives the repo decides whether step 8 ports. Rank the evidence: the signals
   have **converged** - Cursor reads `.claude/agents/`, `.claude/skills/` and `CLAUDE.md` natively,
   and all three tools read `AGENTS.md` - so a `.claude/` directory does not prove Claude Code.

   | Evidence | Reads as | Strength |
   |---|---|---|
   | `.claude/settings.json` containing a `hooks` key | Claude Code | Strong. No other tool reads that file |
   | `.cursor/rules/*.mdc`, `.cursor/hooks.json`, or `.cursor/cli.json` | Cursor | Strong. Cursor's own formats, read by nothing else |
   | `.codex/hooks.json` or `.codex/config.toml` | Codex | Strong. Same reasoning |
   | `.cursorrules` at the repo root | Cursor, on a deprecated setup | Strong for the tool, **and a migration finding**: `.cursorrules` is superseded by `.cursor/rules/*.mdc`, so it becomes a Phase F backlog row as well as a target |
   | `.claude/agents/` or `.claude/skills/` present, no `settings.json` | Claude Code OR Cursor | **Weak.** Cursor reads both directories natively, so the files prove a harness, not a tool |
   | `CLAUDE.md` present, no `.claude/` | Claude Code OR Cursor | **Weak.** Same reason |
   | `AGENTS.md` alone | Claude Code, Cursor, or Codex | **None. ASK, do not guess** |
   | No `.codex/` anywhere | nothing | **Weak evidence of anything.** Codex loads a project-local `.codex/` only when the project is marked trusted, so a Codex user can leave no trace in the repo at all |

   Pre-select only Strong rows. A Weak or None row goes to the user as intake question 3a
   ([`intake.md`](intake.md)). Disagreeing signals - a `.cursorrules` beside a
   `.claude/settings.json` with hooks - mean BOTH are reported and offered.

   Then record **who wrote** any pre-existing `.cursor/` or `.codex/`: grep it for
   `generated by port.py` (stamped into every `.mdc` comment and every `hooks.json`
   `_generated_by` key). Porter output is PRESENT-OK or PRESENT-DRIFT and may be re-emitted; a
   hand-authored file is a **CONFLICT** the user resolves.
10. **Git reality** - default branch, branch naming, hosting platform, existing PR/MR conventions.

    The platform decides which CLI the seats use. The remote alone is not conclusive: self-hosted
    GitLab and Bitbucket Server sit on a company hostname.

    | Evidence | Reads as | Strength |
    |---|---|---|
    | `.gitlab-ci.yml` at the repo root | GitLab | Strong. A GitLab runner is the only thing that consumes this file |
    | `.github/workflows/` | GitHub | Strong. Same reasoning |
    | `bitbucket-pipelines.yml` | Bitbucket | Strong |
    | `git remote get-url origin` host is `github.com` / `gitlab.com` / `bitbucket.org` | that platform | Strong for cloud, absent for self-hosted |
    | Remote host is neither, plus one of the CI files above | that platform, self-hosted | Strong when the CI file agrees |
    | Remote host is neither and there is no CI file | unknown | None. ASK, do not guess |

    Disagreeing signals (a `.gitlab-ci.yml` under a `github.com` origin is a real migration state)
    mean ASK, reporting both sides.

    Then record whether the CLI is authenticated, logged out or absent (`gh auth status`,
    `glab auth status`). Bitbucket has no such CLI - intake Q11 covers it.

## Phase B - the Inventory Report

Present ONE report, about two screens:

```markdown
# Inventory Report - <repo>

## Stack (evidence-based)
| Dimension | Finding | Evidence |
|-----------|---------|----------|
| Language/framework | ... | package.json:... |
| DB/ORM | ... | prisma/schema.prisma |
| Queue/worker | ... | src/worker/ |
| Hosting/CI | ... | .gitlab-ci.yml |
| Test | ... | vitest.config.ts |

## Modules
| Module | Path | Spec module | Purpose | Size | Proposed owner agent |
|--------|------|-------------|---------|------|----------------------|

## Integrations
| Provider | Wrapped in | Called from |
|----------|-----------|-------------|

## Conventions observed
- ... (each with a file example)

## Risky operations found
- ... (each -> proposed deny rule or hook)

## Existing agent surface
- what exists / stale / conflicting

## Flags and globs (feeds vars.json)
- flags: ...
- {{SOURCE_GLOBS}} / {{UI_GLOBS}} / {{DB_GLOBS}} / {{TEST_GLOBS}}: ...

## Gaps vs standard
- ... (numbered; becomes the migration backlog)
```

Get explicit confirmation or corrections before moving on. Corrections override findings.

**The report is a hypothesis.** Later work may invert it - a control assumed present proves absent,
a severity escalates. Let evidence win: update the master-plan, the severity and the report; never
argue the evidence back into agreement.

## Phase C - flags and globs

Two outputs the scaffolder cannot infer. A rule scoped to a nonexistent path never loads - a
silently dead guardrail.

**Flags** - set from evidence, confirmed at intake:

| Flag | Set when the analysis finds |
|---|---|
| `purpose_*` | Pass 0 - one or more of `purpose_code`, `purpose_research`, `purpose_strategy`, `purpose_docs` |
| `ui` | A rendering layer: components, pages/routes, templates, a design-token or CSS-framework config |
| `db` | A schema, an ORM, or migrations |
| `ai` | An LLM/model provider SDK whose output reaches users or drives a decision |
| `audit` | Set by mode, not by evidence - agents will never write to the source |
| `windows` / `posix` | The dev OS (detected, then confirmed) |

**Glob sets** - from the ACTUAL tree, never a framework's idealized layout. Confirm each matches at
least one real file before it goes into `vars.json`.

| Var | Scopes the rule | Typical shape (confirm against the tree) |
|---|---|---|
| `{{SOURCE_GLOBS}}` | `coding-standards`, `code-quality`, `performance` | `src/**/*.{ts,tsx}` - every module path from A.2 |
| `{{UI_GLOBS}}` | `frontend` (flag `ui`) | `src/components/**`, `src/app/**/*.tsx` |
| `{{DB_GLOBS}}` | `data-model` (flag `db`) | `prisma/**`, `src/db/**`, `**/migrations/**` |
| `{{TEST_GLOBS}}` | `testing` | `**/*.{test,spec}.*`, `tests/**`, `e2e/**` |

A monorepo takes the union across packages (`packages/*/src/**`). Flat code with no separation is
scoped to its directory, not to an invented structure.

## Phase D - mapping tables

**Modules → dev agents.** One dev agent per cohesive feature domain, NOT per directory. Merge tiny
related modules; split a grab-bag `lib/` by domain. A cross-cutting layer everything calls (an LLM
client, an integrations dir) gets its own owner. UI gets ONE frontend agent regardless of page
count. Feeds `{{MODULE_PATHS}}`, `{{ROUTING_TABLE}}`, and the roster ([`roster.md`](roster.md)) -
the routing table must cover every agent and every module: no orphans either way.

The report's **Spec module** column carries the code from `docs/specs/modules/<module>/` this module
implements (`BLG` for `FR-BLG-nn`), or `-` for a flat spec set. The owner's scope names both the code
paths and that spec folder; a spec module with no code module (or the reverse) is a reported gap.

**Conventions → rules.** Write `coding-standards`, `frontend`, `data-model`, `testing` from the OBSERVED
conventions. Where observation contradicts good practice (no strict mode, hardcoded colors), do NOT
write the rule as though the code already complied: write the target rule and register the cleanup as a
backlog task. Where a real design system exists, enumerate its actual primitives and make reviewer
enforcement explicit.

**Risky ops → gates and hooks.** Each maps to a settings.json deny rule (stack-specific:
`{{DB_RESET_PATTERN}}` is the real command, never a guess), a hook check, or a gated command. Secret
files found in the repo extend the Read-deny globs.

**Integrations → env and mocking policy.** Each produces a commented group in `.env.example`, a "mock in
tests" line in `testing.md`, and - if it handles sensitive data - a paragraph in `security-privacy.md`.

## Phase E - reconcile against the standard

Diff the existing surface against what `../scripts/scaffold.py` would install. Classify every item;
the class IS the action. Generation never clobbers.

| Class | Meaning | Action |
|---|---|---|
| MISSING | Standard asset absent | **Add** - the scaffolder writes it, parameterized by the mapping tables |
| PRESENT-OK | Exists and matches the standard's intent | **Keep** as-is. The scaffolder reports it as `KEPT` |
| PRESENT-DRIFT | Exists but stale, incomplete, or partly conflicting | **Adapt** in place: add the missing sections, fix broken paths, align frontmatter - minimal edits, preserving user content, and say what changed. This is the scaffolder's `CONFLICT` queue |
| CONFLICT | Contradicts a standard guardrail (a hook that permits force-push, a rule that allows prod writes) | **Flag** to the user as a decision. Never silently resolved either way |
| EXTRA | Exists, not in the standard, not harmful | **Keep and register** in `00-overview.md` / `AGENTS.md`. The standard is a floor, not a ceiling |

Never delete or rewrite a file the user authored, and never "fix" product source during bootstrap:
convention violations become backlog tasks. The bootstrap touches only `.claude/`, `docs/`, the root
instruction files, `.env.example` and the CI stub.

## Phase F - migration backlog

Every gap and convention deviation becomes registered work, grouped into a few large tasks the
user approves:

- `docs/tasks/master-plan.md` gets a "Phase 1 - standardization" section.
- One `TASK-NNN` row per group of related gaps. Owner = the agent that owns that concern. P0 for guardrail gaps, P1 for
  convention drift, P2 for nice-to-haves.
- Create the task files for the P0 items immediately, from `docs/templates/TASK.md`. They
  start at status `Planned` - see [`task-control.md`](task-control.md).
