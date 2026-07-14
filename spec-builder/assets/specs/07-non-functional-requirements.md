---
title: "Non-functional requirements"
sidebar_label: "07. Non-functional requirements"
description: "Performance, security, reliability, usability, and scalability requirements for {{PROJECT_NAME}}."
tags: [specs, nfr, security, {{PROJECT_SLUG}}]
---

# Non-functional requirements

<!-- Every NFR carries a number and a way to measure it. "Fast", "secure", and "scalable" are not
     requirements - they are adjectives, and they cannot fail a test. If the stakeholder cannot
     give you a number, propose one, mark it as a proposal, and register the confirmation as an
     open issue in [11](11-assumptions-constraints.md).

     ID scheme: NFR-XXX-nn, where XXX is the category (PERF, SEC, REL, USE, SCA, MNT, COM). -->

## Summary

| ID | Category | Requirement | Target | Priority |
|----|----------|-------------|--------|----------|
| NFR-PERF-01 | Performance | <requirement> | <number + unit> | Must |
| NFR-SEC-01 | Security | <requirement> | <target> | Must |

## Performance {#nfr-performance}

| ID | Requirement | Target | Measured how | Applies to |
|----|-------------|--------|--------------|------------|
| NFR-PERF-01 | <e.g. page response under normal load> | <p95 < N ms at M concurrent users> | <instrument, environment> | [FR-01](05-functional-requirements.md#fr-01) |
| NFR-PERF-02 | <batch or background job completion> | <duration for volume V> | <instrument> | <FR> |

<!-- A latency target without a percentile and a load level is not a target. State the load the
     number holds at, and where it is measured (server-side, or in the browser - they differ by an
     order of magnitude). -->

## Security {#nfr-security}

<!-- MANDATORY. Every subsection below is filled before this spec set is reviewable. None of them
     may say "TBD" - a security requirement deferred to implementation is a security requirement
     nobody writes. If the organisation has not decided, that is an open issue with a named owner
     and a date, registered in [11](11-assumptions-constraints.md) - which is a decision about a
     decision, and is still not a blank cell. -->

### Data classification

<!-- Which fields are personal, sensitive, or regulated. You cannot choose an encryption or
     retention rule until this table exists, which is why it comes first. -->

| Entity.field (from [08](08-data-model.md)) | Classification | Basis | Handling |
|--------------------------------------------|----------------|-------|----------|
| `<Entity>.<field>` | Public / Internal / Confidential / PII / Sensitive PII | <why: regulation, contract, policy> | <masking, redaction in logs and exports> |

| ID | Requirement |
|----|-------------|
| NFR-SEC-01 | Every field in the data dictionary carries a classification. Fields classified PII or above are excluded from application logs, error reports, and analytics events. |

### Encryption

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-SEC-02 | Encryption in transit | <e.g. TLS 1.2+ on every external and internal hop; no plaintext fallback> |
| NFR-SEC-03 | Encryption at rest | <e.g. database and object storage encrypted; which key management service; who can access the keys> |
| NFR-SEC-04 | Backups | <backups carry the same classification and the same encryption as the source> |

### Access control model

| ID | Requirement |
|----|-------------|
| NFR-SEC-05 | Authorisation is enforced server-side on every request. The permission matrix in [06](06-access-control.md) is the single source; the UI hiding a control is a convenience, never a control. |
| NFR-SEC-06 | Scope filters (Own/Team/All) are applied in the data layer, so a crafted request cannot widen scope. |
| NFR-SEC-07 | <privileged action> is logged with actor, target, and timestamp, and the log is not writable by the actor. |

### Secret management

| ID | Requirement |
|----|-------------|
| NFR-SEC-08 | No secret, key, token, or connection string is committed to the repository or embedded in a client bundle. Secrets live in <the secret store>. |
| NFR-SEC-09 | Secrets are rotatable without a code change, and rotation is <cadence or trigger>. |
| NFR-SEC-10 | Non-production environments never hold production credentials or unmasked production data. |

{{#IF_AI}}
### Untrusted content and the model

<!-- Required whenever user-supplied or third-party content reaches an LLM prompt - which, in this
     system, it does. These are not hardening extras; they are the requirements that keep a
     document upload from becoming a command channel. -->

| ID | Requirement |
|----|-------------|
| NFR-SEC-11 | Content originating from users or third parties is passed to the model as **data, never as instructions**. It is delimited and labelled untrusted, and no instruction found inside it is honoured. |
| NFR-SEC-12 | The model's output is treated as untrusted input by everything downstream: it is validated against a schema before it reaches a database, a shell, a browser, or another API. A model does not get to name a file path, a table, or a command. |
| NFR-SEC-13 | Tool and action permissions available to the model are the minimum for its task, and any irreversible action requires the human step named in [FR-01](05-functional-requirements.md#fr-01). |
| NFR-SEC-14 | Third-party model provider: <provider>. Data retention: <what the provider retains, for how long, and whether it trains on it>. Content classified PII or above is <excluded / permitted only under a signed DPA - state which>. |
| NFR-SEC-15 | Prompts, completions, and any content sent to the provider are logged under the same classification rules as the source data. |

<!-- NFR-SEC-14 is a contractual fact, not a guess. If nobody has read the provider's data-retention
     terms, that is an open issue with a named owner - do not write down what you assume the terms
     say. -->
{{/IF_AI}}

### Other security requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-SEC-16 | Input validation and output encoding | <injection classes explicitly covered> |
| NFR-SEC-17 | Dependency and vulnerability management | <scan cadence; severity that blocks a release> |
| NFR-SEC-18 | Compliance obligations | <regulation or standard that binds this system, or "none identified - confirmed by [SH-nn](02-stakeholders.md)"> |
| NFR-SEC-19 | Data retention and deletion | <how long each classification is kept; how a deletion request is honoured> |

## Reliability {#nfr-reliability}

| ID | Requirement | Target | Notes |
|----|-------------|--------|-------|
| NFR-REL-01 | Availability | <e.g. 99.5% during business hours; define the window> | <what counts as downtime> |
| NFR-REL-02 | Recovery point objective (RPO) | <max acceptable data loss> | <backup frequency that satisfies it> |
| NFR-REL-03 | Recovery time objective (RTO) | <max acceptable outage> | <the restore procedure, and whether it has been tested> |
| NFR-REL-04 | Degraded operation | <what still works when <dependency> is down> | <see [09](09-integration-interface.md)> |

<!-- An RTO nobody has rehearsed is an aspiration. If the restore has never been run, say so - it
     belongs in [12](12-technical-feasibility.md) as a risk. -->

## Usability {#nfr-usability}

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-USE-01 | <e.g. a first-time user completes [UC-01](05-functional-requirements.md) without training> | <success rate, or the training that is provided instead> |
| NFR-USE-02 | Accessibility | <standard and level, e.g. WCAG 2.1 AA, or the subset that is committed to> |
| NFR-USE-03 | Localisation | <languages in the UI; note that codes and enums stay English> |
| NFR-USE-04 | Error messages | <state what a user can do about the error, not just that it happened> |

## Scalability {#nfr-scalability}

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-SCA-01 | Data volume | <records at launch, and growth per year> |
| NFR-SCA-02 | Concurrent users | <at launch, and the horizon the design must not break at> |
| NFR-SCA-03 | Growth headroom | <what the system must absorb without re-architecture> |

<!-- Volumes come from the business, not from the developer's intuition. An order-of-magnitude
     error here is the difference between a table scan and an index - and it is discovered in
     production. -->

## Maintainability and operations {#nfr-maintainability}

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-MNT-01 | Observability | <what is logged, what is traced, what raises an alert, and who receives it> |
| NFR-MNT-02 | Deployment | <cadence, and whether it requires downtime> |
| NFR-MNT-03 | Supportability | <who operates it after handover, and what they are given> |

## Open points

- <every NFR whose target is a proposal rather than a stakeholder decision, linked to its OI in [11](11-assumptions-constraints.md)>
