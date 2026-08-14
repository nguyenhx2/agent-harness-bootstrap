---
title: "Design system"
sidebar_label: "14. Design system"
description: "Design tokens, component inventory, and brand assets for {{PROJECT_NAME}} - the visual contract the wireframes in 10 deliberately leave out."
tags: [specs, design, {{PROJECT_SLUG}}]
---

# Design system

<!-- Optional appendix. 13-revision-history.md remains the last mandatory section and still records
     changes made here. This section exists when the project has (or is adopting) a design system;
     wireframes in 10 stay structural, and the visual decisions live here instead - one home each. -->

The visual contract for {{PROJECT_NAME}}: the tokens every screen consumes, the components screens
are assembled from, and where the source of truth lives. Section [10](10-ui-ux-wireframes.md) says
*what* is on a screen; this section says what it looks and behaves like when it gets there.

## Source of truth

| Question | Answer |
|----------|--------|
| Where tokens are defined | <Figma library / `tokens.json` in repo / CSS variables file - one place> |
| Where components are defined | <Figma library / component package / `src/components/ui/` - one place> |
| Who approves a token change | <role or person> |
| How a change reaches code | <sync tool, export step, or manual PR - and who runs it> |

<!-- If the answer to any row is "two places", that is the defect this section exists to catch:
     record which one wins as a business rule, and file the merge as an OI. -->

## Design tokens

<!-- One row per token the spec constrains. Do not inventory every shade a tool generated - list
     the tokens screens and components actually reference. Values are the decision; usage is the
     contract. Unknown value: <unknown - OI-nn>, never a guess. -->

| ID | Token | Category | Value | Used for | Source |
|----|-------|----------|-------|----------|--------|
| DT-01 | `color.primary` | color | <hex/ref> | <primary actions, links> | <who decided / brand guide> |
| DT-02 | `color.danger` | color | <hex/ref> | <destructive actions, per [10](10-ui-ux-wireframes.md)'s destructive-action rule> | <source> |
| DT-03 | `font.body` | typography | <family, size, line-height> | <all body text> | <source> |
| DT-04 | `space.unit` | spacing | <px/rem base> | <the spacing scale multiplier> | <source> |
| DT-05 | `radius.default` | radius | <px> | <inputs, cards, buttons> | <source> |
| DT-06 | `shadow.raised` | shadow | <value> | <overlays, menus> | <source> |
| DT-07 | `motion.default` | motion | <duration, easing> | <transitions; respects reduced-motion, per NFR-USE> | <source> |

## Component inventory

<!-- One row per reusable component the screens in 10 are built from. "States" must cover at least
     the states table in 10 (empty / loading / error / no-permission / success) where the component
     can be in them. A component with no accessibility note is not done. -->

| ID | Component | Variants | States | Accessibility | Appears in |
|----|-----------|----------|--------|---------------|------------|
| DS-01 | <Button> | <primary / secondary / danger> | <default, hover, focus, disabled, loading> | <focus ring, min target size, per [NFR-USE-02](07-non-functional-requirements.md#nfr-usability)> | [SCR-01](10-ui-ux-wireframes.md) |
| DS-02 | <Form field> | <text / select / date> | <default, error, disabled> | <label bound to input, error announced> | [SCR-01](10-ui-ux-wireframes.md) |
| DS-03 | <Table> | <plain / selectable> | <empty, loading, error> | <header scope, keyboard navigation> | [SCR-02](10-ui-ux-wireframes.md) |

## Brand assets

| Asset | Location | Format | Constraint |
|-------|----------|--------|------------|
| Logo | <path or link> | <svg preferred> | <clear space, minimum size, do-not list> |
| Favicon / app icon | <path or link> | <formats required> | <sizes> |
| Illustration / imagery style | <link to guide, or "none">| - | <tone, licensing> |

## Accessibility mapping

<!-- The design system is where accessibility NFRs become checkable per component instead of
     aspirational per product. Every NFR-USE row that constrains the UI maps to the tokens or
     components that satisfy it. -->

| NFR | Satisfied by | How |
|-----|--------------|-----|
| [NFR-USE-02](07-non-functional-requirements.md#nfr-usability) | <DT-01..DT-02 contrast pairs, DS-01 focus states> | <contrast ratio, focus visibility> |
| [NFR-USE-03](07-non-functional-requirements.md#nfr-usability) | <DS-02 labels, DS-03 keyboard support> | <how it is verified> |

## Adoption rules

- New screens use tokens and inventory components; a screen needing a new component adds a `DS-nn`
  row here first - an unregistered component is scope creep with a paint job.
- A token value change is a contract change: one row in [13-revision-history.md](13-revision-history.md),
  and the downstream sync (see Source of truth) runs in the same change.
- If the repo carries a harness (`.claude/rules/frontend.md` from harness-bootstrap), keep that
  rule's primitives list consistent with the inventory here - this section is the source of truth,
  the rule links back to it.

## Coverage check

- [ ] Every component named in a screen's Elements table in 10 has a `DS-nn` row here.
- [ ] Every `DT-nn` and `DS-nn` cell is filled or carries `<unknown - OI-nn>`.
- [ ] Every NFR-USE row that constrains the UI appears in the accessibility mapping.
