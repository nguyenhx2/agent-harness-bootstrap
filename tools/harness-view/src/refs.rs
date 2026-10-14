//! Content references between harness files.
//!
//! A real harness says how its parts connect in the files themselves: an agent
//! lists the skills, commands and rules it works with, a hook names the rule it
//! exists for in its header and sources a shared `_lib.sh`, a command says which
//! subagent to start. The graph used to know none of that. It drew a skill edge
//! only from one phrasing ("Skills available: ..."), a hook-to-rule edge only
//! from a static table of this repository's own hook names, and nothing at all
//! between commands and agents - so a repository whose files plainly reference
//! each other came out as columns of disconnected boxes.
//!
//! This module reads the references out of the text. It is deliberately strict
//! about WHAT counts as a reference, because inventing a wire is worse than
//! missing one (a seat that mentions "performance budgets" is not wired to a
//! skill called `performance`). A name counts only when it is written in a way a
//! person writes a name on purpose:
//!
//!   - a path:        `.claude/rules/layering.md`, `.claude/skills/docs-sync/SKILL.md`,
//!                    `.claude/scripts/check-env.sh`, or a bare `_lib.sh` / `check-env.sh`
//!                    file name that is the whole word
//!   - a slash form:  `/review` - commands only
//!   - a code span:   `endpoint-scaffold`, or bold **endpoint-scaffold**, exactly
//!   - a slug:        a bare `security-privacy-reviewer` - hyphenated names only; a
//!                    single dictionary word in prose never counts
//!
//! The twin is `references()` in `harness-graph.py`; the two must agree, and
//! `scripts/check_graph_parity.py` compares their output byte for byte.

use std::collections::BTreeSet;

/// Every name the scan found, per kind. A reference resolves only to a name in
/// here, so the extractor never produces an edge to a node that does not exist.
#[derive(Default)]
pub struct Inventory {
    pub agent: BTreeSet<String>,
    pub skill: BTreeSet<String>,
    pub rule: BTreeSet<String>,
    pub command: BTreeSet<String>,
    pub hook: BTreeSet<String>,
    pub script: BTreeSet<String>,
}

impl Inventory {
    fn has(&self, kind: &str, name: &str) -> bool {
        match kind {
            "agent" => self.agent.contains(name),
            "skill" => self.skill.contains(name),
            "rule" => self.rule.contains(name),
            "command" => self.command.contains(name),
            "hook" => self.hook.contains(name),
            "script" => self.script.contains(name),
            _ => false,
        }
    }

    /// A bare name resolves to ONE kind. Commands are left out: a command is
    /// written `/name`, and a skill-backed command often shares its skill's name,
    /// so the bare word means the skill.
    fn by_name(&self, name: &str, with_rules: bool) -> Option<&'static str> {
        for kind in ["agent", "skill", "hook"] {
            if self.has(kind, name) {
                return Some(kind);
            }
        }
        if with_rules && self.rule.contains(name) {
            return Some("rule");
        }
        None
    }
}

fn word_char(c: char) -> bool {
    c.is_ascii_alphanumeric() || c == '_' || c == '-' || c == '.' || c == '/'
}

fn slug_char(c: char) -> bool {
    c.is_ascii_alphanumeric() || c == '_' || c == '-'
}

fn strip_ext<'a>(s: &'a str, exts: &[&str]) -> Option<&'a str> {
    for e in exts {
        if let Some(stem) = s.strip_suffix(e) {
            if !stem.is_empty() {
                return Some(stem);
            }
        }
    }
    None
}

/// Path-shaped words: `.claude/<dir>/<name>...`, also written relative to
/// `.claude/` (`rules/layering.md`) or as a bare file name (`/_lib.sh`).
fn path_refs(word: &str, inv: &Inventory, out: &mut BTreeSet<(&'static str, String)>) {
    let segs: Vec<&str> = word.split('/').collect();
    for i in 0..segs.len() {
        // The directory must be the harness's own: right after `.claude`, or the
        // first segment of the word. `.cursor/rules/x.md` and a skill's private
        // `scripts/` folder are other trees with their own names.
        let anchored = i == 0 || segs[i - 1] == ".claude";
        if !anchored || i + 1 >= segs.len() {
            continue;
        }
        let next = segs[i + 1];
        let hit = match segs[i] {
            "agents" => strip_ext(next, &[".md"]).map(|n| ("agent", n)),
            "rules" => strip_ext(next, &[".md"]).map(|n| ("rule", n)),
            "commands" => strip_ext(next, &[".md"]).map(|n| ("command", n)),
            "skills" => Some(("skill", next)),
            "hooks" => strip_ext(next, &[".sh", ".ps1"]).map(|n| ("hook", n)),
            "scripts" => strip_ext(next, &[".py", ".sh", ".ps1"]).map(|n| ("script", n)),
            _ => None,
        };
        if let Some((kind, name)) = hit {
            if inv.has(kind, name) {
                out.insert((kind, name.to_string()));
            }
        }
    }
    // A word that is ONE file name, possibly behind a leading slash
    // (`$(dirname "$0")/_lib.sh` tokenizes to `/_lib.sh`). Inside a longer path
    // it belongs to whatever directory holds it.
    let parts: Vec<&str> = segs.iter().copied().filter(|s| !s.is_empty()).collect();
    if parts.len() == 1 {
        let f = parts[0];
        if let Some(n) = strip_ext(f, &[".sh", ".ps1"]) {
            if inv.hook.contains(n) {
                out.insert(("hook", n.to_string()));
            }
        }
        if let Some(n) = strip_ext(f, &[".py", ".sh", ".ps1"]) {
            if inv.script.contains(n) {
                out.insert(("script", n.to_string()));
            }
        }
        // `/review`: a slash, then exactly a command name.
        if segs.len() == 2 && segs[0].is_empty() && inv.command.contains(f) {
            out.insert(("command", f.to_string()));
        }
    }
}

/// Spans between paired backticks or `**`, on one line, matched exactly.
fn marked_spans(line: &str) -> Vec<String> {
    let mut out = Vec::new();
    for delim in ["`", "**"] {
        let mut rest = line;
        while let Some(a) = rest.find(delim) {
            let after = &rest[a + delim.len()..];
            match after.find(delim) {
                Some(b) => {
                    out.push(after[..b].trim().to_string());
                    rest = &after[b + delim.len()..];
                }
                None => break,
            }
        }
    }
    out
}

/// Maximal runs of `keep` characters in `s`, as slices of it. The passes below
/// used to copy every word into a fresh String, which is where a 500 KB harness
/// spent most of its scan: in the allocator, not in the matching.
fn runs(s: &str, keep: fn(char) -> bool) -> impl Iterator<Item = &str> {
    let mut start: Option<usize> = None;
    s.char_indices().chain(std::iter::once((s.len(), ' '))).filter_map(move |(i, c)| {
        if keep(c) {
            start.get_or_insert(i);
            None
        } else {
            start.take().map(|a| &s[a..i])
        }
    })
}

/// Every harness item `text` references, as (kind, name).
pub fn references(text: &str, inv: &Inventory) -> BTreeSet<(&'static str, String)> {
    let norm = text.replace('\\', "/");
    let mut out = BTreeSet::new();

    // paths, bare file names and /commands. A word with no `/` can only be a
    // bare hook or script file name, so ordinary prose never reaches path_refs.
    for word in runs(&norm, word_char) {
        let w = word.trim_end_matches('.');
        if w.contains('/') || w.ends_with(".sh") || w.ends_with(".ps1") || w.ends_with(".py") {
            path_refs(w, inv, &mut out);
        }
    }

    // `name` and **name**, exact
    for line in norm.lines() {
        for span in marked_spans(line) {
            if let Some(kind) = inv.by_name(&span, true) {
                out.insert((kind, span));
            }
        }
    }

    // bare hyphenated slugs
    for word in runs(&norm, slug_char) {
        let w = word.trim_matches('-');
        if w.contains('-') {
            if let Some(kind) = inv.by_name(w, false) {
                out.insert((kind, w.to_string()));
            }
        }
    }
    out
}

/// The edge a reference becomes, named by what the two ends are.
pub fn edge_type(from_kind: &str, to_kind: &str) -> &'static str {
    match (from_kind, to_kind) {
        ("hook", "rule") => "enforces",
        ("hook", "hook") => "sources",
        (_, "script") => "runs",
        ("hook", _) => "refers",
        ("instruction", "agent") => "briefs",
        (_, "rule") => "cites",
        (_, "skill") => "uses",
        ("rule", "agent") => "refers",
        (_, "agent") => "delegates",
        (_, "command") => "invokes",
        _ => "refers",
    }
}

/// The node id prefix for a kind.
pub fn id_for(kind: &str, name: &str) -> String {
    let prefix = match kind {
        "command" => "cmd",
        k => k,
    };
    format!("{prefix}:{name}")
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The extractor before v1.21.2, verbatim: the oracle the faster one must match.
    fn references_v1(text: &str, inv: &Inventory) -> BTreeSet<(&'static str, String)> {
        let norm = text.replace('\\', "/");
        let mut out = BTreeSet::new();
        let mut cur = String::new();
        for c in norm.chars().chain(std::iter::once(' ')) {
            if word_char(c) {
                cur.push(c);
            } else if !cur.is_empty() {
                let w = cur.trim_end_matches('.').to_string();
                path_refs(&w, inv, &mut out);
                cur.clear();
            }
        }
        for line in norm.lines() {
            for span in marked_spans(line) {
                if let Some(kind) = inv.by_name(&span, true) {
                    out.insert((kind, span));
                }
            }
        }
        let mut cur = String::new();
        for c in norm.chars().chain(std::iter::once(' ')) {
            if slug_char(c) {
                cur.push(c);
            } else if !cur.is_empty() {
                let w = cur.trim_matches('-').to_string();
                if w.contains('-') {
                    if let Some(kind) = inv.by_name(&w, false) {
                        out.insert((kind, w));
                    }
                }
                cur.clear();
            }
        }
        out
    }

    fn inventory() -> Inventory {
        let mut inv = Inventory::default();
        let add = |set: &mut BTreeSet<String>, names: &[&str]| {
            for n in names {
                set.insert(n.to_string());
            }
        };
        add(&mut inv.agent, &["code-reviewer", "orchestrator", "security-reviewer", "ba-analyst", "qa-test"]);
        add(&mut inv.skill, &["docs-sync", "impeccable", "release", "endpoint-scaffold", "spec-builder"]);
        add(&mut inv.rule, &["repo-invariants", "layering", "security-privacy", "testing", "agent-guardrails"]);
        add(&mut inv.command, &["review", "review-changes", "harness-tune", "secret-scan"]);
        add(&mut inv.hook, &["_lib", "protect-secrets", "guard-main-commit", "guard-pr-merge", "guard-destructive"]);
        add(&mut inv.script, &["check-env", "env-read", "verify-plan", "task", "harness-check"]);
        inv
    }

    /// Text files under `dir`, recursively, until `out` holds `cap` of them.
    fn texts(dir: &std::path::Path, out: &mut Vec<String>, cap: usize) {
        let Ok(rd) = std::fs::read_dir(dir) else { return };
        for e in rd.flatten() {
            if out.len() >= cap {
                return;
            }
            let p = e.path();
            if p.is_dir() {
                let name = e.file_name().to_string_lossy().to_string();
                if !matches!(name.as_str(), "target" | "node_modules" | ".git") {
                    texts(&p, out, cap);
                }
            } else if let Ok(t) = std::fs::read_to_string(&p) {
                out.push(t);
            }
        }
    }

    #[test]
    fn the_fast_extractor_matches_the_previous_one() {
        let inv = inventory();
        let mut corpus: Vec<String> = vec![
            r#"see `.claude/rules/layering.md` and .claude\hooks\protect-secrets.sh, then /review."#.into(),
            r#"**docs-sync** runs `check-env.sh`; source "$(dirname "$0")/_lib.sh" -- code-reviewer..."#.into(),
            "\u{e9}t\u{e9} `release` \u{2014}security-privacy\u{2014} /harness-tune.\n---ba-analyst--- x.py".into(),
            String::new(),
        ];
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        texts(&root.join("tests"), &mut corpus, 300);
        texts(&root.join("../../.claude"), &mut corpus, 700);
        texts(&root.join("../../harness-bootstrap/assets"), &mut corpus, 1200);
        assert!(corpus.len() > 50, "too small a corpus to prove anything: {}", corpus.len());
        let mut hits = 0;
        for t in &corpus {
            let want = references_v1(t, &inv);
            hits += want.len();
            assert_eq!(references(t, &inv), want, "the extractors disagree");
        }
        assert!(hits > 20, "the corpus never references the inventory: {hits}");
    }
}
