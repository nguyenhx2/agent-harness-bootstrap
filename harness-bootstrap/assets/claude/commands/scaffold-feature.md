---
description: Create the skeleton of a feature module (entry point, library module, component).
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
{{#IF_TDD}}4. A failing {{UNIT_FRAMEWORK}} test that names the acceptance criterion of the FR it serves. It
   fails first; the implementation is what makes it pass.
{{/IF_TDD}}
Register the owner agent for the domain in the routing table if this feature is not covered by an
existing entry:

{{ROUTING_TABLE}}

{{^IF_TDD}}Write no tests here: a test against a module with no behavior is a test written to be rewritten,
and the design pass in `/implement-fr` has not run yet.

{{/IF_TDD}}Scaffolding creates structure, not behavior. Leave the logic unimplemented rather than filling it
with a plausible guess.
