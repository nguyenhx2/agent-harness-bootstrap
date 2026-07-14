---
description: Create the skeleton of a feature module (entry point, library module, component, failing test).
argument-hint: <feature-slug>
---

Scaffold the feature **$1**. If $1 is empty, ask for the feature slug and stop.

Follow the layout in `.claude/rules/coding-standards.md`:

1. The entry point (route handler, controller, or command): input validation and delegation only.
   No business logic lives here.
2. The library module that holds the business logic, one directory per feature, testable without
   the transport layer.
3. The user-facing component, built from the existing design-system primitives rather than new
   one-off styles, when the feature has a user interface.
4. A failing {{UNIT_FRAMEWORK}} test that names the acceptance criterion of the FR it serves. It
   fails first; the implementation is what makes it pass.

Register the owner agent for the domain in the routing table if this feature is not covered by an
existing entry:

{{ROUTING_TABLE}}

Scaffolding creates structure, not behavior. Leave the logic unimplemented rather than filling it
with a plausible guess.
