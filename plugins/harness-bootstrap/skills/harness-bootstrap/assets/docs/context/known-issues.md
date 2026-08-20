# Known issues - {{PROJECT_NAME}}

Issues, quirks, and environment gotchas that are known and not yet fixed, together with what to do
about them in the meantime.

Record the WORKAROUND, not just the symptom. An environment gotcha discovered once and left
unwritten gets rediscovered, at full cost, by every agent and every new engineer who hits it: the
build that only succeeds behind a specific wrapper, the test suite that fails under a sandbox that
blocks loopback, the parallelism flag that avoids an out-of-memory kill. Write it down the FIRST
time it is found.

Updated via `/sync-context`. Nothing is deleted: a fixed issue is marked Fixed and keeps its entry,
because the same symptom will come back and the old entry is what makes it recognizable.

| Issue | Symptom | Workaround | Status | Discovered |
|-------|---------|-----------|--------|------------|
| <short name> | <what you see when you hit it, in the words you would search for> | <what to do instead, precisely enough to follow without thinking> | Open | <YYYY-MM-DD> |

<!-- Status: Open | Workaround in place | Fixed (link the fix). -->

<!-- Never record a credential, a secret value, or real customer data here as part of a repro. -->
