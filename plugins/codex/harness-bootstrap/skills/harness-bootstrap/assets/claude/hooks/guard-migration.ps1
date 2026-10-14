# guard-migration.ps1
# Event: PreToolUse   Matcher: Edit|Write
# Flag: db
# Enforces: .claude/rules/data-model.md
# BLOCKS (exit 2) an edit to a database migration that already exists on {{DEFAULT_BRANCH}}.
# Applied migrations are immutable: every database that ran the old version keeps it, so an edit
# makes environments disagree silently. Write a NEW migration instead.
#
# Migration paths: any file under `migrations/` or `migration/`, `db/migrate/`,
# `alembic/versions/`, `flyway/` or `db/changelog/`. A migration that exists only on a feature
# branch is allowed; so is any brand-new migration file.
#
# WHY BLOCK, NOT WARN: see guard-migration.sh.
#
# PARITY CONTRACT: guard-migration.sh and guard-migration.ps1 must stay behaviorally EQUIVALENT.
#
# Contract: reads the PreToolUse JSON payload on stdin. exit 2 = BLOCK (reason on stderr, shown
# to Claude); exit 0 = allow. Fails OPEN on an unreadable payload, a missing git, or a repo with
# no {{DEFAULT_BRANCH}} branch.

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0
}

$path = ([string]$payload.tool_input.file_path) -replace '\\', '/'
if (-not $path) { exit 0 }
if ("/$path" -cnotmatch '/(migrations?|db/migrate|alembic/versions|flyway|db/changelog)/') { exit 0 }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { exit 0 }

$baseCwd = if ($payload.cwd) { [string]$payload.cwd } else { (Get-Location).Path }
$abs = if ($path -cmatch '^(/|[A-Za-z]:/)') { $path } else { (($baseCwd -replace '\\', '/').TrimEnd('/')) + '/' + $path }
$slash = $abs.LastIndexOf('/')
$dir = $abs.Substring(0, $slash)
$name = $abs.Substring($slash + 1)
if (-not (Test-Path -LiteralPath $dir -PathType Container)) { exit 0 }

function Test-Rev([string]$b) {
    & git -C $dir rev-parse --verify --quiet "$b^{commit}" 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

$branch = $null
foreach ($b in @('{{DEFAULT_BRANCH}}', 'main', 'master')) {
    if (Test-Rev $b) { $branch = $b; break }
}
if (-not $branch) { exit 0 }

& git -C $dir cat-file -e "${branch}:./$name" 2>$null
if ($LASTEXITCODE -eq 0) {
    [Console]::Error.WriteLine("BLOCKED by guard-migration: $path is already on $branch, so some database has applied it (or will). Editing it makes environments disagree with no error. Write a NEW migration that changes what this one did, and leave this file as it is.")
    exit 2
}
exit 0
