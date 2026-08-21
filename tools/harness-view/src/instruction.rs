//! Instruction files: the contract each AI coding tool reads before it does
//! anything, and the only part of a harness that does not live under `.claude/`.
//!
//! The graph used to stop at the `.claude/` boundary, which meant the one file
//! every seat is told to obey - `AGENTS.md` - was invisible in a viewer whose
//! whole job is to show what governs an agent. Worse, the tools that are NOT
//! Claude Code read a different file each, so "the harness" a Cursor or a Kiro
//! user actually runs under was unrepresented entirely.
//!
//! ## What is in the table below, and what is not
//!
//! Every path here is sourced, and the source travels with it into the graph so
//! a reader can tell a documented fact from a guess - the same discipline
//! `harness-bootstrap/assets/references/models-and-tools.json` applies to model
//! and tool data. Two kinds of evidence count:
//!
//!   - **In-repo**: `harness-bootstrap/scripts/port.py` and `docs/tools/*.md`
//!     are authoritative for Claude Code, Codex and Cursor, because this
//!     repository generates and ports those files.
//!   - **First-party vendor docs**, cited by URL, for Kiro and Antigravity,
//!     which this repository does not port to.
//!
//! Anything that could not be confirmed from one of those two is NOT invented
//! into a path. It is recorded as a `note` on the entry it qualifies and shown
//! next to the file in the viewer - see the note on `AGENTS.md` about Kiro.
//!
//! ## Containment
//!
//! An instruction file sits at a known relative path, so nothing here is ever
//! built out of request bytes. `build()` takes a `key` that must match an entry
//! in `FILES` exactly, plus - for the directory-shaped entries - a BARE name
//! that passes the same character check `serve::resolve_command` uses. `..`, a
//! separator and a drive letter all fail before a path exists. `from_rel()` is
//! the read side of the same rule: it recognises a repo-relative path and then
//! rebuilds it from the table rather than trusting the string it matched.

use serde_json::{json, Map, Value};
use std::fs;
use std::path::{Path, PathBuf};

/// One instruction file, or one directory of them.
pub struct Spec {
    /// Stable key. Travels in the node id and is the only thing a write accepts.
    pub key: &'static str,
    /// Repo-relative path. The file itself when `ext` is empty, the directory
    /// holding a set of them when it is not.
    pub path: &'static str,
    /// Extension of the files in `path` when this entry is a SET, "" otherwise.
    pub ext: &'static str,
    /// The tools that read it.
    pub tools: &'static [&'static str],
    /// Where the claim above comes from.
    pub source: &'static str,
    /// True when `source` is in-repo evidence or a first-party vendor page.
    pub verified: bool,
    /// A caveat that belongs beside the entry, or "".
    pub note: &'static str,
    /// Must parse as JSON before it may be written back.
    pub json: bool,
    /// Graph node type. Everything here is "instruction" except settings.json,
    /// which already has a node type and only borrows this module's write path.
    pub kind: &'static str,

    /// May this file also appear in SUBDIRECTORIES, each copy governing its own subtree?
    ///
    /// `CLAUDE.md` does: Claude Code reads a per-directory file for work under that directory, and
    /// a real project puts one beside the module it describes. Treating it as a single root file
    /// meant a repo with `src/api/CLAUDE.md` showed one contract in the graph and obeyed four - and
    /// a viewer that shows three quarters of what governs a repo is worse than one that admits it
    /// does not look, because it reads as completeness.
    ///
    /// `AGENTS.md` carries the same per-folder convention and the same failure if missed.
    /// Everything else here is a genuine single file or a directory set, and stays false.
    pub nested: bool,
}

/// How deep a nested search goes, and how many files it will accept.
///
/// Caps rather than an unbounded walk: this runs on every scan, and a vendored tree that slips past
/// the skip list should cost a truncated list, not a hung viewer.
const NEST_MAX_DEPTH: usize = 8;
const NEST_MAX_FILES: usize = 200;

/// Directories a nested search never descends into. Vendored and build trees can hold instruction
/// files belonging to somebody else's project, and those are not this repo's contract.
const NEST_SKIP: &[&str] = &[
    "node_modules",
    "target",
    "dist",
    "build",
    "vendor",
    "__pycache__",
    "venv",
    ".venv",
];

/// The allow-list. Order is not significant; `from_rel` matches on the longest
/// applicable prefix by construction, because no entry's path is a prefix of
/// another's (`.agent/rules` and `.agents/rules` differ at the fourth
/// character, not by nesting).
pub const FILES: &[Spec] = &[
    Spec {
        key: "agents",
        path: "AGENTS.md",
        ext: "",
        tools: &["Claude Code", "Codex", "Cursor", "Antigravity"],
        source: "docs/tools/claude-code.md; docs/tools/codex.md; docs/tools/cursor.md; \
                 antigravity.google/docs/cli/best-practices",
        verified: true,
        note: "Kiro is deliberately absent from this list: no first-party Kiro page confirms \
               that it reads AGENTS.md, so the claim is unverified and is not made here. Kiro's \
               documented instruction surface is .kiro/steering/.",
        json: false,
        nested: true,
        kind: "instruction",
    },
    Spec {
        key: "claude",
        path: "CLAUDE.md",
        ext: "",
        tools: &["Claude Code"],
        source: "docs/tools/claude-code.md; harness-bootstrap/assets/root/CLAUDE.md",
        verified: true,
        note: "A thin @AGENTS.md import plus the Claude-only surface; it is not a second contract.",
        json: false,
        nested: true,
        kind: "instruction",
    },
    Spec {
        key: "gemini",
        path: "GEMINI.md",
        ext: "",
        tools: &["Antigravity"],
        source: "antigravity.google/docs/cli/best-practices",
        verified: true,
        note: "Antigravity accepts either GEMINI.md or AGENTS.md at the workspace root.",
        json: false,
        nested: false,
        kind: "instruction",
    },
    Spec {
        key: "cursor-rules",
        path: ".cursor/rules",
        ext: ".mdc",
        tools: &["Cursor"],
        source: "harness-bootstrap/scripts/port.py (port_cursor_rules); docs/tools/cursor.md",
        verified: true,
        note: "Written by the porter, one per .claude/rules/*.md. No `paths:` becomes \
               alwaysApply: true; `paths: [glob]` becomes globs:.",
        json: false,
        nested: false,
        kind: "instruction",
    },
    Spec {
        key: "kiro-steering",
        path: ".kiro/steering",
        ext: ".md",
        tools: &["Kiro"],
        source: "kiro.dev/docs/steering",
        verified: true,
        note: "Workspace steering files. This repository does not port to Kiro, so these are \
               hand-written where they exist.",
        json: false,
        nested: false,
        kind: "instruction",
    },
    Spec {
        key: "antigravity-rules",
        path: ".agents/rules",
        ext: ".md",
        tools: &["Antigravity"],
        source: "antigravity.google/docs/rules-workflows",
        verified: true,
        note: "Workspace rules, at the workspace or git root. Global rules live in \
               ~/.gemini/GEMINI.md, outside any repository, so they are not scannable.",
        json: false,
        nested: false,
        kind: "instruction",
    },
    Spec {
        key: "antigravity-rules-legacy",
        path: ".agent/rules",
        ext: ".md",
        tools: &["Antigravity"],
        source: "antigravity.google/docs/rules-workflows (documented back-compat path)",
        verified: true,
        note: "The superseded location, still read for backward compatibility.",
        json: false,
        nested: false,
        kind: "instruction",
    },
    // Not an instruction file, and not an instruction node: settings.json is
    // already in the graph. It is in this table because it needs exactly the
    // containment this module provides - a fixed relative path reached by key -
    // and because "make the harness's settings editable" is the same request as
    // "make the contract editable", answered by the same write path.
    Spec {
        key: "settings",
        path: ".claude/settings.json",
        ext: "",
        tools: &["Claude Code"],
        source: "docs/tools/claude-code.md",
        verified: true,
        note: "",
        json: true,
        nested: false,
        kind: "settings",
    },
];

/// Largest instruction file the editor will write back. Two orders of magnitude
/// above the biggest one this repository ships, and small enough that a runaway
/// page cannot fill a disk. Same reasoning as `serve::COMMAND_CAP`.
pub const EDIT_CAP: usize = 512 * 1024;

pub fn spec(key: &str) -> Option<&'static Spec> {
    FILES.iter().find(|s| s.key == key)
}

/// The character check every leaf name must pass. Identical in spirit to
/// `serve::resolve_command`: a name, never a path, so there is no traversal to
/// contain rather than a traversal that is contained.
pub fn bare_name_ok(n: &str) -> bool {
    !n.is_empty()
        && n.chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_' || c == '.')
        && !n.contains("..")
        && !n.starts_with('.')
}

/// Every copy of `file_name` BELOW the root, repo-relative and sorted. The root copy is not
/// included - `found` has already added it, and adding it twice would give one file two nodes.
///
/// Breadth-first with an explicit queue rather than recursion, so the depth cap is the depth cap
/// and not the stack's opinion of one. Directory symlinks are not followed: a link pointing back up
/// the tree would otherwise walk the repository again under a second set of names, and a link
/// pointing outside it would put somebody else's file in this repository's graph.
fn nested_copies(root: &Path, file_name: &str) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    let mut queue: Vec<(PathBuf, String, usize)> = vec![(root.to_path_buf(), String::new(), 0)];

    while let Some((dir, prefix, depth)) = queue.pop() {
        if depth >= NEST_MAX_DEPTH || out.len() >= NEST_MAX_FILES {
            continue;
        }
        let Ok(rd) = fs::read_dir(&dir) else { continue };
        for entry in rd.flatten() {
            let Ok(name) = entry.file_name().into_string() else {
                continue;
            };
            let Ok(ft) = entry.file_type() else { continue };
            if ft.is_symlink() {
                continue;
            }
            if ft.is_dir() {
                // Dot-directories are tool state, not the project's own contracts. `.claude` is
                // covered by its own entries in FILES and must not be walked for these.
                if name.starts_with('.') || NEST_SKIP.contains(&name.as_str()) {
                    continue;
                }
                let child = if prefix.is_empty() {
                    name.clone()
                } else {
                    format!("{prefix}/{name}")
                };
                queue.push((entry.path(), child, depth + 1));
            } else if name == file_name && !prefix.is_empty() {
                if out.len() < NEST_MAX_FILES {
                    out.push(format!("{prefix}/{name}"));
                }
            }
        }
    }
    out.sort();
    out
}

/// Repo-relative, slash-separated path for one entry.
pub fn rel_for(s: &Spec, name: &str) -> String {
    if s.ext.is_empty() {
        // A nested copy carries its whole repo-relative path as its name; the root copy has none.
        if s.nested && !name.trim().is_empty() {
            name.trim().to_string()
        } else {
            s.path.to_string()
        }
    } else {
        format!("{}/{}{}", s.path, name, s.ext)
    }
}

/// Is `rel` a repo-relative path to a nested copy of `file_name`?
///
/// Every component is checked with the same rule a bare name gets, so `..`, a leading dot, a
/// backslash, a drive letter and an absolute path all fail here - before any path exists. The last
/// component must be exactly the file being looked for, which is what stops this from becoming a
/// way to address arbitrary files by dressing them as an instruction file. At least one directory
/// component is required, because the root copy is not addressed this way.
pub fn nested_rel_ok(rel: &str, file_name: &str) -> bool {
    if rel.contains('\\') || rel.starts_with('/') {
        return false;
    }
    let parts: Vec<&str> = rel.split('/').collect();
    if parts.len() < 2 {
        return false;
    }
    if *parts.last().unwrap() != file_name {
        return false;
    }
    parts[..parts.len() - 1].iter().all(|p| bare_name_ok(p))
}

/// Build the absolute path for `key` (plus a leaf `name` for a set entry) out
/// of the table and the root. Nothing from the request survives into the path
/// except a leaf that passed `bare_name_ok`.
pub fn build(root: &Path, key: &str, name: &str) -> Result<PathBuf, String> {
    let s = spec(key).ok_or_else(|| {
        format!("refused: `{key}` is not an instruction file this viewer knows about")
    })?;
    if s.ext.is_empty() {
        let n = name.trim();
        if !n.is_empty() {
            // A per-folder copy is addressed by its repo-relative path. Every component is
            // validated before a path is built, and the last one must be the file itself, so this
            // cannot be turned into a way to reach an arbitrary file.
            if !s.nested {
                return Err(format!(
                    "refused: `{}` is a single file and takes no name",
                    s.path
                ));
            }
            if !nested_rel_ok(n, s.path) {
                return Err(format!(
                    "refused: `{name}` is not a path to a nested `{}` (plain directory names, \
                     then the file itself)",
                    s.path
                ));
            }
            let mut p = root.to_path_buf();
            for part in n.split('/') {
                p.push(part);
            }
            return Ok(p);
        }
        let mut p = root.to_path_buf();
        for part in s.path.split('/') {
            p.push(part);
        }
        return Ok(p);
    }
    let n = name.trim();
    if !bare_name_ok(n) {
        return Err(format!(
            "refused: `{name}` is not a bare file name (letters, digits, dash, underscore, dot)"
        ));
    }
    let mut p = root.to_path_buf();
    for part in s.path.split('/') {
        p.push(part);
    }
    p.push(format!("{n}{}", s.ext));
    Ok(p)
}

/// The read side: recognise a repo-relative path as an instruction file and
/// hand back the table entry plus the validated leaf. The caller rebuilds the
/// path with `build`, so a matched string is never itself used as a path.
pub fn from_rel(rel: &str) -> Option<(&'static Spec, String)> {
    let cleaned = rel.trim().replace('\\', "/");
    for s in FILES {
        if s.ext.is_empty() {
            if cleaned == s.path {
                return Some((s, String::new()));
            }
            continue;
        }
        let prefix = format!("{}/", s.path);
        let Some(tail) = cleaned.strip_prefix(&prefix) else {
            continue;
        };
        let Some(stem) = tail.strip_suffix(s.ext) else {
            continue;
        };
        if bare_name_ok(stem) {
            return Some((s, stem.to_string()));
        }
    }
    None
}

/// Every instruction file actually present under `root`, in table order and
/// then by name. A path that is absent is simply not a node: the graph reports
/// what a repository has, and a node for a file nobody wrote would be a
/// placeholder pretending to be a fact.
pub fn found(root: &Path) -> Vec<(&'static Spec, String, String)> {
    let mut out = Vec::new();
    for s in FILES {
        if s.kind != "instruction" {
            continue;
        }
        if s.ext.is_empty() {
            let mut p = root.to_path_buf();
            for part in s.path.split('/') {
                p.push(part);
            }
            if p.is_file() {
                out.push((s, String::new(), s.path.to_string()));
            }
            // A per-folder contract governs its own subtree, so every copy is part of what
            // actually governs this repository - not just the one at the top. The root copy above
            // keeps its empty name so its node id and its write path are unchanged; a nested one
            // is named by its repo-relative path, which is what makes it addressable at all.
            if s.nested {
                for rel in nested_copies(root, s.path) {
                    out.push((s, rel.clone(), rel));
                }
            }
            continue;
        }
        let mut dir = root.to_path_buf();
        for part in s.path.split('/') {
            dir.push(part);
        }
        let Ok(rd) = fs::read_dir(&dir) else { continue };
        let mut names: Vec<String> = rd
            .flatten()
            .filter(|e| e.path().is_file())
            .filter_map(|e| e.file_name().to_str().map(|x| x.to_string()))
            .filter_map(|f| f.strip_suffix(s.ext).map(|x| x.to_string()))
            .filter(|stem| bare_name_ok(stem))
            .collect();
        names.sort();
        for n in names {
            let rel = rel_for(s, &n);
            out.push((s, n, rel));
        }
    }
    out
}

/// The meta block a node carries: who reads this file, where that claim comes
/// from, and any caveat. `verified` travels as its own field so the UI can mark
/// an unsourced entry rather than presenting every row as equally certain.
pub fn meta_for(s: &Spec) -> Map<String, Value> {
    let mut m = Map::new();
    m.insert(
        "tools".into(),
        Value::Array(s.tools.iter().map(|t| json!(t)).collect()),
    );
    m.insert("source".into(), json!(s.source));
    m.insert("verified".into(), json!(s.verified));
    if !s.note.is_empty() {
        m.insert("note".into(), json!(s.note));
    }
    m
}

// ------------------------------------------------------------- routing tiers

/// One row of the "How much process a change gets" table that v1.18.0 put into
/// the generated `AGENTS.md`.
fn cells(line: &str) -> Vec<String> {
    let t = line.trim();
    if !t.starts_with('|') {
        return Vec::new();
    }
    t.trim_matches('|')
        .split('|')
        .map(|c| c.trim().trim_matches('*').trim().to_string())
        .collect()
}

fn is_separator(line: &str) -> bool {
    let c = cells(line);
    !c.is_empty()
        && c.iter()
            .all(|x| !x.is_empty() && x.chars().all(|ch| ch == '-' || ch == ':'))
}

/// Pull the tier table out of an instruction file, or an empty vector when the
/// file has none.
///
/// The header is matched by what its columns MEAN, not by the heading above it:
/// a first column called "Tier" beside a column that names who runs the change.
/// Matching the surrounding prose would break the moment anyone reworded the
/// section, and the table is the thing being read.
pub fn tier_rows(text: &str) -> Vec<Value> {
    let lines: Vec<&str> = text.lines().collect();
    for (i, line) in lines.iter().enumerate() {
        let head = cells(line);
        if head.len() < 3 {
            continue;
        }
        let lower: Vec<String> = head.iter().map(|c| c.to_lowercase()).collect();
        if lower[0] != "tier" || !lower.iter().any(|c| c.contains("who runs")) {
            continue;
        }
        let who_at = lower.iter().position(|c| c.contains("who runs")).unwrap_or(2);
        let change_at = lower
            .iter()
            .position(|c| c.contains("change"))
            .unwrap_or(1);
        let adds_at = lower.iter().position(|c| c.contains("adds")).unwrap_or(3);
        let mut out = Vec::new();
        for raw in lines.iter().skip(i + 1) {
            if is_separator(raw) {
                continue;
            }
            let c = cells(raw);
            if c.len() < 3 {
                break;
            }
            let pick = |idx: usize| c.get(idx).cloned().unwrap_or_default();
            let tier = pick(0);
            if tier.is_empty() {
                break;
            }
            out.push(json!({
                "tier": tier,
                "change": pick(change_at),
                "who": pick(who_at),
                "adds": pick(adds_at),
            }));
        }
        return out;
    }
    Vec::new()
}

// -------------------------------------------------------------------- writing

/// Re-apply the original file's dominant line ending to replacement content.
///
/// A browser textarea hands back LF for every line whatever the file used, so a
/// one-word edit to a CRLF file would otherwise rewrite every line in it. The
/// promise this write makes is that everything the user did not change stays
/// byte for byte, and on Windows that promise lives or dies here.
pub fn match_eol(original: &str, new: &str) -> String {
    let crlf = original.matches("\r\n").count();
    let lf = original.matches('\n').count();
    let unified = new.replace("\r\n", "\n");
    // Dominant, not merely present: a file with one stray CRLF among 300 LF
    // lines is an LF file with a defect, and converting all of it would be a
    // 300-line diff nobody asked for.
    if crlf > 0 && crlf * 2 >= lf {
        unified.replace('\n', "\r\n")
    } else {
        unified
    }
}

/// Write one instruction file (or settings.json) back.
///
/// Refusals are plain sentences because the page shows what comes back
/// verbatim. Three of them are load-bearing:
///   - an empty save is never an edit anyone meant;
///   - a JSON-shaped file that would stop parsing is refused before it lands,
///     because a broken `settings.json` silently unregisters every hook;
///   - the file must already exist, so this endpoint edits a contract and never
///     creates one out of a key.
pub fn write(root: &Path, key: &str, name: &str, content: &str) -> Result<String, String> {
    let s = spec(key).ok_or_else(|| {
        format!("refused: `{key}` is not an instruction file this viewer knows about")
    })?;
    if content.len() > EDIT_CAP {
        return Err(format!(
            "refused: {} bytes exceeds the {EDIT_CAP}-byte cap for an instruction file",
            content.len()
        ));
    }
    if content.trim().is_empty() {
        return Err("refused: empty content - an instruction file with nothing in it is not an \
                    edit, it is a deletion"
            .into());
    }
    let path = build(root, key, name)?;
    let rel = rel_for(s, name);
    if !path.is_file() {
        return Err(format!(
            "no such file: {rel} - this editor changes an instruction file that exists, it does \
             not create one"
        ));
    }
    if s.json {
        if let Err(e) = serde_json::from_str::<Value>(content) {
            return Err(format!(
                "refused: {rel} would stop being valid JSON ({e}). A settings.json that does not \
                 parse unregisters every hook in it without saying so."
            ));
        }
    }
    let original = fs::read_to_string(&path).unwrap_or_default();
    let body = match_eol(&original, content);
    if body == original {
        return Ok(format!("{rel} is unchanged"));
    }
    crate::toggle::atomic_write(&path, &body).map_err(|e| format!("write failed: {e}"))?;
    Ok(format!("wrote {rel}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn build_refuses_every_traversal_shape() {
        let root = Path::new("/tmp/whatever");
        // the set entries are the only ones that take a name at all
        for bad in [
            "..",
            "../../etc/passwd",
            "a/b",
            r"a\b",
            "C:/Windows/system32/config",
            ".hidden",
            "",
            "   ",
            "x?y",
        ] {
            assert!(
                build(root, "cursor-rules", bad).is_err(),
                "should have refused {bad:?}"
            );
        }
        // and a good one lands exactly where the table says
        let p = build(root, "cursor-rules", "00-overview").unwrap();
        assert!(p.ends_with("00-overview.mdc"), "{p:?}");
        // an unknown key never reaches disk
        assert!(build(root, "nope", "").is_err());
        // a single-file entry refuses a name rather than ignoring it
        assert!(build(root, "agents", "x").is_err());
        assert!(build(root, "agents", "").unwrap().ends_with("AGENTS.md"));
    }

    #[test]
    fn from_rel_recognises_only_the_table() {
        assert_eq!(from_rel("AGENTS.md").unwrap().0.key, "agents");
        assert_eq!(from_rel("CLAUDE.md").unwrap().0.key, "claude");
        let (s, n) = from_rel(".cursor/rules/testing.mdc").unwrap();
        assert_eq!((s.key, n.as_str()), ("cursor-rules", "testing"));
        let (s, n) = from_rel(".kiro/steering/product.md").unwrap();
        assert_eq!((s.key, n.as_str()), ("kiro-steering", "product"));
        assert_eq!(from_rel(".agents/rules/x.md").unwrap().0.key, "antigravity-rules");
        assert_eq!(
            from_rel(".agent/rules/x.md").unwrap().0.key,
            "antigravity-rules-legacy"
        );
        for bad in [
            "README.md",
            "src/main.rs",
            ".cursor/rules/../../../etc/passwd",
            ".cursor/rules/nested/x.mdc",
            ".cursor/rules/.hidden.mdc",
            "AGENTS.md/../SECRET",
            "",
        ] {
            assert!(from_rel(bad).is_none(), "should not have matched {bad:?}");
        }
    }

    #[test]
    fn tier_rows_reads_the_v1_18_table_and_nothing_else() {
        let md = "# AGENTS.md\n\n\
                  ### How much process a change gets\n\n\
                  | Tier | The change | Who runs it | What it adds |\n\
                  |------|------------|-------------|--------------|\n\
                  | **Direct** | one module, reversible | the owning agent, called straight | the agent proves each criterion |\n\
                  | **Standard** | one domain, several files | the owning agent | a hand check |\n\
                  | **Guarded** | two or more domains | `orchestrator` - one at a time | the full flow below |\n\n\
                  Choosing a heavier tier is a defect.\n";
        let rows = tier_rows(md);
        assert_eq!(rows.len(), 3, "{rows:?}");
        assert_eq!(rows[0]["tier"], "Direct");
        assert_eq!(rows[2]["tier"], "Guarded");
        assert!(rows[2]["who"].as_str().unwrap().contains("orchestrator"));
        assert!(rows[0]["change"].as_str().unwrap().contains("one module"));
        // a file with no such table reports none rather than guessing
        assert!(tier_rows("# AGENTS.md\n\n| a | b |\n|---|---|\n| 1 | 2 |\n").is_empty());
        assert!(tier_rows("no tables here at all").is_empty());
    }

    #[test]
    fn match_eol_keeps_a_crlf_file_crlf() {
        let crlf = "a\r\nb\r\nc\r\n";
        assert_eq!(match_eol(crlf, "a\nB\nc\n"), "a\r\nB\r\nc\r\n");
        let lf = "a\nb\nc\n";
        assert_eq!(match_eol(lf, "a\nB\nc\n"), "a\nB\nc\n");
        // one stray CRLF does not make an LF file a CRLF file
        let mostly_lf = "a\r\nb\nc\nd\ne\nf\n";
        assert_eq!(match_eol(mostly_lf, "a\nb\nc\n"), "a\nb\nc\n");
        // and an unchanged CRLF body round-trips to itself byte for byte
        assert_eq!(match_eol(crlf, "a\nb\nc\n"), crlf);
    }
}
