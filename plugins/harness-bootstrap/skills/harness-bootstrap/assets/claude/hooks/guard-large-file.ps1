# guard-large-file.ps1
# Event: PreToolUse   Matcher: Bash|PowerShell
# Flag: hooks_strict
# Enforces: .claude/rules/code-quality.md (repository hygiene)
# BLOCKS (exit 2) a `git add` or `git commit` that would put into history a file over 5 MB
# ($LimitKB) or a binary artifact by extension ($BinExt), unless Git LFS tracks the path.
# `git add` is checked with `git add --dry-run <same args>`; `git commit` checks what is staged,
# plus the tracked changes `-a` would stage.
#
# WHY BLOCK, NOT WARN: see guard-large-file.sh - a blob in history is permanent, and a local
# database or model dump is how real data leaks into a repository.
#
# PARITY CONTRACT: guard-large-file.sh and guard-large-file.ps1 must stay behaviorally
# EQUIVALENT - same limit, same extension list, same LFS exemption.
#
# Contract: reads the PreToolUse JSON payload on stdin. exit 2 = BLOCK (reason on stderr, shown
# to Claude); exit 0 = allow. Fails OPEN on an unreadable payload or a missing git.

$LimitKB = 5120
$BinExt = @('zip', 'tar', 'gz', 'tgz', 'bz2', 'xz', '7z', 'rar', 'jar', 'war', 'exe', 'dll', 'so', 'dylib',
    'bin', 'iso', 'dmg', 'msi', 'mp4', 'mov', 'avi', 'mkv', 'mp3', 'wav', 'flac', 'psd', 'sqlite', 'sqlite3',
    'db', 'mdb', 'parquet', 'pkl', 'pickle', 'pt', 'pth', 'onnx', 'h5', 'ckpt', 'safetensors')

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0
}

function Unquote([string]$t) {
    if ($t.StartsWith('"')) { $t = $t.Substring(1) }
    if ($t.EndsWith('"')) { $t = $t.Substring(0, $t.Length - 1) }
    if ($t.StartsWith("'")) { $t = $t.Substring(1) }
    if ($t.EndsWith("'")) { $t = $t.Substring(0, $t.Length - 1) }
    return $t
}

function Join-Dir([string]$base, [string]$d) {
    $d = $d -replace '\\', '/'
    if ($d -cmatch '^(/|[A-Za-z]:/)') { return $d }
    return "$base/$d"
}

function Test-Paths([string]$root, [string[]]$paths) {
    foreach ($f in $paths) {
        if (-not $f) { continue }
        $full = "$root/$f"
        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { continue }
        $attr = & git -C $root check-attr filter -- $f 2>$null
        if ("$attr" -cmatch ': filter: lfs$') { continue }
        $dot = $f.LastIndexOf('.')
        if ($dot -ge 0) {
            $ext = $f.Substring($dot + 1).ToLower()
            if ($BinExt -ccontains $ext) {
                [Console]::Error.WriteLine("BLOCKED by guard-large-file: '$f' is a binary artifact (.$ext). Committed, it stays in every clone forever - and a local database or model dump is the usual way real data leaks into a repo. Add it to .gitignore, track it with Git LFS (git lfs track '*.$ext'), or keep it in an artifact store.")
                exit 2
            }
        }
        $kb = [math]::Floor((Get-Item -LiteralPath $full).Length / 1024)
        if ($kb -gt $LimitKB) {
            [Console]::Error.WriteLine("BLOCKED by guard-large-file: '$f' is $kb KB, over the $LimitKB KB limit. Large blobs stay in history forever. Track it with Git LFS, generate it at build time, or keep it out of the repo.")
            exit 2
        }
    }
}

$cmd = [string]$payload.tool_input.command
if (-not $cmd) { exit 0 }
if ($cmd -cnotmatch '(^|[^a-zA-Z0-9_-])git([^a-zA-Z0-9_-]|$)') { exit 0 }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { exit 0 }
$workdir = if ($payload.cwd) { ([string]$payload.cwd) -replace '\\', '/' } else { (Get-Location).Path -replace '\\', '/' }

foreach ($seg in ($cmd -split '&&|\|\||;|\||\r?\n')) {
    $toks = @($seg.Trim() -split '\s+' | Where-Object { $_ -ne '' })
    $n = $toks.Count
    if ($n -eq 0) { continue }
    if ($toks[0] -ceq 'cd' -and $n -ge 2) { $workdir = Join-Dir $workdir (Unquote $toks[1]); continue }
    for ($i = 0; $i -lt $n; $i++) {
        $tok = Unquote $toks[$i]
        if (-not ($tok -ceq 'git' -or $tok -clike '*/git')) { continue }
        $gdir = $workdir; $sub = ''; $k = $i + 1
        while ($k -lt $n) {
            $a = Unquote $toks[$k]
            if ($a -ceq '-C') { $k++; if ($k -lt $n) { $gdir = Join-Dir $gdir (Unquote $toks[$k]) } }
            elseif ($a -ceq '-c') { $k++ }
            elseif ($a.StartsWith('-')) { }
            else { $sub = $a; break }
            $k++
        }
        $root = & git -C $gdir rev-parse --show-toplevel 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $root) { break }
        $root = ([string]$root).Trim()
        $argv = @()
        for ($j = $k + 1; $j -lt $n; $j++) {
            $a = Unquote $toks[$j]
            if ($a.Contains('>') -or $a.Contains('<')) { break }
            $argv += $a
        }
        if ($sub -ceq 'add') {
            $out = & git -C $gdir add --dry-run @argv 2>$null
            $paths = @()
            foreach ($line in @($out)) {
                $m = [regex]::Match([string]$line, "^add '(.*)'$")
                if ($m.Success) { $paths += $m.Groups[1].Value }
            }
            Test-Paths $root $paths
        } elseif ($sub -ceq 'commit') {
            Test-Paths $root @(& git -C $gdir diff --cached --name-only 2>$null)
            $all = $false; $skip = $false
            foreach ($a in $argv) {
                if ($skip) { $skip = $false; continue }
                if ($a -ceq '--all') { $all = $true }
                elseif (@('-m', '-F', '-C', '-c', '--author', '--date', '--file') -ccontains $a) { $skip = $true }
                elseif ($a.StartsWith('--')) { }
                elseif ($a.StartsWith('-')) {
                    if ($a -cmatch 'a') { $all = $true }
                    if ($a -cmatch '[mFCc]$') { $skip = $true }
                }
            }
            if ($all) { Test-Paths $root @(& git -C $gdir diff --name-only 2>$null) }
        }
        break
    }
}
exit 0
