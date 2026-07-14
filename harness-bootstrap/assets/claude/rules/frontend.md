---
# {{UI_GLOBS}} expands to one quoted glob per line, e.g. "src/components/**", "src/app/**"
paths:
  - "{{UI_GLOBS}}"
---

# Frontend

Applies to UI code.

## Build from primitives and tokens

- UI is assembled from the project's shared primitives and design tokens. A screen that reaches
  past them to raw elements and hardcoded values is how a design system dies: it fragments
  silently, one "just this once" at a time.
- Hardcoded colors, spacing, radii, font sizes, and z-indices are not accepted. If a token is
  missing, add the token - that is a five-minute change and it is the right one.
- Raw native selects, raw data tables, and status text styled inline are replaced by the
  corresponding primitive. A data table is sortable, filterable, and paginated by design, not by
  each caller reinventing it.
- Adding a new primitive is a deliberate act: create it, export it from the shared entry point,
  test it, and document it, in one change.

## Structure

- Components render. Business logic, data fetching orchestration, and formatting rules live outside
  them, in modules that can be tested without a DOM.
- State is local until it demonstrably cannot be. A global store is the exception, and each entry
  in it has a reason.
- Lists that can grow without bound are virtualized, and images carry explicit dimensions
  (performance.md).

## Icons and assets

- No emoji as iconography, anywhere in the UI. Icons come from the project's icon set as SVG.
- Brand assets are self-hosted, use the correct variant for the background they sit on, keep their
  aspect ratio and clear space, and carry meaningful alternative text.

## Accessibility

- Every interactive element is reachable and operable by keyboard, with a visible focus state.
- Every control has an accessible name; every image has alternative text (empty if decorative).
- Color is never the sole carrier of meaning, and contrast meets the project's stated target.
- Semantic elements before ARIA. ARIA that contradicts the element underneath is worse than none.

## Rendering untrusted or generated content

Content the user supplied, and content a model generated, is untrusted (agent-guardrails.md). It is
rendered through a sanitizing renderer - never injected as raw HTML - and any link or action it
contains is validated against an allowlist before it becomes clickable.
