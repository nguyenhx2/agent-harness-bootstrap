---
title: "Glossary"
sidebar_label: "03. Glossary"
description: "Domain vocabulary for {{PROJECT_NAME}} - one term, one meaning."
tags: [specs, glossary, {{PROJECT_SLUG}}]
---

# Glossary

<!-- This is the anti-hallucination vocabulary. Every term used in 04-12 that a newcomer could
     misread belongs here. When an agent or a developer later invents a plausible-sounding synonym,
     this table is what catches it.

     A term that means two things in two departments is a defect in the model, not a documentation
     gap: record both meanings, mark the collision, and raise it as an open issue. -->

## Domain terms

| Term | Definition | Synonyms and aliases | Where it appears |
|------|-----------|----------------------|------------------|
| <Term> | <one sentence, in the business's language, not the schema's> | <what else people call it, including the wrong names> | <spec section, entity, or screen> |

<!-- Prefer the word the business uses and record the schema name as an alias. Renaming a column is
     cheap; retraining a company is not. -->

## Status values and enumerations

<!-- Every status a domain object can hold, in the order it holds them. Enum values are ALWAYS
     English regardless of the prose language of this document - they end up in code and in the
     database. The display label may be localised; the value may not. -->

| Entity | Value (English, canonical) | Display label | Meaning | Set by |
|--------|---------------------------|---------------|---------|--------|
| <entity> | `DRAFT` | <label shown to users> | <what is true when the object is in this state> | <role or system event> |

## Roles

<!-- Names only, defined here once; the permission matrix lives in
     [06-access-control.md](06-access-control.md). Two documents naming roles differently is the
     most common defect in a spec set. -->

| Role (English, canonical) | Who holds it | Defined in |
|---------------------------|--------------|------------|
| `<role_name>` | <group from [02](02-stakeholders.md)> | [06](06-access-control.md) |

## Abbreviations

| Abbreviation | Expansion | Notes |
|--------------|-----------|-------|
| <ABC> | <full form> | <the one thing a newcomer gets wrong about it> |

{{#IF_AI}}
## AI and model terms

<!-- Only the terms this project actually uses. Do not copy in a generic ML glossary - a term
     nobody on the team says is noise, and noise is what makes people stop reading glossaries. -->

| Term | Definition in this project |
|------|---------------------------|
| <term> | <what it means HERE, not in general> |
{{/IF_AI}}

## Term collisions

<!-- Where one word means two things. Leaving these implicit is how two teams ship incompatible
     features while both believing they read the same spec. -->

| Term | Meaning A (context) | Meaning B (context) | Resolution |
|------|--------------------|--------------------|------------|
| <term> | <meaning, and who uses it this way> | <meaning, and who uses it this way> | <the term this spec set uses, or [OI-nn](11-assumptions-constraints.md)> |
