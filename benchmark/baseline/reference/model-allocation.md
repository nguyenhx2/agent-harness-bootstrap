# Model allocation (project-bootstrap)

Every generated agent's frontmatter MUST carry an explicit `model:` key. An unset `model:` means
the agent silently inherits whatever model the caller (often the orchestrator, often the user's
most expensive default) happens to be running - that is not a choice, it is a default nobody made,
and on a multi-agent roster it is pure waste: mechanical or narrowly-scoped work pays premium-model
prices for no quality gain. Never leave `model:` unset in a generated agent.

## The principle: cheap generation, expensive verification

Generation - writing code or docs against a settled spec - is well within a mid-tier model. The
work that actually needs the strongest model is judgment: deciding what to build, root-causing why
something broke, and catching what a generation pass got wrong. Spend the expensive model on the
judgment seats and the review gates, not on volume.

This is not theoretical: on a real bootstrapped project, the review gates (`code-reviewer` +
`security-reviewer`) caught 22+ defects that the implementation passes had shipped green - several
of them data-losing (a report doubled under retry, a forgeable consent gate, silently-dropped user
input). Downgrading the reviewers to save cost is a false economy - they are the safety net, and
that matters most precisely where CI is thin or off.

## Decision rule

Classify every agent - the ones named below and any project-specific `<domain>-dev` or one-off
agent invented later - against this heuristic, in order:

| Question | If yes | Model |
|----------|--------|-------|
| Does it make consequential judgment calls (planning, decomposition, root-cause diagnosis) or exist specifically to catch OTHER agents' mistakes (a review/merge gate)? | Yes | `opus` |
| Does it produce code, docs, or structured output against an already-settled spec/rules/schema? | Yes | `sonnet` |
| Is the task mechanical and low-judgment - formatting, summarizing, running a fixed pipeline, archiving? | Yes | `haiku` |

Apply the rows in order and stop at the first match - a reviewer is never downgraded to `sonnet`
just because its output also happens to be "structured".

## Standard roster allocation

| Tier | Agents | Model | Why |
|------|--------|-------|-----|
| Judgment / gates | `orchestrator` | `opus` | Plans, decomposes, and judges other agents' results - the highest-leverage seat on the roster |
| Judgment / gates | `debugger` | `opus` | Root-cause reasoning under incomplete information is the hardest single-agent task in the roster |
| Judgment / gates | `code-reviewer`, `security-reviewer` | `opus` | The safety net - catches defects the implementation pass shipped green, several of them severe. This is the seat least safe to discount |
| Judgment / gates | `merge-manager` (if fielded) | `opus` | A gate, not an author: the strict merge checklist plus conflict-drop detection is judgment, not formatting |
| Judgment / gates | `{{REPO_SLUG}}-auditor`, `perf-reviewer` (audit mode) | `opus` | Same role as the reviewer trio - manual analysis that must catch what the deterministic scanners miss |
| Implementation | Every `<domain>-dev` / `app-dev` / `frontend-ui-dev` / `data-modeler` / `db-engineer` | `sonnet` | Implementation against a settled spec and clear rules is well within Sonnet |
| Implementation | `qa-test`, `spec-guardian`, `ba-analyst`, `brainstormer`, `tech-researcher`, `devops` | `sonnet` | Structured output (tests, requirement checks, specs, options, pipelines) against clear inputs |
| Mechanical | `history-tracker` | `haiku` | Summarizes an append-only archive - low judgment, high volume |
| Mechanical | `db-seeder` | `haiku` | Runs a fixed, deterministic generation script against a schema - no open judgment |
| Mechanical | `sast-runner` (audit mode) | `haiku` | Runs a pinned scanner suite and normalizes output; it explicitly never judges severity |

Any agent not in this table - a new `<domain>-dev`, a project-specific one-off - is classified with
the Decision rule above, not left unset and not guessed by analogy to the "closest-sounding" name.

## Applying it

- Every frontmatter block emitted from `templates/agents-pack.md` and `templates/audit-pack.md`
  carries `model: opus|sonnet|haiku` on its own line inside the `---` fences, alongside `name`,
  `description`, and `tools`.
- Record the roster's model allocation in the setup-plan echo (step 1) and re-state it in the
  Quality gate section 7 check, so a reviewer of the bootstrap output can see the allocation was a
  decision, not an omission.
- If the project later adds an agent outside this table, apply the Decision rule and add a row to
  the project's own `docs/context/tool-changelog.md` explaining the pick - do not leave it unset.
