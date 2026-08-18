# /review-changes

Run the reviewers over the current diff before merging.

1. Get the diff: `git diff` and `git diff --staged`.
2. Dispatch `code-reviewer` over the result.
3. Rebuild the code graph with python .claude/scripts/code-graph.py and refresh
   the HTML view with python .claude/scripts/graph-html.py.

Reviewing is not approving.
