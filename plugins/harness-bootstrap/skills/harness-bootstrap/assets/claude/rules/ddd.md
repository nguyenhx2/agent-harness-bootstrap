---
paths:
  - {{SOURCE_GLOBS}}
---

# Domain-driven design

This project develops under DDD. The harness wires the discipline to things agents can check, so it
survives model changes and compactions the way the rest of the harness does.

## Ubiquitous language is law

`docs/context/glossary.md` (seeded from spec section 03) is the single vocabulary. Code, tests,
task files, and commit messages use the glossary's exact terms - no synonyms, no translations, no
"Client" where the glossary says "Customer". A concept the glossary does not name is added THERE
first, in the same change that introduces it; inventing a term inline is how two modules end up
modeling the same thing twice.

## Bounded contexts are the agent scopes

Each dev agent's module scope IS a bounded context. The mapping is deliberate: the same word may
mean different things in different contexts, and that is fine - but only inside the boundary.

- Cross-context access goes through the context's published interface. Never import another
  context's internals; that is the same violation as editing outside your scope.
- Where a context consumes another's model, translate at the boundary (an anti-corruption layer,
  however small) instead of letting a foreign model leak in.

## Aggregates and invariants

- State changes go through the aggregate root. A write that bypasses the root to touch a child
  entity is a defect even when it works.
- Invariants the spec states (BR-nn business rules) live inside the aggregate that owns them, not
  in callers. `spec-guardian` checks the diff against those rules by name.
- Domain events are named in the glossary's past tense (`OrderPlaced`, not `PlaceOrder`) and carry
  the aggregate's identity.

## How this plugs into the loop

Spec section 03 seeds the glossary; section 08's entities mark the aggregate candidates; the
module→agent mapping fixes the context boundaries. When a boundary turns out wrong, that is an ADR
plus a re-scope through `/harness-update` - never a quiet cross-context import.
