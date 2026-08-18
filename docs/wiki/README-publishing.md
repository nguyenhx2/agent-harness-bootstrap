# Publishing the wiki

The pages in this directory are the SOURCE for the GitHub wiki. The wiki itself is a separate git
repository (`<repo>.wiki.git`) and nothing in CI reads it, which is exactly why wikis rot: the counts
inside them go stale and no check ever notices.

So the reference pages are not written here at all. They are generated from the assets by
`scripts/build_wiki.py`, and the narrative pages beside them are copied through unchanged.

## Build

```bash
python scripts/build_wiki.py            # -> dist/wiki/
```

## Publish

**Automatically, on every merge to `main`.** `.github/workflows/wiki.yml` rebuilds the wiki and
pushes it, and is a no-op unless the built output actually differs. There is deliberately no path
filter: the builder reads the assets, the scaffolder's flag set, and figures derived from
`benchmark.py`, so the real input set is most of the repository and a filter would have been wrong
the first time someone added an input. Comparing the built output instead cannot be wrong.

The `eval` workflow also builds the wiki on every run, so a change that breaks a page fails the
build before it can reach the wiki at all.

### By hand, if you need to

```bash
python scripts/build_wiki.py
git clone https://github.com/nguyenhx2/agent-harness-bootstrap.wiki.git /tmp/ahb-wiki
cp dist/wiki/*.md /tmp/ahb-wiki/
cd /tmp/ahb-wiki && git add -A && git commit -m "docs: rebuild wiki from the repository" && git push
```

### One thing the automation cannot do

The wiki repository does not exist until the first page has been created through the GitHub UI.
That is a one-time manual step GitHub does not expose over the API, and it has already been done
for this repo. A fork would need to do it once before the workflow can push.

## Do not edit pages in the wiki UI

Any page carrying the generated banner is overwritten on the next build, and the next build now
happens on every merge. Change the asset it is generated from, or the narrative source in
`docs/wiki/`, and the page follows.
