---
# {{SOURCE_GLOBS}} expands to one quoted glob per line, e.g. "src/**/*.{ts,tsx}"
paths:
  - "{{SOURCE_GLOBS}}"
---

# Code quality

Defines what a finding IS and the severity model that security-privacy.md and performance.md both
use. Language-agnostic: ground every finding in a file of this repo, never in generic advice.

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

Style that a formatter or linter settles is tooling configuration, not review output. If the repo
has no formatter, ONE Info finding ("no formatter configured") replaces every individual style nit.

## Severity model (shared by all reviews)

Severity is defined by **consequence**, never by how bad the code looks. The security and
performance rules use these same four levels and do not redefine them.

| Severity | Definition (consequence-based) | Merge/release effect |
|----------|--------------------------------|----------------------|
| **Blocker** | Wrong results, data loss, or a security breach in NORMAL operation - no unusual input needed. Dead security control, secret in the repo, corrupting write. | Must fix before merge or release. |
| **Major** | Defect fires under realistic conditions (edge input, provider outage, concurrency, growth) OR the code cannot be changed safely (zero tests on a critical path, god-service everyone edits). | Fix in this cycle; needs an owner and a task. |
| **Minor** | Raises the cost or risk of future change (duplication, boolean traps, scattered config) but does not misbehave today. | Register as a backlog task; fix opportunistically. |
| **Info** | Observation worth recording: a trade-off, a missing convention, a "this will not scale past X" note. | No action required; keep for context. |

Tie-break: ask "what is the worst thing that happens if nobody acts?" and grade THAT. When two
levels seem plausible, take the lower one and state the condition that would upgrade it.

## Defect-predicting smells

Detect cheaply (grep, glob, AST - no execution needed). Thresholds are triage cutoffs, not laws: a
900-line parser table is fine; a 900-line "service" with 30 imports is not.

| Smell | Cheap detection | Why it predicts defects | Typical severity |
|-------|-----------------|-------------------------|------------------|
| God-file / god-service | File > ~500 LOC AND > ~15 imports/fan-out; or one class named `*Service`/`*Manager`/`*Utils` that half the modules import | Every change collides here; unrelated features share state and failure modes; nobody can test it in isolation | Major when it owns critical logic, else Minor |
| Duplicated logic across module boundaries | Grep a distinctive constant, formula, or regex; more than 1 hit in DIFFERENT modules is duplication (same-module repetition is cheaper) | The copies WILL diverge; the bug gets fixed in one place and shipped in the other | Major if business rules (pricing, auth, validation), else Minor |
| Swallowed errors | `catch` blocks that are empty, log-only, or `return null` with no rethrow or propagation; `except: pass`; `_ = err`; `.catch(() => ...)` | Converts loud failures into silent wrong state; the defect surfaces far from its cause | Blocker on money/auth/data paths, Major elsewhere |
| Boolean trap parameters | Signatures with 2 or more boolean params, or call sites reading `doThing(true, false, true)` | Call sites are unreviewable; transposed flags pass type-check and pass tests that mirror the mistake | Minor (Major on a public or API surface) |
| Primitive obsession at API boundaries | Public functions and endpoints passing money as a number, IDs as bare strings, dates as strings, status as free text | The type system cannot catch unit, currency, or ID-kind mixups exactly where callers are external | Minor; Major when money or IDs actually get mixed |
| **Dead security control** | A function named `validate*`/`verify*`/`sanitize*`/`check*`/`encrypt*` whose body always returns success, returns its input unchanged, or is commented out, while callers still call it | The MOST dangerous smell: the codebase LOOKS defended, reviewers and tests are reassured, and the control does nothing. Always cross-file this to security-privacy.md | **Blocker**, always |
| Scattered config reads | `process.env.` / `os.environ` / `getenv` hits in more than ~3 files instead of one config module | No single place validates presence or format; a missing variable fails at first use deep in a request, not at boot; the variable list drifts from `.env.example` | Minor; Major when it hides required-variable validation |

Detection discipline: grep gives CANDIDATES; read the code before reporting. A finding nobody
verified by reading the file is a guess, and guesses destroy a review's credibility.

## Type safety

Dynamic or loosened typing is not a defect by itself - report what it COSTS in this codebase.

- Check the type-checker config for disabled strictness (`strict: false`, `noImplicitAny: false`,
  `strictNullChecks: false`; or an absent mypy/pyright config, or blanket
  `ignore_missing_imports`). Grep and COUNT the escape hatches: `: any`, `as any`, `@ts-ignore`,
  `@ts-expect-error`, `# type: ignore`.
- What it costs: null and undefined bugs pass compile and surface at runtime; refactors lose the
  compiler as a safety net, so renames miss call sites; one `any` at a boundary silently infects
  every downstream consumer.
- Phrase the finding as a measured statement plus a consequence, not doctrine: "strict is off and
  there are 143 `any`s; null-safety bugs like `<file>:<line>` reading `.price` of a possibly
  undefined item are invisible to the compiler." Severity: Major when the review found actual bugs
  strict mode would have caught, else Minor, with the enablement path (per-directory, or strict
  plus a suppressions burn-down) as the suggested direction, registered as a migration task.

## Reviewing tests

Authoring rules are in testing.md. When reviewing:

**No tests exist** produces one Major finding, stated as risk, not morality: "No test files found.
Every change to <named critical paths> is verified only by manual testing; regressions ship
silently." Name the 2-3 paths where a regression costs most (payment, auth, data mutation) as where
tests should START. Do not lecture about TDD.

**Tests exist** - assess whether they would catch a regression:

| Check | How | Finding if it fails |
|-------|-----|---------------------|
| External providers mocked | Grep test files for real SDK or network imports with no mock layer | Tests hit live services: flaky, slow, may mutate real data, fail offline (Major) |
| Behavior vs implementation | Do asserts check outputs and state, or mock-call counts and private internals? | Implementation-coupled tests break on every refactor and pass on real bugs (Minor) |
| Critical paths covered | Map test files to the money, auth, and data modules | "Tests exist but none touch <module>" (Major for critical modules) |
| Tests actually run | Is the test script wired into CI and the repo's task flow? | A suite nobody runs is documentation, not protection (Minor) |
| Assertions exist | Spot-read for tests that only check "does not throw" | A smoke-only suite gives false confidence (Minor/Info) |

Coverage PERCENTAGE alone is Info at best. Coverage of a path that moves money or grants access is
what earns Major.

## Output contract

Every finding, regardless of severity, ships in this shape. A review report is a list of these,
grouped by severity, Blockers first. Security and performance findings use this same contract, plus
their own extra field.

1. **Location**: `path/to/file.ext:123` - a real file and line that was read, not a guess.
2. **Defect statement**: ONE sentence, present tense, about behavior: "X does Y when Z".
3. **Failure scenario**: concrete inputs leading to a wrong output or state. "A refund of 0.1 + 0.2
   stores 0.30000000000000004 and the reconciliation job flags it" beats "floating point issues".
4. **Severity** from the shared model, with the consequence that justifies it.
5. **Suggested direction**: one line pointing at the fix ("extract the formula into one module and
   import it from both callers") - **NOT a patch**. A reviewer's diff is likely wrong about context
   it cannot see, invites rubber-stamping, and blurs reviewing into authoring. The owning dev agent
   implements it.

No finding without a location. No severity without a consequence. No patch, ever.
