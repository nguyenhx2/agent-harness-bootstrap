# Audit mode — a read-only control plane beside untouched source

How to bootstrap a workspace whose agents ANALYSE one or more product repos but never modify them: a
security audit, a compliance assessment, a due-diligence review. Copyable assets — the `protect-repos`
hook, `/security-scan`, `/triage-findings`, the finding template — live under `../assets/audit/` and
are installed by `../scripts/scaffold.py` under the `audit` flag. Everything not overridden here
follows the normal brownfield procedure: the docs tree, the task loop, the OS-aware hook generation
are unchanged.

## Division of labor with the `security-audit` skill

This mode **builds** the scaffolding; the sibling `security-audit` skill **runs** the audit inside it.
Keep the boundary sharp — no procedure lives in both places.

- **harness-bootstrap (audit mode)** generates the read-only auditor agents, the `protect-repos`
  guardrail, the findings tree, the standards rule, the scan/triage commands, and the task loop. Its
  deliverable is a workspace where an audit CAN run safely.
- **security-audit** executes: read-and-hypothesise, the sensitive-data-at-rest sweep, scanner runs,
  review, triage, report, re-scan verification. Once the workspace exists, hand over — do not re-derive
  its procedure here.

Two of its references are required reading for whoever runs the audit; the generated `CLAUDE.md` should
POINT at them, never copy them: `standards.md` (the anchoring blind spot — after mapping standards to
repos, ask what standard is NOT in your table) and `sensitive-data-at-rest.md` (the mandatory
persistence-layer sweep; a negative result is still a recorded result).

## Procedure deltas

Audit mode is brownfield with the write assumption inverted. Trigger: agents must not change product
source — fixes are applied by the user or a separate delivery team. Relative to the numbered procedure
in `../SKILL.md`:

| Step | Delta in audit mode |
|---|---|
| 0. Analysis | Run **per repo**; each gets its own Inventory Report section (stack, entry points, secret-file naming, risky surfaces). Its output parameterizes auditors, not dev agents |
| 1. Intake | Add: which standards apply per repo, the scanner strategy, the severity scale, who applies fixes |
| NEW: baseline | **Verify the standards baseline** — see below. Completes BEFORE any scan runs or any finding is written |
| 2. Roster | From the audit roster below. `.claude/` and `docs/` live at the WORKSPACE ROOT, never inside a product repo. Add `docs/findings/` beside the standard tree |
| 3. Guardrails | Add `protect-repos`; harden `protect-secrets` (no `.env.example` allowlist); extend the settings.json deny with `Edit`/`Write` globs on every repo dir |
| 4. `.env.example` | For the CONTROL PLANE only (scanner image tags, report options). Never scaffold env files inside a product repo |
| 5. Orchestration | The task loop is unchanged ([`task-control.md`](task-control.md)); tasks are findings-to-fix and scan/triage work, not features |
| 6. Verify | The normal quality gate, plus: `protect-repos` blocks an in-repo write (exit 2), a scanner runs end-to-end on one repo, and one finding round-trips finding → task → re-scan |

## Workspace layout

The workspace root holds the control plane; each product repo stays an independent git repo, untouched:

```
{{WORKSPACE_ROOT}}/
  .claude/            # control plane: agents, rules, commands, hooks, settings.json
  docs/               # standard tree + findings/
    findings/
      raw/            # normalized scanner output per run (JSON/SARIF), dated
      {{REPO_1}}/     # FND-NNN-<slug>.md per finding
      {{REPO_2}}/
  {{REPO_1}}/         # product repo (own .git) - READ-ONLY for agents
  {{REPO_2}}/         # product repo (own .git) - READ-ONLY for agents
```

Consequences of the multi-repo shape: the control plane's own git repo must ignore the repo dirs;
`guard-main-commit`-style hooks are irrelevant for product repos (agents never commit there) but still
apply to the control plane; every path an agent cites is prefixed with its repo dir, so findings are
unambiguous; and repo boundaries define auditor scopes 1:1.

## Standards baseline — before any finding

The standards-currency protocol — the versioned table, the `verified: YYYY-MM-DD` stamp, the
re-verification cadence, the `UNVERIFIED` marking — lives in the generated
`.claude/rules/security-privacy.md`. Do not restate it; follow it. Two things are specific to audit
mode and are not negotiable:

- The baseline is verified with **WebSearch, dated, BEFORE the first finding is written** — not during
  triage, not at report time. A stale version baked into a rule file mis-cites requirements for the
  life of the project.
- **Every requirement ID cites its standard version.** IDs are version-scoped — one can be renumbered,
  merged, or removed across major versions — so a bare ID is meaningless. The finding frontmatter
  carries `standard`, `standard_version`, and `requirement_id` as separate fields
  (`../assets/audit/FINDING.md`), and `/triage-findings` refuses a finding whose version is unconfirmed.

Scanner rulesets drift too (Semgrep packs, Trivy and Checkov policy bundles): pin image tags, record
digests in `docs/context/tool-changelog.md`, and re-pull deliberately as a recorded decision.

## Separation of duties — three enforcement layers

The agent that analyses code must not be the agent that modifies it. In audit mode this is absolute: NO
agent modifies product source; writes are confined to `docs/` and `.claude/`. (The principle is stated
in the OWASP AISVS — cite a chapter only after confirming it against the version you verified in the
baseline step, never from memory.) Stating it in a rule is not enforcement. Three layers, each catching
what the previous misses:

| Layer | Mechanism | Catches |
|---|---|---|
| 1. settings.json deny | `Edit({{REPO_N}}/**)` + `Write({{REPO_N}}/**)` per repo | The straightforward attempt, before any hook runs |
| 2. `protect-repos` hook | PreToolUse on Edit/Write: RESOLVES the target path (relative → absolute against cwd, `..` collapsed) and blocks anything inside a repo dir | Path shapes the deny globs miss — relative paths, traversal, alternate separators |
| 3. `agent-guardrails.md` | The audit clause: read-only on product source, findings instead of fixes | Tools without layers 1–2 (non-Claude runners via `AGENTS.md`), and it keeps the model reasoning inside the constraint |

Layer 1 without 2 is glob-brittle; layer 2 without 3 produces agents that fight the hook instead of
registering findings. Deploy all three.

**Test every hook's ALLOW cases, not just its BLOCK cases.** A hook that blocks everything passes every
block-case test and looks identical to a working hook — until it silently stops the agent writing its
own findings. For `protect-repos`: an in-repo write payload must exit 2 **and** a write to
`docs/findings/<repo>/x.md` must exit 0. That second payload is not arbitrary — there is a real
case-sensitivity collision between repo names and the lowercased findings dirs. It is explained in the
comments at the top of `../assets/audit/hooks/protect-repos.ps1` and `.sh`, which is also why neither
script may be "simplified" back to a substring match. Read those comments before touching either.

## Scanner strategy

Decide at intake and record in `tech-stack.md`:

| Strategy | How | Trade-off | Use when |
|---|---|---|---|
| Host install | Install each scanner on the machine | Fast startup; pollutes the host, version skew between machines, install needs privileges | A single dedicated audit machine the user controls |
| **Docker (default)** | One pinned image per scanner, source bind-mounted read-only | Installs nothing; version pinned by tag + digest; the read-only mount is itself a guardrail. Slower cold start, report paths need normalizing | Almost always — it matches the audit posture: touch nothing |
| Config-only | Generate scanner configs + CI snippets; the user runs them | Zero local execution; but no agent-verifiable results, so re-scan verification is impossible | The user forbids local execution entirely |

The exact Docker shape — note `:ro`, which makes even a misbehaving scanner unable to write into the
repo (a fourth, incidental enforcement layer). Run it from the repo dir being scanned, and write output
OUT via stdout or a second, writable mount pointed at `docs/findings/raw/` — never a writable mount of
the source:

```
docker run --rm -v "${PWD}:/src:ro" {{SCANNER_IMAGE}}:{{PINNED_TAG}} <scanner args against /src>
```

## The secrets paradox — `.env.example` is not safe here

The stock `protect-secrets` hook allowlists `.env.example` — correct for a repo the team itself
maintains, where that file is placeholders by construction. An audit inspects OTHER people's repos,
where `.env.example` frequently holds real credentials copied from a working `.env`. Whether it does is
precisely what the audit must determine, so the hook must not presume the answer:

- In audit mode, generate `protect-secrets` WITHOUT the `.env.example` allowlist: every `.env*` file is
  secret until proven otherwise. The secret scanner is the evidence path — it reads the file inside its
  container; the agent needs only `file:line` + pattern type, never the contents.
- Naming conventions escape stock globs: `.env_dev`, `.env_staging`, `.env_prod` use an underscore, so
  a `.env.*` glob never matches. Derive the ACTUAL secret-file names per repo from the analysis and
  extend both the deny globs and the hook pattern (`\.env[._]` shapes, plus whatever else was found:
  `*.jks`, `*.mobileprovision`, `*.tfvars`, cloud credential files).
- The control plane's own `.env.example` keeps the normal rules — it is generated, not inherited.

## Audit roster

The presets in [`roster.md`](roster.md) assume someone writes code; the audit formation replaces the
dev agents with read-only auditors. Tools for every auditor and reviewer: `Read, Grep, Glob, Bash`
(Bash for git history and scanner invocation only). `Edit`/`Write` only for the agents that maintain
`docs/`. Model and effort per the allocation table in `roster.md` — the auditor seats are review seats,
and [`cost-model.md`](cost-model.md) explains why they are not the place to save money.

| Agent | Role |
|---|---|
| `orchestrator` | Routes scan/triage/review missions; owns the task loop; never analyses code itself |
| `<repo>-auditor` (one per repo) | Deep manual review of its repo: architecture, authz, data flows, stack-specific risk. Scope = the repo dir, read-only. Writes findings under `docs/findings/<repo>/` |
| `sast-runner` | Runs the pinned scanner containers, normalizes output into `docs/findings/raw/`, dedupes against existing findings. Explicitly never judges severity |
| `security-reviewer` | Cross-repo security judgment: triage severity, confirm or reject scanner findings, map to requirement IDs |
| `perf-reviewer` | Performance findings |
| `code-reviewer` | Maintainability and quality findings |
| `spec-guardian` | RE-PURPOSED: instead of guarding FRs, it anchors every finding to a verified `standard + version + requirement_id`, and rejects bare or unverified IDs |
| `debugger` | Reproduces suspected issues read-only — a PoC in scratch space, never in the repo |
| `history-tracker` | Curates the run archive; in an audit the audit trail is part of the deliverable |

**Intentionally unfilled seats** — the completeness check in `roster.md` requires every empty seat to be
named with who covers it:

| Unfilled seat | Covered by |
|---|---|
| Implementer (`<domain>-dev`) | THE USER applies all fixes, in the product repos |
| `devops` / deploy | The user or the product teams; agents never touch CI or infra state |
| `qa-test` | The user's test suites verify fixes; agents only re-scan — verification, not testing |
| DB trio | Nobody. No schema or data work exists in a read-only audit; schema RISKS are findings owned by the repo's auditor |

## Finding lifecycle

An agent never fixes a finding in place. The lifecycle routes it to the user and back:

```
finding (scanner or manual) -> severity (security-reviewer) -> requirement ID (spec-guardian)
  -> task registration (/new-task + master-plan row, task status Planned)
  -> USER fixes in the product repo
  -> re-scan / re-review verifies (finding status Fixed -> Verified; its `verified:` date is set)
```

One finding, one file (`docs/findings/<repo>/FND-NNN-<slug>.md`, template at
`../assets/audit/FINDING.md`). The finding's `status` and its linked task's status move together —
task states are the five in [`task-control.md`](task-control.md), so a newly registered finding's task
is `Planned`. False positives are RECORDED (`status: False-positive`, with reasoning), never deleted;
the next scan would only resurrect them. `/security-scan` runs the scanners and registers new findings;
`/triage-findings` walks the unreviewed ones through severity, requirement anchoring, and registration.

**Convergence → census.** When two independently-dispatched agents converge on the same defect CLASS —
each finding a different instance of, say, the same missing-guard pattern — the orchestrator does not
merely register the two instances. It dispatches one focused enumeration pass (a "census") for that
pattern across every repo in scope, so the class closes with a known blast radius instead of "at least
two". Independent convergence is the strongest cheap signal that a defect is systemic rather than
local: spend one census on it, and register the census itself as a task so its coverage is auditable.

## Reporting rules

- Every finding cites `path/from/workspace/root:line`. A finding an auditor cannot point to is an
  opinion, and the repo prefix is mandatory in a multi-repo workspace.
- NEVER reproduce a secret value in a finding, task, log, or report — findings are committed files.
  Cite `file:line` plus the pattern TYPE (`AWS access key shape`, `JWT`). A leaked secret inside a
  finding file is itself a Critical finding.
- No real personal data in evidence excerpts: describe, do not quote.
- Severity, standard, version, and requirement ID live in frontmatter, so they are machine-greppable;
  the prose explains impact and recommendation. The audience is the person who will fix it.
