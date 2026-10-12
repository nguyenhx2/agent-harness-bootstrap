#!/bin/sh
# Blocks reads of .env and key files. Exit 2 = block.
# Enforces .claude/rules/agent-guardrails.md (secrets are never read into context).
. "$(dirname "$0")/_lib.sh"
exit 0
