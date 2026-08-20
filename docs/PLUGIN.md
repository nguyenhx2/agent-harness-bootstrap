# Installing as a plugin

Both skills, `harness-bootstrap` and `spec-builder`, install as plugins in Claude Code,
Cursor, Codex, and any other client that reads the
[Agent Plugins](https://agent-plugins.org/) standard. This is the recommended install path:
updates arrive through the client's own update command instead of a manual re-download, and
the installed version is always identifiable. The zip download (see the README) remains fully
supported as the offline, pinned alternative.

| Client | Reads | Marketplace in this repo |
|---|---|---|
| Claude Code | `.claude-plugin/plugin.json` convention (single-skill) | `.claude-plugin/marketplace.json` |
| Codex | `.codex-plugin/plugin.json` | `.agents/plugins/marketplace.json` |
| Cursor, VS Code, Copilot, Kiro, ChatGPT | Agent Plugins `plugin.json` at the plugin root | plugin directories under `plugins/` |

The three manifests sit at three different paths, so one plugin directory serves every client
at once, and all of them read the same `skills/` tree.

## Claude Code

```bash
/plugin marketplace add nguyenhx2/agent-harness-bootstrap
/plugin install harness-bootstrap@agent-harness-bootstrap
/plugin install spec-builder@agent-harness-bootstrap
```

Install either plugin on its own, or both. Each entry points at `harness-bootstrap/` or
`spec-builder/` directly: its `SKILL.md` lives at that directory's root with no `skills/`
subdirectory and no skills manifest, so Claude Code auto-loads it as a single-skill plugin.
No further configuration is required.

## Codex

```bash
codex plugin marketplace add nguyenhx2/agent-harness-bootstrap
```

Then open `/plugins` in Codex CLI and install `harness-bootstrap`, `spec-builder`, or both.
The marketplace lives at `.agents/plugins/marketplace.json`, the path Codex reads from a
repository, and its entries point at the plugin directories under `plugins/`.

## Cursor and other Agent Plugins clients

The directories under `plugins/` are Agent Plugins 1.1.0 packages: a `plugin.json` at the
plugin root and the skill under `skills/`. Cursor loads a local plugin by folder, so clone
this repository and copy (or link) the plugin directory into Cursor's local plugin folder:

```bash
git clone https://github.com/nguyenhx2/agent-harness-bootstrap
cp -r agent-harness-bootstrap/plugins/harness-bootstrap ~/.cursor/plugins/local/
```

Then reload the window. The same directories are what any other Agent Plugins client
consumes, because the standard fixes both the manifest path and the `skills/` location.

**Verified how far:** the Claude Code route was verified by installing both plugins from
this repository and reading back what the client reported. The Codex and Cursor routes are
built to the published specifications and their manifests are validated against the
Agent Plugins 1.1.0 JSON schema in CI, but the install round-trip has not been exercised
here - neither CLI is available on the machine this was built on. Treat those two as
specification-conformant rather than field-tested, and open an issue if a client disagrees.

## Invoking the skills

Once installed, invoke a skill by its namespaced form:

```
/harness-bootstrap:harness-bootstrap
/spec-builder:spec-builder
```

Claude also triggers each skill automatically from the trigger phrases in its
`SKILL.md` description, the same as when the skill is installed from the zip.

## Updating

```bash
/plugin update harness-bootstrap@agent-harness-bootstrap
/plugin update spec-builder@agent-harness-bootstrap
```

Neither plugin has its own `plugin.json`, so the `version` field in each marketplace
entry (`.claude-plugin/marketplace.json`) is what governs updates. Users only receive an
update when that field is bumped. Both skills release together under one repo version,
so both marketplace entries bump in lockstep with every release (see `docs/RELEASING.md`).

## Plugin route vs. zip route

Both are supported in parallel and will stay that way:

- **Plugin route**: managed by the `claude` CLI's `/plugin` commands, updates on demand,
  requires network access to this repo.
- **Zip route**: download a release archive from GitHub Releases and unzip it into
  `.claude/skills/`, works offline, pins to an exact version until you replace the files.

Neither path is being deprecated in favor of the other. Pick whichever fits your workflow.

## What is not covered

`tools/harness-view`, the standalone Rust binary, is not distributed as a plugin. Download
the platform binary for it from GitHub Releases, as with the zips.
