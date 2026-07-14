# Code-quality review - knowledge base (project-bootstrap)

Loaded by the `code-reviewer` agent (and the orchestrator in audit mode - see
[audit-mode.md](audit-mode.md)). Defines what a quality finding IS, the severity model shared with
[performance-review.md](performance-review.md) and [security-review.md](security-review.md), and
the smells that actually predict defects. Everything here is language-agnostic; ground each finding
in THIS repo's files, never in generic advice.

## Table of contents

- [What is a finding](#what-is-a-finding)
- [Severity model (shared by all three review docs)](#severity-model-shared-by-all-three-review-docs)
- [Defect-predicting smells](#defect-predicting-smells)
- [Type-safety review](#type-safety-review)
- [Test-coverage review](#test-coverage-review)
- [Output contract](#output-contract)

## What is a finding

A finding **changes what a reader would do**: fix code, add a test, rotate a secret, register a
backlog task, reject a merge. If knowing it changes nothing, it is not a finding.

| Is a finding | Is NOT a finding |
|--------------|------------------|
| `catch {}` around a payment call - failures vanish | Brace style, quote style, import order |
| The same discount formula copy-pasted in two modules | "This could be more functional" |
| A validator that returns `true` unconditionally | Preference for a different library, absent a defect |
| Public API taking 4 positional booleans | Anything a formatter or linter autofix settles |
| No test touches the money-moving path | "Coverage is only 62%" with no risk attached |

Style that a formatter/linter settles is tooling configuration, not review output. If the repo has
no formatter, ONE Info finding ("no formatter configured") replaces every individual style nit.

## Severity model (shared by all three review docs)

Severity is defined by **consequence**, never by how bad the code looks. The performance and
security docs use these same four levels.

| Severity | Definition (consequence-based) | Merge/release effect |
|----------|--------------------------------|----------------------|
| **Blocker** | Wrong results, data loss, or a security breach in NORMAL operation - no unusual input needed. Dead security control, secret in the repo, corrupting write. | Must fix before merge/release. |
| **Major** | Defect fires under realistic conditions (edge input, provider outage, concurrency, growth) OR the code cannot be changed safely (zero tests on a critical path, god-service everyone edits). | Fix in this cycle; needs an owner and a task. |
| **Minor** | Raises the cost or risk of future change (duplication, boolean traps, scattered config) but does not misbehave today. | Register as backlog task; fix opportunistically. |
| **Info** | Observation worth recording: a trade-off, a missing convention, a "this will not scale past X" note. | No action required; keep for context. |

Tie-break: ask "what is the worst thing that happens if nobody acts?" and grade THAT. When two
levels seem plausible, take the lower one and state the condition that would upgrade it.

## Defect-predicting smells

Each smell: how to detect it cheaply (grep/glob/AST - no execution needed) and why it predicts
defects. Thresholds are triage cutoffs, not laws - a 900-line parser table is fine; a 900-line
"service" with 30 imports is not.

| Smell | Cheap detection | Why it predicts defects | Typical severity |
|-------|-----------------|-------------------------|------------------|
| God-file / god-service | File > ~500 LOC AND > ~15 imports/fan-out; or one class named `*Service`/`*Manager`/`*Utils` that half the modules import | Every change collides here; unrelated features share state and failure modes; nobody can test it in isolation | Major when it owns critical logic, else Minor |
| Duplicated logic across module boundaries | Grep a distinctive constant/formula/regex; > 1 hit in DIFFERENT modules = duplication (same-module repetition is cheaper) | The copies WILL diverge; the bug gets fixed in one place and shipped in the other | Major if business rules (pricing, auth, validation), else Minor |
| Swallowed errors | `catch` blocks that are empty, log-only, or `return null` with no rethrow/propagation: grep `catch` and read the bodies; `except: pass`; `_ = err`; `.catch(() => ...)` | Converts loud failures into silent wrong state; the defect surfaces far from its cause | Blocker on money/auth/data paths, Major elsewhere |
| Boolean trap parameters | Signatures with >= 2 boolean params, or call sites reading `doThing(true, false, true)` | Call sites are unreviewable; transposed flags pass type-check and tests that mirror the mistake | Minor (Major on public/API surface) |
| Primitive obsession at API boundaries | Public functions/endpoints passing money as `number`, IDs as bare `string`, dates as strings, status as free-text | The type system cannot catch unit/currency/ID-kind mixups exactly where callers are external | Minor; Major when money or IDs actually get mixed |
| **Dead security control** | A function named `validate*`/`verify*`/`sanitize*`/`check*`/`encrypt*` whose body always returns success, returns its input unchanged, or is commented out; callers still call it | The MOST dangerous smell: the codebase LOOKS defended, reviewers and tests are reassured, and the control does nothing. Always cross-file this to [security-review.md](security-review.md) | **Blocker**, always |
| Scattered config reads | `process.env.` / `os.environ` / `getenv` hits in > ~3 files instead of one config module | No single place validates presence/format; missing var fails at first use deep in a request, not at boot; env list drifts from `.env.example` | Minor; Major when it hides required-var validation |

Detection discipline: grep gives CANDIDATES; read the code before reporting. A finding you did not
verify by reading the file is a guess, and guesses destroy the audit's credibility.

## Type-safety review

Dynamic or loosened typing is not a defect by itself - report what it COSTS in this codebase:

- **TypeScript**: check `tsconfig.json` for `strict: false`, `noImplicitAny: false`,
  `strictNullChecks: false`; grep `: any`, `as any`, `@ts-ignore`, `@ts-expect-error` and COUNT
  them. Python: `mypy`/`pyright` config absent or `ignore_missing_imports` blanket-on; grep
  `# type: ignore`.
- What it actually costs: null/undefined bugs pass compile and surface at runtime; refactors lose
  the compiler as a safety net (renames miss call sites); `any` at a boundary silently infects
  every downstream consumer.
- Phrase the finding as a measured statement plus consequence, not doctrine:
  "`strict` is off and there are 143 `any`s (`git grep -c ': any'`); null-safety bugs like
  `src/orders/total.ts:88` reading `.price` of a possibly-undefined item are invisible to the
  compiler." Severity: Major when the audit found actual bugs strict mode would have caught,
  else Minor with the enablement path (per-directory or `strict` + suppressions burn-down) as the
  suggested direction, registered as a migration task per
  [codebase-analysis.md](codebase-analysis.md).

## Test-coverage review

**No tests exist** -> one Major finding, stated as risk, not morality:
"No test files found (`glob **/*.{test,spec}.*` = 0). Every change to <named critical paths> is
verified only by manual testing; regressions ship silently." Name the 2-3 paths where a regression
costs most (payment, auth, data mutation) as where tests should START. Do not lecture about TDD.

**Tests exist** -> assess whether they would catch a regression:

| Check | How | Finding if it fails |
|-------|-----|---------------------|
| External providers mocked | Grep test files for real SDK/network imports without a mock layer | Tests hit live services: flaky, slow, may mutate real data, fail offline (Major) |
| Behavior vs implementation | Do asserts check outputs/state, or mock-call counts and private internals? | Implementation-coupled tests break on every refactor and pass on real bugs (Minor) |
| Critical paths covered | Map test files to the money/auth/data modules from the analysis | "Tests exist but none touch <module>" (Major for critical modules) |
| Tests actually run | Is the test script wired into CI / the repo's task flow? | A suite nobody runs is documentation, not protection (Minor) |
| Assertions exist | Spot-read: tests that only check "does not throw" | Smoke-only suite gives false confidence (Minor/Info) |

Coverage PERCENTAGE alone is Info at best; coverage of a path that moves money or grants access is
what earns Major.

## Output contract

Every finding, regardless of severity, ships in this shape - a reviewer report is a list of these,
grouped by severity (Blockers first):

1. **Location**: `path/to/file.ts:123` (real file:line you read, not a guess).
2. **Defect statement**: ONE sentence, present tense, about behavior - "X does Y when Z".
3. **Failure scenario**: concrete inputs -> wrong output/state. "A refund of 0.1 + 0.2 stores
   0.30000000000000004 and the reconciliation job flags it" beats "floating point issues".
4. **Severity** from the shared model, with the consequence that justifies it.
5. **Suggested direction**: one line pointing the fix ("extract the formula into
   `pricing/discount.ts` and import from both callers") - **NOT a patch**. The reviewer's diff is
   likely wrong about context it cannot see, invites rubber-stamping, and blurs the line between
   reviewing and authoring; the owning dev agent implements per the flow in
   [team-roster.md](team-roster.md).

No finding without a location. No severity without a consequence. No patch, ever.
