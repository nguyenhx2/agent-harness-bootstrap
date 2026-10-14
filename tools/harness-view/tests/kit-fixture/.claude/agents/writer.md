---
name: writer
description: Drafts and revises documents under docs/ from the researcher's notes.
tools: Read, Write, Edit, Grep, Glob
disallowedTools: Bash(rm *), WebFetch
model: sonnet
effort: medium
maxTurns: 40
permissionMode: acceptEdits
skills:
  - citation-style
mcpServers:
  - drive
  - glossary:
      type: stdio
      command: glossary-server
hooks:
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "bash .claude/hooks/style-lint.sh"
  Stop:
    - hooks:
        - type: prompt
          prompt: "Check every claim in the draft cites a source."
memory: project
background: false
omitClaudeMd: false
effort_note: ignored by Claude Code, kept to prove unknown keys do not break the scan
isolation: worktree
color: green
initialPrompt: |
  Read the brief in docs/brief.md first.
  Then ask the researcher for sources.
experimental:
  cacheTtl: 1h
---

Drafts documents. Follows `citation-style` for every reference.
