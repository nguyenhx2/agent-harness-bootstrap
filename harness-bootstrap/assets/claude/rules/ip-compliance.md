---
# {{SOURCE_GLOBS}} expands to one quoted glob per line, e.g. "src/**/*.{ts,tsx}"
# {{DEP_MANIFEST_GLOBS}} expands to the dependency manifests and lockfiles, e.g. "package.json",
# "package-lock.json", "pyproject.toml", "go.mod", "Cargo.toml"
paths:
  - "{{SOURCE_GLOBS}}"
  - "{{DEP_MANIFEST_GLOBS}}"
---

# Intellectual property

Applies when adding a dependency or writing source. Severity comes from the shared model in
code-quality.md; the output contract there applies here too. This file is about what the org is
allowed to SHIP - licence obligations, provenance, and ownership. security-privacy.md is about what
must not leak; model-policy.md is about where data may be processed.

An IP defect does not fail a test, does not slow anything down, and does not show up in a scanner
score. It shows up years later, in a diligence review or a letter, and by then it is in every release.
That is why an agent must not make one of these calls silently.

## Dependency licences

Adding a dependency is a **licensing decision**, not a packaging detail. The agent proposes; a human
accepts.

| Licence family | Position | Why |
|---|---|---|
| {{ALLOWED_LICENCES}} | Allowed | Permissive: use, modify, and distribute with attribution. The obligation is a notice, not the source |
| {{DENIED_LICENCES}} | Denied | Copyleft and network-copyleft. See below |
| Anything else, or missing/unclear licence | STOP and ask | No licence at all means no permission at all. "It's on GitHub" is not a grant |

The risk, stated plainly so nobody treats this as taste:

- **Copyleft (GPL, LGPL, MPL and relatives) in a proprietary product is a distribution obligation.**
  Linking or bundling can oblige the org to offer the corresponding source of the derived work under
  the same terms. That is a business decision, and it is irreversible once shipped.
- **Network-copyleft (AGPL) triggers on SaaS use.** The usual mental model - "we never distribute a
  binary, so copyleft cannot reach us" - is exactly the hole AGPL was written to close: serving users
  over a network IS the trigger. A single AGPL transitive dependency in a hosted service can put the
  whole service's source under an offer obligation.
- **Transitive dependencies count.** The licence that binds the org is the licence of everything that
  ends up in the artifact, not the licence of the package that was typed into the manifest.
- Dual-licensed and "source-available" packages (BSL, SSPL, Commons Clause, custom "free for
  non-commercial use") are DENIED by default: they read like open source and are not.

An agent adding a dependency states, in the task file: the package, its licence, its transitive
licence set, and which row of the table above it lands in. No row cited means the dependency is not
added.

## Provenance of generated code

Code an agent writes must be authored, not recalled.

- If an agent reproduces a substantial, recognisable block from a specific project it has seen - an
  algorithm implementation, a whole file's structure, a distinctive body of code - that is a
  **provenance risk**, and it gets flagged in the task file, not shipped. The failure mode: the org
  ships someone else's copyrighted code under its own copyright header, and nobody in the review chain
  knew it was a copy, because it arrived as an ordinary diff.
- Snippets pasted from a blog, an answer site, or another repo carry that source's licence with them.
  Cite the source in the task file, or write the code.
- Verbatim copy of a file from another repo into this one is not a refactor. It is a licence event,
  and it needs the same table above.
- Removing a licence header to make a file "look consistent" is a violation, not tidying.

## Attribution and NOTICE

- Preserve every licence header on every file that carries one. If a file is moved or split, the
  header moves with it.
- Permissive licences (MIT, BSD, Apache-2.0) require the copyright notice and licence text to travel
  with the distribution. Apache-2.0 additionally requires that any `NOTICE` file's contents be
  reproduced in the derived work.
- The project keeps a third-party notices file covering every shipped dependency. Adding a dependency
  updates it in the same {{PR_OR_MR}}. The failure mode is a slow one: notices are never wrong on the
  day the dependency lands, only on the day of the audit two years later.

## Ownership of agent-authored code

{{IP_OWNERSHIP_STATEMENT}}

Whatever that statement says, two consequences hold for this repo:

- Agent-authored code is **contributed under the same terms as human-authored code** - same review,
  same copyright header, same CLA or DCO obligations if the project has them. There is no separate,
  laxer path because a model wrote it.
- Commits carry no AI-attribution trailer (conventional-commits.md). Attribution of authorship is a
  legal position, not a courtesy line in a commit message.

## The check on a diff

Runnable by `code-reviewer` and `security-reviewer` on any diff, before merge:

1. **Did the manifest or lockfile change?** If yes, list every added package (direct AND transitive)
   and resolve each licence: `npm ls --all` + `license-checker` / `pip-licenses` / `go-licenses` /
   `cargo-deny check licenses`, whichever the stack has. Any licence in {{DENIED_LICENCES}}, any
   unclear or missing licence, any source-available licence: **Blocker**, and it is a routing decision
   for a human, not a fix the reviewer applies.
2. **Did a licence header disappear or change?** `git diff` on the header lines of every touched file.
   A deleted header is a Blocker.
3. **Is there a copied block?** Any added hunk of ~20+ lines that is stylistically foreign to the
   file around it, or carries another project's naming or comment conventions, is asked about in the
   review: where did this come from? Unanswered means it does not merge.
4. **Do the notices still cover the dependency set?** New shipped dependency, unchanged notices file:
   Major.

Findings are reported, not silently fixed - a reviewer that patches a licence problem has removed the
one decision a human was supposed to make.
