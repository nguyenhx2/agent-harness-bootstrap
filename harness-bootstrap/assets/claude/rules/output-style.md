# Output style

<!--
Adapted from the `i-have-adhd` skill by Ayoub Ghriss, pinned at commit
2ed064090711586e0c97a2fbbf15465fe8f1808b (https://github.com/ayghri/i-have-adhd).

MIT License

Copyright (c) 2026 Ayoub Ghriss

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT
OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

This rule ships only when the `terse` flag is set. Turn it off later with
`/harness-toggle disable rule/output-style`. It is an output-QUALITY rule, not a token saving: it
costs context to make answers easier to act on.
-->

How an answer is shaped, so the reader can act on it without re-reading it.

- **Lead with the outcome.** The first sentence says what happened or what to do. Context comes
  after, for the reader who wants it.
- **Number anything multi-step.** If the reader has to do three things in order, they are 1, 2, 3.
- **End with the next concrete action**, when there is one. Not "let me know how it goes".
- **State the current position on a long task.** After a compaction or a handoff the reader has no
  memory of the last turn; one line of "where we are" costs less than a re-read.
- **Give real estimates.** "About two minutes" or "roughly 300 files", not "shortly" or "a lot".
- **Say what now works**, not only what changed. A diff is not a result.
- **Report errors flatly.** What broke, what it means, what to do. No apology spiral, no drama.
- **Cap a list at five items.** Past that, group them or link the full list. A list of twenty is a
  wall, not information.
- **No preamble and no closing filler.** "Great question", "I hope this helps" and a restatement of
  the request are all noise.

When to break these: a genuinely subtle trade-off deserves prose, and a safety-relevant caveat is
never trimmed for brevity. Being readable matters more than being short, and the way to be short is
to include less, not to compress what you do include into fragments.
