# Installing as a plugin

Both skills, `harness-bootstrap` and `spec-builder`, are distributed as a Claude Code
plugin marketplace hosted in this repo. This is the recommended install path: updates arrive
through `/plugin update` instead of a manual re-download, and the installed version is always
identifiable. The zip download path (see the README) remains fully supported as the offline,
pinned alternative.

## Add the marketplace and install

```bash
/plugin marketplace add nguyenhx2/agent-harness-bootstrap
/plugin install harness-bootstrap@agent-harness-bootstrap
/plugin install spec-builder@agent-harness-bootstrap
```

Install either plugin on its own, or both. Each plugin is a single skill: its `SKILL.md`
lives at the plugin's root with no `skills/` subdirectory and no skills manifest, so Claude
Code auto-loads it as a single-skill plugin. No further configuration is required.

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
