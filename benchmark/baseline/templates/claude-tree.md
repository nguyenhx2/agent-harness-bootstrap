# .claude/ directory tree scaffold (project-bootstrap)

Full target structure for the standardized AI-agent operating folder. Relative forward-slash paths
only. Items marked (opt) are generated only when the intake accepts them; dev agents come from the
codebase-analysis module mapping (one per feature domain).

```
.claude/
  settings.json                    # permission allow/deny + hook registration -> settings.json.template
  rules/                           # behavioral law; 00-overview.md first; one concern per file -> rules-pack.md
    00-overview.md                 # system, invariant principles, precedence, rule list
    tech-stack.md
    coding-standards.md
    testing.md
    git-workflow.md
    conventional-commits.md
    agent-guardrails.md            # NEVER skip
    security-privacy.md
    docs-workflow.md
    task-tracking.md
    data-model.md                  # (opt: DB)
    frontend.md  design-system.md  # (opt: UI)
    human-in-the-loop.md           # (opt: AI product)
    <hosting>.md                   # (opt: one per infra target, e.g. railway.md)
    <language>.md                  # (opt: e.g. vietnamese-diacritics.md)
  agents/                          # -> agents-pack.md
    orchestrator.md                # mission controller - always
    <domain>-dev.md                # one per feature domain from the module mapping
    frontend-ui-dev.md             # (opt: UI)
    code-reviewer.md  security-reviewer.md  spec-guardian.md   # read-only reviewers - always
    qa-test.md                     # (opt)
    data-modeler.md  db-engineer.md  db-seeder.md              # (opt: DB trio)
    ba-analyst.md  devops.md  debugger.md  history-tracker.md
    brainstormer.md  tech-researcher.md                        # (opt: planning pair)
  commands/                        # -> commands-pack.md; MR/PR naming per platform
    implement-fr.md  review-mr.md|review-pr.md  secret-scan.md
    new-task.md  task-resume.md
    brainstorm.md  new-adr.md  new-spec-section.md  sync-context.md
    test.md                        # (opt)
    db-migration.md  seed-db.md    # (opt: DB)
    deploy-<hosting>.md            # (opt: hosting; GATED)
    scaffold-feature.md            # (opt)
  hooks/                           # -> hooks-pack.md; ps1 (Windows) or sh (POSIX)
    README.md                      # table: hook / event / purpose + conventions
    protect-adr.*  guard-main-commit.*  check-commit-msg.*
    protect-secrets.*  specs-reminder.*  agent-history.*
  skills/                          # project-installed skills (db-seed, tdd, ...)
  state/
    history/                       # agent-run archive (agent-history hook); gitignored
```

Also add to `.gitignore`: `.claude/state/` and `.claude/worktrees/`.
