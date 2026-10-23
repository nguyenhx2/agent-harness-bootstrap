# spec-builder

**English** · [日本語](README.ja.md)

Writes the requirements contract for a project under `docs/specs/`, from whatever you have: an
idea, meeting notes, a transcript, a PRD, legacy documents or an existing codebase. Every
requirement gets a stable FR ID and Given/When/Then acceptance criteria, assumptions and open
issues are flagged rather than guessed, and a one-page confirmation sheet lets a PO or client answer
yes, no or change. A JSON index lets agents read the contract without loading every document. It
never invents a requirement.

## Install

```text
/plugin marketplace add nguyenhx2/agent-harness-bootstrap
/plugin install spec-builder@agent-harness-bootstrap
```

Or as a plain skill, for any agent the `skills` CLI supports:

```bash
npx skills add nguyenhx2/agent-harness-bootstrap --skill spec-builder
```

Then run `/spec-builder` in your repository and point it at your input. It writes in the language
of your input.

## What it runs, sends and fetches

- **Runs:** `python` on the bundled `scripts/scaffold.py`, `scripts/ingest.py` and
  `scripts/route_sources.py`, which use only the Python standard library and write into the
  target repository. To read a format the standard library cannot, `ingest.py` calls the
  `markitdown` or `anydoc` converter if you have installed one; neither is bundled or installed
  for you.
- **Sends:** nothing. There is no telemetry, no server and no MCP server.
- **Fetches:** only a URL you give it as a source, through `markitdown`. Otherwise it reads only
  the files you point it at.

Its companion, `harness-bootstrap`, builds the agent harness that works from this contract.
Full documentation: <https://github.com/nguyenhx2/agent-harness-bootstrap>. Licensed
AGPL-3.0-only.
