# Business rules - {{PROJECT_NAME}}

The behavioral rules this system enforces, each with the source that authorized it. A rule that
lives only in code is a rule the next agent will break without knowing it existed.

Numbered BR-NN, stable forever: a rule that is superseded is marked, never renumbered and never
deleted. Downstream files (tasks, findings, tests) cite these IDs.

Updated via `/sync-context` whenever behavior-affecting logic changes.

| ID | Rule | Source | Status | Enforced in |
|----|------|--------|--------|-------------|
| BR-01 | <the rule, stated as a testable invariant> | <FR-NN or ADR-NNN> | Active | <module or test that enforces it> |

<!-- "Status" is Active or Superseded (by BR-NN). Rules are appended, never edited in place: the
     history of what was true when is what makes an old defect explicable. -->

<!-- A rule with no "enforced in" is aspirational. Either point at the code that enforces it, or
     open a task to write that code. -->
