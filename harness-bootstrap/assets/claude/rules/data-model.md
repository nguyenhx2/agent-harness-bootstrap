---
# {{DB_GLOBS}} expands to one quoted glob per line, e.g. "prisma/**", "migrations/**", "src/models/**"
paths:
  - "{{DB_GLOBS}}"
---

# Data model

Applies to schema, migrations, and model definitions. ORM: {{ORM}}.

## The schema follows the documented model

`docs/specs/08-data-model.md` holds the ERD and the data dictionary; the schema implements it. A
schema change that the dictionary does not describe is a schema change nobody agreed to. If the
model needs to change, change the document in the same pull request.

## Conventions

- Naming is consistent across every entity, and follows {{ORM}}'s idiom rather than a per-table
  preference. Pick it once; do not relitigate per model.
- Enumerated values are declared enums, not free-text strings with a comment. A status column that
  accepts any string will eventually hold every string.
- Every foreign key has an explicit referential action; the default is rarely what was intended.
- Index against the actual query shape - the real WHERE, ORDER BY, and JOIN columns - not against
  every column and not against a guess (performance.md).
- Money is never a float. Dates are stored with an explicit timezone or as UTC, decided once.
- Nullability is a decision, not an oversight: a nullable column is a state the code must handle.

## Migrations

- Every schema change ships as a migration. Never hand-edit a database to match the code, and never
  edit a migration that has already run anywhere but a throwaway local database.
- Forward-only. A mistake is fixed by a new migration, not by rewriting history.
- One pull request carries all three: the migration, the data-dictionary update, and the seed
  update. A migration that lands without its seed leaves every teammate with a broken local
  database.
- Destructive migrations (dropping a column or table, narrowing a type, deleting rows) are gated:
  they need an explicit request, a backup, and an expand-then-contract plan - add the new shape,
  migrate the data, cut over, and only then remove the old shape in a later change.
- A database reset is never run against anything but a local or ephemeral test database, and never
  without being asked (agent-guardrails.md).

## Seeds

- Seed data is synthetic, deterministic, and idempotent: running the seed twice leaves the same
  state, and it never depends on random values that make a failure unreproducible.
- Seeds target local and development databases only. There is no seed path that can reach
  production.
- No real personal data in a seed, ever. Not a scrubbed export, not a "just the names" subset.
