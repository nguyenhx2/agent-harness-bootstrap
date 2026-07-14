# docs/ directory tree scaffold (project-bootstrap)

Full target structure for the standardized documentation tree. Relative forward-slash paths only.
Content skeletons for every file live in `docs-pack.md`.

```
docs/
  README.md                  # index table: folder, read-level (ALWAYS/ON-DEMAND/MANUAL), content
  specs/                     # 13-section BA docs (spec-builder skill) - source of truth
                             # (leave for spec-builder; do not hand-invent sections)
  requirements/              # PRD-FR-NN-<slug>.md, one per feature + README index
  architecture/
    system-overview.md       # Mermaid high-level architecture (brownfield: the ACTUAL architecture)
    decisions/               # ADR-NNN-<topic>.md, immutable after Accepted + README index
    api-contracts/           # <domain>.md per API domain + README conventions
  tasks/
    README.md
    master-plan.md           # phased plan + index table (task/owner/deps/priority/phase/status)
    active/                  # TASK-NNN-<slug>.md - in progress (status: Active | Blocked)
    pending/                 # deferred/descoped with recorded reason (status: Pending) + README
    done/                    # finished tasks (status: Done)
  context/                   # AI long-term memory
    domain-glossary.md  business-rules.md  known-issues.md  tool-changelog.md
  templates/
    TASK.md.template  PRD.md.template  ADR.md.template
```

Language: docs prose in the project's docs language; task files, master-plan, and ADRs 100%
English; codes/enums/filenames always English.
