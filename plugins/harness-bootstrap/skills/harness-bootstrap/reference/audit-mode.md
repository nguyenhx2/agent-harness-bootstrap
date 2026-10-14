# Audit mode - a read-only control plane beside untouched source

A workspace whose agents ANALYSE one or more product repos and never modify them: a security audit,
a compliance assessment, a due-diligence review. The assets (`protect-repos` hook, `/security-scan`,
`/triage-findings`, the finding template) live under `../assets/audit/`, installed by the `audit`
flag. Everything not overridden here follows the brownfield procedure unchanged.

## Division of labor with the `security-audit` skill

This mode **builds** the scaffolding; the `security-audit` skill **runs** the audit in it. No
procedure lives in both.

- **harness-bootstrap (audit mode)** generates the read-only auditor agents, the `protect-repos`
  guardrail, the findings tree, the standards rule, the scan/triage commands and the task loop.
- **security-audit** executes: read-and-hypothesise, the sensitive-data-at-rest sweep, scanner runs,
  review, triage, report, re-scan verification. Hand over once the workspace exists.

The generated `CLAUDE.md` POINTS at two of its references, never copies them: `standards.md` (after
mapping standards to repos, ask which standard is NOT in your table) and `sensitive-data-at-rest.md`
(the mandatory persistence-layer sweep; a negative result is still a recorded result).

## Procedure deltas

Brownfield with the write assumption inverted: agents never change product source; the user or a
delivery team applies fixes. Relative to the procedure in `../SKILL.md`:

| Step | Delta in audit mode |
|---|---|
| Analysis | Run **per repo**; each gets its own Inventory Report section (stack, entry points, secret-file naming, risky surfaces). It parameterizes auditors, not dev agents |
| Intake | Add: which standards apply per repo, the scanner strategy, the severity scale, who applies fixes |
| NEW: baseline | **Verify the standards baseline** (below), BEFORE any scan runs or any finding is written |
| Roster | The audit roster below. `.claude/` and `docs/` live at the WORKSPACE ROOT, never inside a product repo. Add `docs/findings/` |
| Guardrails | Add `protect-repos`; harden `protect-secrets` (no `.env.example` allowlist); deny `Edit`/`Write` on every repo dir in settings.json |
| `.env.example` | For the CONTROL PLANE only (scanner image tags, report options). Never inside a product repo |
| Orchestration | The task loop is unchanged ([`task-control.md`](task-control.md)); tasks are findings-to-fix and scan/triage work |
| Verify | The normal quality gate, plus: `protect-repos` blocks an in-repo write (exit 2), a scanner runs end to end on one repo, and one finding round-trips finding -> task -> re-scan |

## Workspace layout

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

The control plane's git repo ignores the repo dirs. Commit hooks apply to the control plane only
(agents never commit in product repos). Every cited path is prefixed with its repo dir. Repo
boundaries define auditor scopes 1:1.

## Standards baseline - before any finding

The standards-currency protocol (versioned table, `verified: YYYY-MM-DD` stamp, re-verification
cadence, `UNVERIFIED` marking) lives in the generated `.claude/rules/security-privacy.md`. Two
audit-specific rules on top:

- Verify the baseline with **WebSearch, dated, BEFORE the first finding is written** - a stale
  version in a rule file mis-cites requirements for the life of the project.
- **Every requirement ID cites its standard version** - IDs are renumbered, merged or removed across
  major versions. The finding frontmatter carries `standard`, `standard_version` and
  `requirement_id` as separate fields (`../assets/audit/FINDING.md`); `/triage-findings` refuses an
  unconfirmed version.

Scanner rulesets drift too (Semgrep packs, Trivy and Checkov bundles): pin image tags, record digests
in `docs/context/tool-changelog.md`, and re-pull only as a recorded decision.

## Separation of duties - three enforcement layers

NO agent modifies product source; writes are confined to `docs/` and `.claude/`. (OWASP AISVS states
the principle - cite a chapter only after confirming it against the verified baseline.) A rule alone
is not enforcement; deploy all three layers:

| Layer | Mechanism | Catches |
|---|---|---|
| 1. settings.json deny | `Edit({{REPO_N}}/**)` + `Write({{REPO_N}}/**)` per repo | The straightforward attempt, before any hook runs |
| 2. `protect-repos` hook | PreToolUse on Edit/Write: RESOLVES the target path (relative -> absolute against cwd, `..` collapsed) and blocks anything inside a repo dir | Path shapes the deny globs miss - relative paths, traversal, alternate separators |
| 3. `agent-guardrails.md` | The audit clause: read-only on product source, findings instead of fixes | Tools without layers 1-2 (non-Claude runners via `AGENTS.md`), and it keeps the model reasoning inside the constraint |

Layer 1 alone is glob-brittle; layer 2 without 3 gives agents that fight the hook instead of
registering findings.

**Test every hook's ALLOW cases, not just its BLOCK cases.** For `protect-repos`: an in-repo write
must exit 2 **and** a write to `docs/findings/<repo>/x.md` must exit 0. A real case-sensitivity
collision between repo names and the lowercased findings dirs is explained at the top of
`../assets/audit/hooks/protect-repos.ps1` and `.sh` - which is why neither may be "simplified" back
to a substring match. Read those comments before touching either.

## Scanner strategy

Decide at intake and record in `tech-stack.md`:

| Strategy | How | Trade-off | Use when |
|---|---|---|---|
| Host install | Install each scanner on the machine | Fast startup; pollutes the host, version skew between machines, install needs privileges | A single dedicated audit machine the user controls |
| **Docker (default)** | One pinned image per scanner, source bind-mounted read-only | Installs nothing; version pinned by tag + digest; the read-only mount is itself a guardrail. Slower cold start, report paths need normalizing | Almost always - it matches the audit posture: touch nothing |
| Config-only | Generate scanner configs + CI snippets; the user runs them | Zero local execution; but no agent-verifiable results, so re-scan verification is impossible | The user forbids local execution entirely |

The Docker shape - `:ro` keeps even a misbehaving scanner out of the repo. Run from the repo dir;
output leaves via stdout or a second writable mount at `docs/findings/raw/`, never a writable mount
of the source:

```
docker run --rm -v "${PWD}:/src:ro" {{SCANNER_IMAGE}}:{{PINNED_TAG}} <scanner args against /src>
```

## The secrets paradox - `.env.example` is not safe here

In someone else's repo, `.env.example` often holds real credentials copied from a working `.env` -
and whether it does is what the audit must determine:

- Generate `protect-secrets` WITHOUT the `.env.example` allowlist: every `.env*` file is secret until
  proven otherwise. The secret scanner reads the file inside its container; the agent needs only
  `file:line` + pattern type.
- `.env_dev` / `.env_staging` / `.env_prod` escape a `.env.*` glob. Derive the ACTUAL secret-file
  names per repo from the analysis and extend the deny globs and the hook pattern (`\.env[._]`
  shapes, plus whatever was found: `*.jks`, `*.mobileprovision`, `*.tfvars`, cloud credential files).
- The control plane's own `.env.example` keeps the normal rules - it is generated, not inherited.

## Audit roster

Read-only auditors replace the dev agents of [`roster.md`](roster.md). Every auditor and reviewer
gets `Read, Grep, Glob, Bash` (Bash for git history and scanners only); `Edit`/`Write` only for the
agents maintaining `docs/`. Model and effort per `roster.md` - auditor seats are review seats, not
the place to save money ([`cost-model.md`](cost-model.md)).

| Agent | Role |
|---|---|
| `orchestrator` | Routes scan/triage/review missions; owns the task loop; never analyses code itself |
| `<repo>-auditor` (one per repo) | Deep manual review: architecture, authz, data flows, stack risk. Scope = its repo dir, read-only. Findings under `docs/findings/<repo>/` |
| `sast-runner` | Runs the pinned scanner containers, normalizes into `docs/findings/raw/`, dedupes. Never judges severity |
| `security-reviewer` | Cross-repo security judgment: triage severity, confirm or reject scanner findings, map to requirement IDs |
| `perf-reviewer` | Performance findings |
| `code-reviewer` | Maintainability and quality findings |
| `spec-guardian` | RE-PURPOSED: anchors every finding to a verified `standard + version + requirement_id`; rejects bare or unverified IDs |
| `debugger` | Reproduces suspected issues read-only - a PoC in scratch space, never in the repo |
| `history-tracker` | Curates the run archive; in an audit the audit trail is part of the deliverable |

**Intentionally unfilled seats** (`roster.md`'s completeness check requires each to be named):

| Unfilled or idle seat | Covered by |
|---|---|
| Implementer (`<domain>-dev`) | THE USER applies all fixes, in the product repos |
| `devops` (installed but idle) | The user or the product teams; agents never touch CI or infra state. The seat file ships (it is unconditional) but the routing table gives it no audit missions |
| `qa-test` | The user's test suites verify fixes; agents only re-scan - verification, not testing (not installed unless `tests` is set) |
| `ba-analyst`, `merge-manager` (installed but idle) | No requirements elicitation and no merges happen in a read-only audit; the routing table gives them no missions |
| DB trio | Nobody. No schema or data work exists in a read-only audit; schema RISKS are findings owned by the repo's auditor |

The manifest installs `history-tracker` under `long` OR `audit`, so it is fielded here without `long`.

## Finding lifecycle

An agent never fixes a finding in place:

```
finding (scanner or manual) -> severity (security-reviewer) -> requirement ID (spec-guardian)
  -> task registration (/new-task + master-plan row, task status Planned)
  -> USER fixes in the product repo
  -> re-scan / re-review verifies (finding status Fixed -> Verified; its `verified:` date is set)
```

One finding, one file (`docs/findings/<repo>/FND-NNN-<slug>.md`, template `../assets/audit/FINDING.md`).
The finding's `status` and its task's status move together; a new finding's task is `Planned`
([`task-control.md`](task-control.md)). False positives are RECORDED (`status: False-positive`, with
reasoning), never deleted - the next scan would resurrect them. `/security-scan` runs the scanners
and registers new findings; `/triage-findings` walks unreviewed ones through severity, requirement
anchoring and registration.

**Convergence -> census.** When two independently dispatched agents hit the same defect CLASS, the
orchestrator registers a census task: one focused enumeration of that pattern across every repo in
scope, so the class closes with a known blast radius instead of "at least two".

## Reporting rules

- Every finding cites `path/from/workspace/root:line`; the repo prefix is mandatory.
- NEVER reproduce a secret value in a finding, task, log or report: cite `file:line` plus the pattern
  TYPE (`AWS access key shape`, `JWT`). A secret leaked into a finding file is itself Critical.
- No real personal data in evidence excerpts: describe, do not quote.
- Severity, standard, version and requirement ID live in frontmatter (machine-greppable); the prose
  explains impact and recommendation, addressed to the person who will fix it.
