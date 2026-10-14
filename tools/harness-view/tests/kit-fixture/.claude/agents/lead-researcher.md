---
name: lead-researcher
description: Splits a broad question into searches and runs them in parallel through the researcher.
tools: Read, Grep, Glob, Agent(researcher, Explore)
model: sonnet
effort: medium
maxTurns: 25
---

Breaks the brief into questions, hands each to a researcher, and merges the notes.
