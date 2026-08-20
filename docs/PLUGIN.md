# Installing as a plugin

Both skills, `harness-bootstrap` and `spec-builder`, install as plugins in Claude Code,
Cursor, Codex, and any other client that reads the
[Agent Plugins](https://agent-plugins.org/) standard. This is the recommended install path:
updates arrive through the client's own update command instead of a manual re-download, and
the installed version is always identifiable. The zip download (see the README) remains fully
supported as the offline, pinned alternative.

| Client | Reads | Where it lives here |
|---|---|---|
| Claude Code | single-skill convention (`SKILL.md` at the directory root) | `.claude-plugin/marketplace.json` |
| Codex | `.codex-plugin/plugin.json` | `plugins/codex/<skill>/`, listed by `.agents/plugins/marketplace.json` |
| Cursor, VS Code, Copilot, Kiro, ChatGPT | Agent Plugins `plugin.json` at the plugin root | `plugins/<skill>/` |

**Why Codex has its own directory.** The first attempt put all three manifests in one directory,
since they sit at three different paths. Codex rejects it: when a root `plugin.json` is present
it validates it, and it refuses the `$schema` key that Agent Plugins requires
(`missing or invalid plugin.json`). Every other Agent Plugins field passes, so it is that one
key. Dropping `$schema` would satisfy both clients today, but it ships a manifest the standard
calls non-conformant, so each skill gets two roots instead. Pointing Codex at a `skills` path
outside its own root does not work either: Codex copies only the plugin root into
`~/.codex/plugins/cache/`, and the skill is simply absent after install.

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

**Verified how far:** all three routes were exercised against the real clients.

- **Claude Code** (`claude` 2.x): both plugins installed from this repository, client reported
  `harness-bootstrap 1.15.0`, Skills (1).
- **Codex** (`codex-cli` 0.148.0): marketplace added, both plugins installed, and
  `SKILL.md` confirmed present inside `~/.codex/plugins/cache/.../skills/<skill>/` after
  install, which is the part that had silently failed in an earlier layout.
- **Cursor** (`cursor-agent` 2026.08.11): the generated Agent Plugins tree was loaded with
  `--plugin-dir` and the agent confirmed the skill was available. The test used a
  uniquely-named copy of the generated tree, because both skills are also installed globally
  on the test machine and would otherwise have answered for themselves.

Three real defects came out of that round and are fixed: `policy.installation` had to be
`AVAILABLE` rather than a plausible-looking `user`; the marketplace source path resolves from
the repository root (`./plugins/...`), not from the directory holding `marketplace.json`; and
`.codex-plugin/plugin.json` needs an explicit `skills` path plus an `interface` block or the
install is refused.

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
