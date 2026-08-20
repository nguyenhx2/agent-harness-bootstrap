---
description: Seed the local or development database with deterministic synthetic data per the ERD.
---

Dispatch `db-seeder` with the db-seed skill.

- Local and development databases only. Check the connection target first and refuse if it points
  at a shared, staging, or production database.
- Synthetic data only: never real customer records, never real personal data, never a production
  dump. Seeded data is committed and read by everyone.
- Deterministic: fixed seed values, so two runs produce the same rows and a failing test is
  reproducible.
- Idempotent: upserts, never blind inserts. Re-running the seed must not duplicate rows.
- Consistent with the ERD in `docs/specs/`: every required relation is populated, so a foreign key
  is never dangling.

Verify row counts per table after the run and report them. A seed script that "succeeded" while
writing nothing is the failure mode to catch.
