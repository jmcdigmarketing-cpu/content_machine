# Agent collaboration — Cursor and Claude Code on this repo

> **Read this before starting a project here.** It is short on purpose. It says what
> each agent is reliably good at, what each one reliably gets wrong, and who decides
> what gets built. The rules you must *follow* live in
> [.cursor/rules/content-machine.mdc](../.cursor/rules/content-machine.mdc) and
> [AGENTS.md](../AGENTS.md); this is the *why* behind two of them, plus credit where it
> is earned.
>
> Everything below is drawn from work actually done in this repo, with commits named.
> Nothing here is generic advice.

---

## Who decides what gets built

**The operator does.** Neither agent has earned that job, and there is a clean example
of why.

Claude Code ranked **Coverr the #1 tool borrow** — reasoning that `assets/manager.py` is
a clean name→class registry, so a third stock provider was a small, well-seamed add.
That is a *tractability* argument wearing a value argument's clothes.

Cursor built it, then went and looked at the render path, and wrote
[decisions.md §26](decisions.md): TapIn ships `background_mode: hybrid` at
`hybrid_local_ratio: 0.45`, so **~55% of runtime is already stock**, joined by a hard
concat with no fade. A fourth keyword API diversifies *the same class of footage*. The
operator's actual complaint was unrelated live-action and a jarring cut — which no
provider fixes. §26 also identified the one borrow that survives: a **crossfade at the
hybrid join**.

That is the best single piece of work in that wave, and it was Cursor overruling a
Claude Code recommendation with measured evidence. It is exactly what should happen.

**So the division is:**

| Question | Who is actually good at it |
|---|---|
| What is broken? What already exists? What does the evidence say? | **Claude Code** — it audits, checks claims against code, and reads licences |
| What does the implementation surface look like once touched? | **Cursor** — it builds at volume and finds out what the code really does |
| **What is worth building?** | **The operator.** Both agents bias toward what is easy to ship |

Feed ideas from both sides. Let the operator pick. An agent proposing its own backlog
tends to propose whatever it finds tractable.

---

## What Cursor does well — keep doing these

Checked, not flattery. Each of these is a behaviour worth repeating.

- **It respects a licence hold until the operator lifts it.** Edge TTS was the
  highest-value item on its own list and stayed parked (LGPL-3.0) until the
  operator replaced #412 with an unmodified `[free]` extra under Wave B
  constraints (decisions §28). It did not quietly add the dependency because
  the item was attractive.
- **It pushes back with evidence**, per §26 above.
- **It extends safety rails to classes nobody had noticed.** `tests/__init__.py` now
  blanks `DATABASE_URL` / `DATABASE_KEY` before any import and patches
  `TOPIC_GRAPH_FILE` into the suite store — plus `tests/test_database_url_isolation.py`
  as its own tripwire. Nobody asked for that.
- **It improved on a hook Claude Code wrote.** `.githooks/commit-msg` only *rejected*
  AI-attribution trailers; Cursor added `.githooks/prepare-commit-msg`, which *strips*
  the injected line so a legitimate commit can land. Strictly better.
- **It ships without dead code.** Every new `core/` module in the last wave —
  `chapters`, `demonetization`, `policy_runbook`, `seasonal_calendar`, `spoken_numbers`,
  `topic_graph` — has a real production caller. That rule has held.
- **It gets absence right where it counts.** `core/demonetization.py` opens with
  *"Missing is not $0"* and returns `None` for unmeasured revenue rather than zero. That
  is [decisions.md](decisions.md) §18 internalised rather than recited.
- **It says the tests failed first** in commit messages.

---

## What keeps going wrong — one pattern, two faces

Every defect found in the last four audits was **green in CI**. Not one was a crash, a
lint error, or a failing test. So "the tests pass" cannot be the finish line here, and
the misses are not sloppiness — they are **judgement at the boundary of the change**.

### Face 1 — "what else does this pattern catch?"

`core/spoken_numbers.py` rewrites numbers for TTS. Its record rule is
`\b(\d{1,2})-(\d{1,2})\b`, which is correct for `Gaethje is now 25-4` — the intended
case, and the case the tests cover. It also runs on every channel, unconditionally, in
`generate_audio`. Measured:

| Script says | Voice says |
|---|---|
| `Expect 5-10 years of compounding.` | "five ten years" |
| `Returns of 10-15% are typical.` | "ten fifteen%" |
| `She worked a 9-5 for a decade.` | "nine five" |

Worst on MoneyWise, which is made of ranges and percentages.

**The repo already contained the answer.** `core/fact_grounding.py` solves the identical
ambiguity, with a comment saying so — *"Fighter records only … Bare `10-9` / `29-28`
round scores must not fire"* — by requiring a verb cue (`is|now|went|record of`). The
new module dropped that guard.

Three tests were written. None used a range or a percent. The happy path was proved and
the question "what else does this match?" was never asked.

### Face 2 — "did this edit actually take effect?"

The dependency wave was real work, correctly planned and correctly written:
`pyproject.toml` moved to `Pillow==11.3.0` and `requests==2.32.4`, and moviepy was cut
properly (`_probe_video_duration` reused, `AudioFileClip` mocks removed).

The environment was never installed into. Measured:

```
declared               installed
Pillow    11.3.0   →   9.5.0     <- all 26 CVEs still live
requests  2.32.4   →   2.32.3
```

So the security fix is *declared*, not applied; CI (fresh install) now runs a different
Pillow major than the operator's machine; and the upgrade's entire risk — "will the
render still work on a new Pillow" — was never tested, because nothing has run on
11.3.0.

### The rule both faces collapse into

Ask **"and what else?"** before calling something done. What else does this regex catch;
what else does this flag disable; did the file edit actually change the running system.
Then check whether this codebase already answered the same question somewhere — twice
now, it had.

---

## What Claude Code gets wrong — for symmetry

Recorded because a one-sided retrospective is not honest.

- **It asserts from partial evidence.** It claimed Pillow was "pinned for moviepy 1.0.3
  compat" (moviepy does not depend on Pillow at all), and that `PROMPT_VERSION` was
  "bumped by hand with no A/B" (it is hashed from the prompt source, and
  `core/prompt_evals.py` is the A/B). Both were corrected in later commits — after being
  written down as fact.
- **It concluded from a truncated `grep`** that `hook_motion` had no production caller.
  `head` had cut the output; the caller was there.
- **It optimises for tractable**, per the Coverr example above.

The countermeasure is the same one it asks of Cursor: measure, then write.

---

## Working alongside each other

Both agents are frequently in this repo at the same time. Recent waves have been 1000+
uncommitted lines from one agent while the other was editing.

- **Re-read a file immediately before editing it.** State from earlier in a session is
  stale.
- **Never `git checkout` a file to discard changes you did not make.** This has already
  destroyed an in-progress edit once.
- **Stage explicitly by path.** `git add -A` sweeps up the other agent's work and
  misattributes it in the commit message.
- **Commit the other agent's body as written first**, then your fixes on top, so the
  delta is reviewable rather than silently folded in.

### The mailbox

Nothing signals that the operator switched tools, so [handoff.md](handoff.md) is how
the previous agent tells the next one what it did and what it broke. Two slots; you
overwrite your own and never touch the other's; you write it **as your last edit**, not
from memory next session.

It is wired at both ends deliberately. A mailbox referenced only from `AGENTS.md` is
two hops from the file an agent actually auto-loads, and a channel that is reachable
but never read is indistinguishable from silence — you end up writing "the other agent
hasn't replied" into an address that was never published. So
`.cursor/rules/content-machine.mdc` (what Cursor loads) and `CLAUDE.md` (what Claude
Code loads) each name `docs/handoff.md` themselves, in their first 40 lines, and
`tests/test_agent_handoff.py` fails if either end stops naming it.

**Two provenance channels, and you need both.** The `Co-authored-by:` trailer says
*who* wrote a commit — necessary because both agents commit as the same git author. The
SHA recorded in each slot says *what has landed since* that slot was written. `py -m
scripts.ops agents` reads both plus the uncommitted count. The mailbox can go stale;
`git log` cannot.

Signing was banned here until 2026-08-28 (hooks stripped and rejected the trailers).
The ban made the two agents indistinguishable in history at exactly the point the repo
started running both at once — 103 of 236 commits carry a trailer, Claude's last on
2026-07-09 and Cursor's on 2026-08-25, so the record silently became half-kept rather
than clean. It is now required, and the hook warns on a missing trailer instead of
rejecting a present one.

Deliberately not built: a machine-readable duplicate of the mailbox, a freshness gate
on it (a check that reddens because nobody worked the weekend gets ignored — same
failure as any always-on warning, §24), or any real-time channel.

## Related

- [.cursor/rules/content-machine.mdc](../.cursor/rules/content-machine.mdc) — the rules
  themselves, auto-loaded by Cursor.
- [AGENTS.md](../AGENTS.md) — the entry point and the 30-second version.
- [decisions.md](decisions.md) — §18, §24, §25 and §26 are the load-bearing ones.
- [tests/CLAUDE.md](../tests/CLAUDE.md) — store isolation, which is the rule with the
  worst blast radius when ignored.
