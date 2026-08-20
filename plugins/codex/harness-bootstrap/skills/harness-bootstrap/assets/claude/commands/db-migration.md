---
description: Generate a database migration from schema changes, following the ERD and the data dictionary.
argument-hint: <migration-name>
---

Generate the migration **$1**. If $1 is empty, ask for a migration name and stop.

1. Diff the schema against the data model in `docs/specs/`. If the design is new, update the ERD
   and the data dictionary in the same {{PR_OR_MR}} as the migration.
2. Generate the migration with the project's migration tool, against the LOCAL development database
   only. Never run a migration, a reset, or a schema push against a shared, staging, or production
   database. That is a gated action and it is not gated by this command.
3. Review the generated SQL before applying it. Escalate to the user, do not apply, when it
   contains: a DROP of a populated column or table, a NOT NULL added to an existing table without a
   default, a destructive type change, or any statement that can lose data. Generated does not mean
   safe.
4. Update the seed script in the same {{PR_OR_MR}} so it still matches the schema.
5. Record the migration in `docs/context/tool-changelog.md`: what changed, why, and how it was
   verified.
