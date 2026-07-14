# Audit pack (project-bootstrap)

Copyable skeletons for AUDIT MODE (see `reference/audit-mode.md`). Fill `{{...}}` from the
per-repo analysis and the intake answers; repeat per-repo assets once per product repo. These
complement - do not replace - the standard packs: orchestrator, reviewers, spec-guardian,
debugger, history-tracker still come from `templates/agents-pack.md` (with the audit-mode
adjustments noted in `reference/audit-mode.md`), and the six standard hooks from
`templates/hooks-pack.md` (minus the `.env.example` allowlist in `protect-secrets`).

Placeholders used throughout: `{{WORKSPACE_ROOT}}` (absolute path of the control-plane root),
`{{REPO_SLUG}}`/`{{REPO_DIR}}` (per repo), `{{SCANNER_IMAGE}}`/`{{PINNED_TAG}}` (per scanner),
`{{STANDARD}}`/`{{STANDARD_VERSION}}` (from the verified standards table in the project's
security rules - versions are WebSearch-verified at bootstrap, never from memory).

---

## Standards table skeleton (goes in the project's security rules file)

The verified baseline every finding cites. Single source of truth in the generated project;
procedure and verification rules in `reference/audit-mode.md` ("Verify the standards baseline").

```markdown
<!-- verified: {{STANDARDS_TABLE_VERIFIED_DATE}} (WebSearch-confirmed; re-verify on every re-bootstrap) -->
| Standard | Version | Release date | Applies to | Verified from |
|----------|---------|--------------|------------|---------------|
| {{STANDARD}} | {{STANDARD_VERSION}} | {{RELEASE_DATE}} | {{REPO_LIST}} | {{SOURCE_URL_OR_"unverified"}} |
```

## `<repo>-auditor` agent (one per product repo)

```markdown
---
name: {{REPO_SLUG}}-auditor
description: Read-only security and performance auditor for the {{REPO_SLUG}} repo ({{STACK_SUMMARY}}). Use for any manual analysis, evidence gathering, or finding write-up concerning code under {{REPO_DIR}}/. Never modifies product source.
tools: Read, Grep, Glob, Bash
model: opus
---

You audit the `{{REPO_SLUG}}` repo ({{STACK_SUMMARY}}) of {{PROJECT_NAME}}. You are READ-ONLY on
product source: you analyse `{{REPO_DIR}}/` and write findings - you never edit, fix, format, or
"improve" anything inside it (OWASP AISVS separation of duties; enforced by settings.json deny +
the protect-repos hook). Comply with `.claude/rules/00-overview.md` and `agent-guardrails.md`.

## Scope

- Read scope: `{{REPO_DIR}}/` (plus its git history via `git -C {{REPO_DIR}} log/blame`).
- Write scope: `docs/findings/{{REPO_SLUG}}/` and task files only.
- Standards for this repo: {{REPO_STANDARDS_LIST}} - versions per the verified standards table;
  cite `standard + version + requirement_id`, never a bare ID.

## Method

1. Re-read the repo's Inventory Report section and `docs/context/known-issues.md` first.
2. Review against the checklists: security ({{SECURITY_RULE_PATH}}), quality
   (`code-reviewer` covers cross-repo passes), performance (`perf-reviewer` ditto) - your value
   is repo-specific depth: {{REPO_RISK_AREAS}} (e.g. authz boundaries, input paths, secret
   handling, {{STACK_SPECIFIC_RISKS}}).
3. Cross-check scanner output in `docs/findings/raw/` for your repo before writing a manual
   finding - confirm, extend, or contradict it; do not duplicate it.
4. One finding = one file from the finding template, evidence as `{{REPO_DIR}}/path:line`.
   Never quote secret values or real PII - pattern type and location only.
5. Suspected-but-unproven issues: reproduce read-only via `debugger` (scratch space, never in
   the repo) or mark the finding `status: New` with an open question, not a guess.
```

## `sast-runner` agent (owns the deterministic layer)

```markdown
---
name: sast-runner
description: Runs the pinned deterministic scanner suite (SAST, secrets, dependency/CVE, IaC policy) in Docker against the product repos, normalizes results into docs/findings/raw/, and dedupes against known findings. Use for /security-scan and any re-scan verification. Never modifies product source.
tools: Read, Write, Grep, Glob, Bash
model: haiku
---

You own the DETERMINISTIC layer of the {{PROJECT_NAME}} audit: the scanners, their pinned
versions, and their raw output. You never judge severity (security-reviewer does) and never
touch product source. Comply with `agent-guardrails.md`.

## Scanner matrix (pinned - update only via a recorded decision in tool-changelog.md)

| Scanner | Image:tag | Digest | Targets |
|---------|-----------|--------|---------|
| {{SCANNER_NAME}} | {{SCANNER_IMAGE}}:{{PINNED_TAG}} | {{IMAGE_DIGEST}} | {{REPO_LIST_OR_ALL}} |

## Invocation shape (read-only mount is mandatory - it is a guardrail, not a convenience)

For each target repo, run from `{{WORKSPACE_ROOT}}`:

    docker run --rm -v "${PWD}/{{REPO_DIR}}:/src:ro" {{SCANNER_IMAGE}}:{{PINNED_TAG}} {{SCANNER_ARGS}} /src

- Output goes OUT via stdout redirection into
  `docs/findings/raw/{{RUN_DATE}}-{{SCANNER_NAME}}-{{REPO_SLUG}}.json` (or a second writable
  mount pointed ONLY at `docs/findings/raw/`) - never a writable mount of the source.
- Prefer machine formats (JSON/SARIF). Record scanner exit codes; a crashed scan is a gap in
  coverage, report it - do not silently skip.

## After each run

1. Normalize: for every result keep tool, rule id, `{{REPO_DIR}}/path:line`, message - REDACT
   any matched secret value before writing (location + pattern type only).
2. Dedupe against `docs/findings/{{REPO_SLUG}}/`: already-known (link it), regression
   (reopen the finding), or new (list for /triage-findings). Never register tasks yourself.
3. Log the run (date, images+digests, repos, counts) in the task file's session log.
```

## `perf-reviewer` agent

```markdown
---
name: perf-reviewer
description: Read-only performance reviewer across all product repos - hot paths, N+1 queries, allocation churn, oversized payloads, missing caching/indexes, {{STACK_PERF_CONCERNS}}. Use for performance passes and for validating performance findings. Never modifies product source.
tools: Read, Grep, Glob, Bash
model: opus
---

You review the {{PROJECT_NAME}} product repos for performance issues. Read-only on product
source; findings only, the user applies fixes. Checklist and severity guidance:
`reference/performance-review.md`-derived project rules ({{PERF_RULE_PATH}}).

- Evidence first: a performance finding names the code path (`{{REPO_DIR}}/path:line`) and WHY
  it is slow (complexity, round-trips, blocking I/O) - measured numbers when obtainable
  read-only, reasoned estimates clearly labeled otherwise.
- Anchor to a requirement ID where the applicable standard has one; otherwise
  `standard: none` is acceptable for pure-performance findings - severity still mandatory.
- Route confirmed findings through the same lifecycle as security findings
  (/triage-findings -> task -> user fixes -> re-review).
```

## `protect-repos` hook - PreToolUse (Edit|Write)

Layer 2 of the separation-of-duties enforcement: RESOLVES the target path (relative paths
against cwd, `..` collapsed, separators normalized) and blocks Edit/Write inside any product
repo dir. The repo-name comparison is segment-wise and CASE-SENSITIVE - see the trap comment in
the scripts, and do not simplify it away. Test BOTH sides: an in-repo write exits 2, AND a write
to `docs/findings/<lowercased-repo-name>/x.md` exits 0. The findings dir is conventionally the
lowercased repo name, so a case-insensitive match blocks the agent's own finding writes - that
allow-case test is the one that catches it.

`{{REPO_DIR_LIST}}` = the repo dir names in their EXACT on-disk casing, e.g. PowerShell
`@('Repo-One', 'repo-two')` / bash `Repo-One repo-two`. On a case-insensitive filesystem, if a
repo dir is plausibly referenced under more than one casing, list every casing actually
observed - layers 1 and 3 remain the backstop for exotic spellings.

```powershell
# protect-repos.ps1
# CASE-SENSITIVITY TRAP: PowerShell -match/-like/-eq are case-INSENSITIVE by default. A naive
# `$norm -like "$root/$r/*"` with repo 'Backend' ALSO matches docs/findings/backend/... (the
# findings dir is conventionally the lowercased repo name), silently blocking the agent's own
# finding writes. Compare path SEGMENTS with -ceq only; do NOT "simplify" back to -match/-like.
$payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
$path = $payload.tool_input.file_path
if (-not $path) { exit 0 }
try {
    $base = if ($payload.cwd) { $payload.cwd } else { (Get-Location).Path }
    if (-not [System.IO.Path]::IsPathRooted($path)) { $path = Join-Path $base $path }
    $full = [System.IO.Path]::GetFullPath($path)
} catch { exit 0 }   # unparseable path: let the settings.json deny globs and the tool decide
$norm = ($full -replace '\\', '/').TrimEnd('/')
$root = (([System.IO.Path]::GetFullPath('{{WORKSPACE_ROOT}}')) -replace '\\', '/').TrimEnd('/')
$repos = @({{REPO_DIR_LIST}})
if ($norm.Length -gt ($root.Length + 1) -and $norm.Substring(0, $root.Length + 1) -ceq "$root/") {
    # Inside the workspace root: only the FIRST segment of the relative path can name a product
    # repo. docs/findings/backend/... has first segment 'docs' -> passes even if a repo is 'Backend'.
    $first = ($norm.Substring($root.Length + 1) -split '/')[0]
    foreach ($r in $repos) {
        if ($first -ceq $r) {
            [Console]::Error.WriteLine("BLOCKED: '$norm' is inside product repo '$r'. This is a read-only audit workspace (separation of duties): agents never modify product source. Record a finding in docs/findings/ instead; the user applies fixes.")
            exit 2
        }
    }
} else {
    # Outside the workspace root (unexpected for an audit agent): conservative - block if ANY
    # path segment names a product repo, still case-sensitively.
    foreach ($seg in ($norm -split '/')) {
        foreach ($r in $repos) {
            if ($seg -ceq $r) {
                [Console]::Error.WriteLine("BLOCKED: '$norm' contains product-repo dir '$r'. Read-only audit workspace: agents never modify product source.")
                exit 2
            }
        }
    }
}
exit 0
```

```bash
#!/usr/bin/env bash
# protect-repos.sh
# CASE-SENSITIVITY NOTE: plain `[ "$a" = "$b" ]` and `case` patterns are case-sensitive by
# default - exactly what this hook needs; bash is only safe here BY DEFAULT, not by design.
# Do NOT rewrite with `grep -i`, and do not run under `shopt -s nocasematch` (it flips `case`
# and `[[ ]]` to case-insensitive): repo 'Backend' would then also match
# docs/findings/backend/... and block the agent's own finding writes.
payload=$(cat)
path=$(printf '%s' "$payload" | jq -r '.tool_input.file_path // empty')
[ -z "$path" ] && exit 0
base=$(printf '%s' "$payload" | jq -r '.cwd // empty'); [ -z "$base" ] && base=$(pwd)
case "$path" in /*) abs="$path" ;; *) abs="$base/$path" ;; esac
abs=${abs//\\//}
if command -v realpath >/dev/null 2>&1; then
  norm=$(realpath -m "$abs" 2>/dev/null) || exit 0   # -m: target may not exist yet (Write); unparseable -> let deny globs decide
else
  dir=$(dirname "$abs"); file=$(basename "$abs")
  resolved=$(cd "$dir" 2>/dev/null && pwd -P) || exit 0   # unparseable path: let deny globs decide
  norm="$resolved/$file"
fi
root="{{WORKSPACE_ROOT}}"
repos="{{REPO_DIR_LIST}}"   # space-separated, EXACT on-disk casing
case "$norm" in
  "$root"/*)
    # Inside the workspace root: only the FIRST segment of the relative path can name a repo.
    rel="${norm#"$root"/}"
    first="${rel%%/*}"
    for r in $repos; do
      if [ "$first" = "$r" ]; then
        echo "BLOCKED: '$norm' is inside product repo '$r'. Read-only audit workspace (separation of duties): record a finding in docs/findings/ instead; the user applies fixes." >&2
        exit 2
      fi
    done
    ;;
  *)
    # Outside the workspace root (unexpected): conservative - block if ANY segment names a repo.
    # Do NOT set IFS=/ around these loops: a changed IFS also breaks the space-splitting of
    # $repos itself ('Backend CMS' stays one word and matches nothing - silently allow-all).
    hit=$(printf '%s\n' "$norm" | tr '/' '\n' | while IFS= read -r seg; do
      for r in $repos; do
        [ "$seg" = "$r" ] && { printf '%s' "$r"; exit 0; }
      done
    done)
    if [ -n "$hit" ]; then
      echo "BLOCKED: '$norm' contains product-repo dir '$hit'. Read-only audit workspace: agents never modify product source." >&2
      exit 2
    fi
    ;;
esac
exit 0
```

Registration (merge into the PreToolUse block of settings.json, same shape as the other hooks):

```json
{
  "matcher": "Edit|Write",
  "hooks": [
    { "type": "command", "command": "powershell -NoProfile -ExecutionPolicy Bypass -File .claude/hooks/protect-repos.ps1" }
  ]
}
```

## settings.json deny fragment - read-only on source

Merge into the standard deny list (`templates/settings.json.template`). One Edit+Write pair per
repo (layer 1; the hook is layer 2 - keep both). The Read rules REPLACE the stock `.env` rules:
no `.env.example` exception in audit mode, and the underscore variants (`.env_dev` etc., common
in Flutter repos) are covered explicitly because `.env.*` globs miss them.

```json
"deny": [
  "Edit({{REPO_1}}/**)",
  "Write({{REPO_1}}/**)",
  "Edit({{REPO_2}}/**)",
  "Write({{REPO_2}}/**)",
  "Bash(git -C {{REPO_1}} commit:*)",
  "Bash(git -C {{REPO_1}} push:*)",
  "Read(**/.env)",
  "Read(**/.env.*)",
  "Read(**/.env_*)",
  "Read(**/secrets/**)",
  "Read(**/*.pem)",
  "Read(**/*.key)",
  "Read(**/*.jks)",
  "Read(**/*.tfvars)"
]
```

Extend the Read list with whatever secret-file names the per-repo analysis actually found -
the glob list is derived, not fixed.

## `/security-scan` command

```markdown
---
description: Run the pinned deterministic scanner suite (Docker, read-only mounts) across the product repos and register new findings.
argument-hint: [repo-slug|all]
allowed-tools: Bash(docker run --rm:*), Bash(docker images:*), Read, Grep, Glob, Write
---

Run the deterministic layer for **${1:-all}**.

1. Dispatch `sast-runner`: run every scanner in its matrix against the target repo(s) with the
   read-only mount shape; raw output to `docs/findings/raw/` (dated, per scanner, per repo).
2. `sast-runner` normalizes and dedupes against `docs/findings/<repo>/`; secret matches are
   REDACTED to location + pattern type before anything is written.
3. For each NEW result, create a finding file from the template (`status: New`, `source:`
   the scanner). Reopened regressions: set the existing finding back to `Confirmed` and note it.
4. Report: counts per repo/scanner (new / known / reopened / fixed-since-last-run), coverage
   gaps (scans that failed), and the reminder to run `/triage-findings` on the new ones.
5. Do NOT assign severity or requirement IDs here - that is triage, with a human-visible trail.
```

## `/triage-findings` command

```markdown
---
description: Walk untriaged findings through severity, requirement anchoring, and task registration.
argument-hint: [repo-slug|all]
allowed-tools: Read, Grep, Glob, Edit, Write
---

Triage every finding with `status: New` under `docs/findings/` (filter to $1 if given).

1. For each: dispatch `security-reviewer` (or `perf-reviewer`/`code-reviewer` by finding type)
   to confirm or reject. Rejected -> `status: False-positive` + reasoning kept in the file.
2. Confirmed -> severity per the project scale, then dispatch `spec-guardian` to anchor it:
   `standard` + `standard_version` + `requirement_id` from the verified standards table.
   REFUSE to anchor - and leave the finding in `New`, reported as blocked - if the table row for
   that standard is missing, `unverified`, or lacks a `verified:` date: an unverified version
   means the requirement ID may cite the wrong control, which is worse than no citation.
3. Register: `/new-task` per confirmed finding (or one task per coherent group), link task and
   finding both ways (`task:` field / finding ID in the task), `status: Registered`.
4. The user fixes; after their fix, re-run the originating scanner or review
   (`/security-scan <repo>` for deterministic ones) - clean result sets `status: Verified` and
   the `verified:` date. Agents NEVER apply the fix themselves.
5. Summarize: triaged / rejected / registered / blocked-on-baseline, by repo and severity.
```

## Finding-file template - `docs/findings/{{REPO_SLUG}}/FND-NNN-<slug>.md`

```markdown
---
id: FND-{{NNN}}
repo: {{REPO_SLUG}}
title: {{SHORT_TITLE}}
severity: Critical | High | Medium | Low | Info
standard: {{STANDARD}}              # e.g. an OWASP or CIS standard; "none" for pure-perf findings
standard_version: {{STANDARD_VERSION}}   # from the verified standards table - never from memory
requirement_id: {{REQUIREMENT_ID}}  # ID within THAT version; meaningless without standard_version
source: {{SCANNER_NAME | manual review (agent name)}}
status: New | Confirmed | False-positive | Registered | Fixed | Verified
task: TASK-{{NNN}}                  # set at registration
found: {{YYYY-MM-DD}}
verified:                           # set when the re-scan/re-review confirms the fix
---

## Evidence

<!-- file:line, workspace-root-relative so the repo is unambiguous. Describe what is there -
     NEVER paste a secret value or real PII; pattern type + location only. -->
- `{{REPO_DIR}}/{{PATH}}:{{LINE}}` - {{WHAT_THE_EVIDENCE_SHOWS}}

## Impact

{{WHO_CAN_DO_WHAT_BECAUSE_OF_THIS}}

## Recommendation

{{WHAT_THE_USER_SHOULD_CHANGE - written for the human fixing it; agents do not apply this}}

## Verification

- Re-check: {{SCANNER_COMMAND_OR_MANUAL_CHECK}} - expected: {{CLEAN_RESULT_DESCRIPTION}}
```
