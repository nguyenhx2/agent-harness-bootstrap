---
description: Run a structured brainstorming session on a decision or a feature idea.
argument-hint: <topic>
---

Brainstorm **$1**. If $1 is empty, ask for the topic and stop.

Dispatch `brainstormer`, with `tech-researcher` for evidence:

1. Frame the decision: what is actually being chosen, what constraints bind it, and what is already
   fixed by an Accepted ADR.
2. Produce 3 to 5 genuine options. A straw-man option that exists only to be rejected is noise.
3. Build a trade-off matrix: what each option costs, what it buys, and what it forecloses.
4. Give a recommendation with its reasoning. The user decides; the agent never decides silently.

When the recommendation rests on an unmeasured assumption, run a small timeboxed measurement spike
before committing to it. A measured result routinely overturns a plausible-sounding guess.

Outcomes:

- Stack-affecting: record it as an ADR with `/new-adr` before any implementation starts.
- Product-affecting: update the PRD in `docs/requirements/`.
- Neither: record it in the task file's decisions section so the reasoning survives.
