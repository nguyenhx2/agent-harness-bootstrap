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

The wiki repository only exists once the first page has been created through the GitHub UI. That is
a one-time manual step GitHub does not expose over the API:

1. Open https://github.com/nguyenhx2/agent-harness-bootstrap/wiki
2. Create the first page with any content and save it.

After that:

```bash
python scripts/build_wiki.py
git clone https://github.com/nguyenhx2/agent-harness-bootstrap.wiki.git /tmp/ahb-wiki
cp dist/wiki/*.md /tmp/ahb-wiki/
cd /tmp/ahb-wiki && git add -A && git commit -m "docs: rebuild wiki from the repository" && git push
```

## Do not edit pages in the wiki UI

Any page carrying the generated banner is overwritten on the next build. Change the asset it is
generated from, or the narrative source in `docs/wiki/`, and the page follows.
