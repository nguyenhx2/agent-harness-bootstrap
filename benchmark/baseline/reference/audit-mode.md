# Audit mode - read-only assessment control plane (project-bootstrap)

Reference for the `project-bootstrap` skill: how to bootstrap a workspace whose agents ANALYSE
one or more product repos but never modify them - a security/performance audit, a compliance
assessment, a due-diligence review. Copyable assets (auditor/sast-runner/perf-reviewer bodies,
the `protect-repos` hook, `/security-scan`, `/triage-findings`, the finding-file template, the
read-only settings fragment) live in `templates/audit-pack.md`. Everything not overridden here
follows the normal brownfield procedure - the docs tree, the task-control loop, and the OS-aware
hook generation are unchanged.

Sibling references: standards versions come from `reference/security-review.md` (the verified
standards table - single source of truth, do not duplicate it); review checklists from
`reference/code-quality-review.md` and `reference/performance-review.md`.

## Table of contents

- [Division of labor with the security-audit skill](#division-of-labor-with-the-security-audit-skill)
- [When audit mode applies - procedure deltas](#when-audit-mode-applies---procedure-deltas)
- [Multi-repo control-plane layout](#multi-repo-control-plane-layout)
- [Verify the standards baseline (MANDATORY, before any finding)](#verify-the-standards-baseline-mandatory-before-any-finding)
- [Separation of duties - three enforcement layers](#separation-of-duties---three-enforcement-layers)
- [Two-layer model - knowledge + deterministic](#two-layer-model---knowledge--deterministic)
- [Scanner strategy - host vs Docker vs config-only](#scanner-strategy---host-vs-docker-vs-config-only)
- [The secrets paradox - .env.example is not safe here](#the-secrets-paradox---envexample-is-not-safe-here)
- [Audit roster - filled and intentionally unfilled seats](#audit-roster---filled-and-intentionally-unfilled-seats)
- [Finding lifecycle](#finding-lifecycle)
- [Reporting rules](#reporting-rules)

## Division of labor with the security-audit skill

This mode BUILDS the scaffolding; the sibling **`security-audit` skill**
(`../../security-audit/SKILL.md`) RUNS the audit inside it. Keep the boundary sharp - no
procedure lives in both places:

- **project-bootstrap (audit mode)** generates: read-only auditor agents, the `protect-repos`
  guardrail, the findings tree, the verified standards table, the scan/triage commands, the task
  loop. Its deliverable is a workspace where an audit CAN run safely.
- **security-audit** executes: read-and-hypothesise, the sensitive-data-at-rest sweep, scanner
  runs, review, triage, report, re-scan verification (its phases 0-8). When the bootstrap is
  done and the user wants the audit performed, hand over to `security-audit` - do not re-derive
  its procedure from this file.

Two of its references are REQUIRED reading for whoever runs the audit; the generated CLAUDE.md
and audit rules should POINT at them, never copy them:

- `security-audit/reference/standards.md` - the anchoring blind spot: after mapping standards to
  repos, ask what standard is NOT in your table.
- `security-audit/reference/sensitive-data-at-rest.md` - the mandatory persistence-layer sweep;
  a negative result is still a recorded result.

## When audit mode applies - procedure deltas

Audit mode is brownfield with the write assumption inverted. Trigger: the user says (or the
intake reveals) that agents must not change product source - fixes are applied by the user or by
a separate delivery team. Relative to the numbered SKILL.md procedure:

| Step | Delta in audit mode |
|------|---------------------|
| 0. Analysis | Run per repo (each repo gets its own Inventory Report section: stack, entry points, secret-file naming, risky surfaces). Analysis output parameterizes auditors, not dev agents |
| 1. Intake | Add: which standards apply per repo, scanner strategy (see below), severity scale, who applies fixes |
| NEW: baseline | **Verify the standards baseline** - see the mandatory section below. Must complete BEFORE any scan runs or finding is written |
| 2. Roster + scaffold | Roster from the audit table below; `.claude` + `docs/` live at the WORKSPACE ROOT, never inside a product repo. Add `docs/findings/` beside the standard tree |
| 3. Guardrails | Add the `protect-repos` hook; harden `protect-secrets` (no `.env.example` allowlist); extend the settings.json deny with Edit/Write globs on every repo dir |
| 4. `.env.example` | For the CONTROL PLANE only (scanner image tags, report options). Never scaffold env files inside product repos |
| 5. Orchestration | The task loop is unchanged; tasks are findings-to-fix and scan/triage work, not features |
| 6. Skills | Prefer scanner/report skills; skip codegen skills |
| 7. Verify | Same quality gate, plus: `protect-repos` blocks an in-repo write (exit 2), a scanner runs end-to-end on one repo, and one finding round-trips finding -> task -> re-scan |

## Multi-repo control-plane layout

The workspace root holds the control plane; each product repo stays an independent git repo,
untouched:

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
  ...
```

Consequences of the multi-repo shape: the control plane's own git repo (if any) must ignore the
repo dirs; `guard-main-commit`-style hooks are irrelevant for product repos (agents never commit
there) but still apply to the control plane; every path an agent cites must be prefixed with the
repo dir so findings are unambiguous; and repo boundaries define auditor scopes 1:1.

## Verify the standards baseline (MANDATORY, before any finding)

Findings anchor to requirement IDs of published standards (e.g. OWASP ASVS, OWASP AISVS,
MASVS/MASTG, CIS benchmarks). Requirement IDs are VERSION-SCOPED - an ID can be renumbered,
merged, or removed across major versions - so a bare ID is meaningless and a stale version baked
into a rule file silently mis-cites requirements for the life of the project. Before writing the
repo -> standard mapping or any finding:

- WebSearch EACH applicable standard for its current version and release date. Do not copy
  version numbers from memory or from this skill - anything written down ages.
- Record the result in the standards table in `reference/security-review.md`-derived project
  rules with a `verified: YYYY-MM-DD` stamp, so staleness is visible at a glance. Re-verify on
  every re-bootstrap.
- Every citation is `standard + version + ID` (e.g. `ASVS <version> V<chapter>.<n>.<n>`), never a
  bare ID. The finding-file frontmatter carries `standard`, `standard_version`, and
  `requirement_id` as separate fields (template in `templates/audit-pack.md`).
- If a version cannot be confirmed from an authoritative source, mark the table row `unverified`
  rather than asserting it - `/triage-findings` refuses findings whose standard version is not
  confirmed.
- Scanner rulesets drift too (Semgrep registry packs, Trivy/Checkov policy bundles): pin image
  tags, record image digests in `docs/context/tool-changelog.md`, and re-pull deliberately as a
  recorded decision - never silently.

## Separation of duties - three enforcement layers

OWASP AISVS Appendix C (verify the current version per the baseline step) states the principle:
the agent that analyses code must not be the agent that merges or modifies it. In audit mode this
is absolute - NO agent modifies product source; writes are confined to `docs/` and `.claude/`.
Stating it in a rule is not enforcement. Three layers, each catching what the previous misses:

| Layer | Mechanism | Catches |
|-------|-----------|---------|
| 1. settings.json deny | `Edit({{REPO_N}}/**)` + `Write({{REPO_N}}/**)` per repo (fragment in `templates/audit-pack.md`) | The straightforward attempt, before any hook runs |
| 2. `protect-repos` hook | PreToolUse Edit\|Write: RESOLVES the target path (relative -> absolute against cwd, `..` collapsed) and blocks anything inside a repo dir | Path shapes the deny globs miss - relative paths, traversal, alternate separators |
| 3. Rule file | `agent-guardrails.md` audit clause: read-only on product source, findings instead of fixes | Tools without layers 1-2 (non-Claude runners via AGENTS.md) and keeps the model reasoning inside the constraint |

Layer 1 without 2 is glob-brittle; layer 2 without 3 produces agents that fight the hook instead
of registering findings. Deploy all three.

**Test every hook's ALLOW cases, not just its BLOCK cases.** A hook that blocks everything passes
every block-case test and looks identical to a working hook - until it silently stops the agent
from writing its own findings. The reverse (a hook that exits 0 on every input) is the
better-known failure and also looks identical to a working hook. Both are only caught by
asserting exit codes on BOTH sides. For `protect-repos` that means: an in-repo write payload
must exit 2 AND a write to `docs/findings/<lowercased-repo-name>/x.md` must exit 0. The second
payload is not arbitrary: PowerShell's `-match`/`-like`/`-eq` are case-INSENSITIVE by default,
so a naive check for repo `Backend` also matches `docs/findings/backend/...` - and findings dirs
are conventionally the lowercased repo names, so this collision is the default outcome of the
very layout recommended above. The pack's hook therefore compares path SEGMENTS case-sensitively
(`-ceq`; only the first segment under the workspace root can name a repo). Bash is case-sensitive
only BY DEFAULT - `shopt -s nocasematch` or `grep -i` reintroduces the same trap - so the bash
flavor states this explicitly rather than relying on it silently. Do not simplify either script
back to a substring match.

## Two-layer model - knowledge + deterministic

An audit ruleset splits into two layers, and the bootstrap must wire BOTH, because neither alone
suffices:

- **Knowledge layer** - rules and checklists the agents load (`.claude/rules/`, the standards
  mapping, `reference/code-quality-review.md`, `reference/performance-review.md`). This is what
  lets an agent judge design-level issues no scanner sees (authz logic, trust boundaries, N+1
  patterns). But rules alone get forgotten - context compaction, long sessions, and model drift
  erode purely-instructional constraints.
- **Deterministic layer** - scanners the agents invoke (SAST, secret scanning, dependency/CVE,
  IaC policy - e.g. Semgrep, Gitleaks, Trivy, Checkov, OSV-Scanner; owned by the `sast-runner`
  agent). Deterministic output does not fade and is reproducible run-to-run. But scanners alone
  cannot prevent bad reasoning at generation time and miss everything that needs semantics.

Rule of thumb: the knowledge layer decides WHAT matters and interprets; the deterministic layer
proves WHERE and survives compaction. A finding confirmed by both is high-confidence; a
knowledge-only finding needs manual evidence; a scanner-only finding needs triage before it
becomes a task.

## Scanner strategy - host vs Docker vs config-only

Decide at intake and record in `tech-stack.md`:

| Strategy | How | Pros | Cons | Use when |
|----------|-----|------|------|----------|
| Host install | `pip/brew/choco install` each scanner | Fastest startup, native paths | Pollutes the host, version skew between machines, install needs privileges | Single dedicated audit machine the user controls |
| **Docker (DEFAULT for audit)** | One pinned image per scanner, source bind-mounted read-only | Installs NOTHING on the host; version pinned by tag+digest; the read-only mount is itself a guardrail | Requires Docker; slower cold start; path mapping in reports needs normalizing | Almost always - matches the audit posture (touch nothing) |
| Config-only | Generate scanner configs + CI snippets; user runs them | Zero local execution | No agent-verifiable results; re-scan verification impossible | User forbids local execution entirely |

The exact Docker shape - note `:ro`, which makes even a compromised or misbehaving scanner unable
to write into the repo (a fourth, incidental enforcement layer):

```
docker run --rm -v "${PWD}:/src:ro" {{SCANNER_IMAGE}}:{{PINNED_TAG}} <scanner args against /src>
```

Run from the repo dir being scanned (or mount `{{WORKSPACE_ROOT}}/{{REPO_N}}`); write output OUT
via stdout redirection or a second writable mount pointed at `docs/findings/raw/` - never a
writable mount of the source. Pin `{{PINNED_TAG}}` per the baseline step; record digests in
`docs/context/tool-changelog.md`.

## The secrets paradox - .env.example is not safe here

The STOCK `protect-secrets` hook (templates/hooks-pack.md) allowlists `.env.example` - correct
for a repo the team itself maintains, where that file is placeholders by construction. An audit
inspects OTHER people's repos, and in real repos `.env.example` frequently contains real
credentials (copied from a working `.env` "to be helpful"). Whether it does is precisely what the
audit must determine - so the hook must not presume the answer:

- In audit mode, generate `protect-secrets` WITHOUT the `.env.example` allowlist: every `.env*`
  file is treated as secret until proven otherwise. Secret-scanner (e.g. Gitleaks) output is the
  evidence path - the deterministic layer reads the file inside its container; the agent never
  needs the contents, only file:line + pattern type.
- Naming conventions escape stock globs: Flutter projects commonly use `.env_dev`,
  `.env_staging`, `.env_prod` - underscore, not dot, so a `.env.*` glob never matches. Derive the
  ACTUAL secret-file names per repo from step-0 analysis and extend both the deny globs and the
  hook pattern (use `\.env[._]` shapes, plus whatever else analysis found: `*.jks`, `*.mobileprovision`,
  `*.tfvars`, cloud credential files).
- The control plane's own `.env.example` (scanner config) keeps the normal rules - it is
  generated, not inherited.

## Audit roster - filled and intentionally unfilled seats

The team-roster presets assume someone writes code; the audit formation replaces dev agents with
read-only auditors. Tools for every auditor/reviewer: `Read, Grep, Glob, Bash` (Bash for git
history and scanner invocation only); Edit/Write only for agents that maintain `docs/` files.
Bodies in `templates/audit-pack.md`.

| Agent | Role |
|-------|------|
| `orchestrator` | Routes scan/triage/review missions; owns the task loop; never analyses code itself |
| `<repo>-auditor` (one per repo) | Deep manual review of its repo: architecture, authz, data flows, stack-specific risk. Scope = the repo dir, read-only. Writes findings under `docs/findings/<repo>/` |
| `sast-runner` | Owns the deterministic layer: runs the pinned scanner containers, normalizes output into `docs/findings/raw/`, dedupes against existing findings |
| `security-reviewer` | Cross-repo security judgment: triage severity, confirm/reject scanner findings, map to requirement IDs |
| `perf-reviewer` | Performance findings (see `reference/performance-review.md`) |
| `code-reviewer` | Maintainability/quality findings (see `reference/code-quality-review.md`) |
| `spec-guardian` | RE-PURPOSED: instead of guarding FRs, anchors every finding to a verified `standard + version + requirement_id`, and rejects findings with bare or unverified IDs |
| `debugger` | Reproduces suspected issues read-only (build a PoC in scratch space, never in the repo) |
| `history-tracker` | Curates the agent-run archive - in an audit, the audit trail is part of the deliverable |

**Intentionally unfilled seats** - the roster-completeness check in `reference/team-roster.md`
demands every empty seat be NAMED in CLAUDE.md with who covers it:

| Unfilled seat | Covered by |
|---------------|-----------|
| Implementer (`<domain>-dev`) | THE USER applies all fixes in the product repos |
| `devops` / deploy | The user (or the product teams); agents never touch CI or infra state |
| `qa-test` | The user's test suites verify fixes; agents only re-scan (verification, not testing) |
| DB trio (`data-modeler`, `db-engineer`, `db-seeder`) | Nobody - no schema or data work exists in a read-only audit; schema RISKS are findings owned by the repo's auditor |

## Finding lifecycle

Findings are never fixed in place by an agent - the lifecycle routes them to the user and back:

```
finding (scanner or manual) -> severity (security-reviewer) -> requirement ID (spec-guardian)
  -> task registration (/new-task + master-plan row, status Registered)
  -> USER fixes in the product repo
  -> re-scan / re-review verifies (status Fixed -> Verified; finding's `verified:` date set)
```

One finding file per finding (`docs/findings/<repo>/FND-NNN-<slug>.md`, template in
`templates/audit-pack.md`); its `status` and the linked TASK's status move together. False
positives are RECORDED (`status: False-positive` + reasoning), never deleted - the next scan run
would just resurrect them. `/security-scan` runs the scanners and registers new findings;
`/triage-findings` walks unreviewed ones through severity + requirement anchoring + task
registration.

**Convergence -> census.** When two independently-dispatched agents converge on the same defect
CLASS (each finds a different instance of, say, the same missing-guard pattern), the orchestrator
does not merely register the two instances: it dispatches one focused enumeration pass (a
"census") for that pattern across every repo in scope, so the class closes with a known blast
radius instead of "at least two". Independent convergence is the strongest cheap signal that a
defect is systemic rather than local - spend one census on it, and record the census itself as a
task so its coverage is auditable.

## Reporting rules

- Every finding cites `path/from/workspace/root:line` evidence - a finding an auditor cannot
  point to is an opinion, and the repo prefix is mandatory in multi-repo workspaces.
- NEVER reproduce a secret value in a finding, task, log, or report - findings are committed
  files. Cite file:line + pattern TYPE (`AWS access key shape`, `JWT`), exactly like
  `/secret-scan`. A leaked secret in a finding file is itself a Critical finding.
- No real PII in evidence excerpts; describe, do not quote.
- Severity, standard, version, and requirement ID live in frontmatter (machine-greppable);
  prose explains impact and recommendation - the user fixing it is the audience.
