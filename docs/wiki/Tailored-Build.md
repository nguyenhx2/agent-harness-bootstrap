# Tailored Build

`spec-builder` ends with a contract. `harness-bootstrap` begins with a codebase. **The step between
them is where the team gets decided**, and it is the step most agent kits do not have at all.

## The problem it answers

The usual way to ship an agent kit is to ship all of it: every agent, a hundred skills, every rule
and every hook, installed before anyone has read the codebase. It looks generous. What it actually
does is hand you a team you did not pick, for a project it has never seen.

That costs more than it looks like it costs:

- **You pay context for all of it, in every session.** A rule that matches no file in your repo is
  not free. It is a tax on every request, forever.
- **Seats end up with no owner.** An agent nobody routes work to is not capability held in reserve.
  It is a name in a routing table that makes the table harder to read.
- **The advice goes generic.** Guidance written to be true in any repository is rarely specific
  enough to act on in yours.
- **You cannot tell what is load-bearing.** When everything is installed, nothing signals that it
  was chosen, so nobody can safely remove anything.

Completeness gets mistaken for fit. They are not the same thing, and only one of them is worth
paying for.

## What decides what

Both inputs are evidence. The contract says what has to be built, in numbered requirements. The
codebase analysis says what is already here. The roster comes from those two and from nothing else.

| Decided from | What it decides |
|---|---|
| The modules that actually exist | One dev agent each, scoped to real paths. No module, no seat. |
| The contract and your answers | Which of the 16 seats are filled. A run installs **7 to 15 of the 16 seats**, never all of them by default. |
| The manifests in your repo | Which skills are even proposed. You choose from that shortlist, and `/skill-wire` connects each one to the agent that will use it. |
| The paths that exist | Which rules are path-scoped, which is what keeps most rule content out of the default session. |

## The numbers are measured, not claimed

Scaffold with the leanest answers and you get 7 seats. Answer yes to databases, tests and a
long-lived project and you get 15.

That range is not a figure somebody wrote down. `scripts/check_numbers.py` computes it using the
**scaffolder's own selection function**, over every combination of the flags that gate an agent, so
it cannot drift from what a real run would install. Re-implementing the rule in the checker would
just create a second answer; reusing the real one makes disagreement impossible. It was
cross-checked against three real scaffold runs and agrees with all three.

If you change which agents are gated, that range changes, and every place the repository quotes it
fails until it is updated. That includes this page.

## Discovery and wiring are two problems

Finding a skill and connecting it are not the same job, and the harness treats them separately.

**Skill Discovery** answers *you cannot choose from a catalogue you have never read*. It reads this
project's manifests - Python, Ruby, .NET, Java and Kotlin, JavaScript, plus monorepo markers - works
out the stack, and only then proposes. Marketplace catalogues are a source, not an authority. Nothing
installs unless you pick it.

**Skill Wire** answers *installed is not the same as reachable*. `/skill-wire` connects a chosen
skill to the agent seat or command that will use it, and records that connection as a node in the
graph rather than a convention in a document.

Because the wire is a node, `harness-view` can show which skills are wired and which are merely
sitting on disk, and `assess` reports the difference as a finding rather than leaving you to notice
it.

## It is checkable

A seat nobody owns is a cost, not a capability. The same is true of a skill nobody is told to use,
and a rule that matches no file in the repository. `harness-view assess` names all three:

```bash
harness-view assess .
```

That is the point of stating the claim as a number instead of an adjective. "Tailored" is a word
anyone can put in a README. *Seven to fifteen of sixteen, and here is the finding when a seat has no
module* is something you can check.

## See also

- [[Flag Reference]] - what each answer turns on
- [[Agent Reference]] - the seats and when each is installed
- [[Harness View]] - the scoring engine
