# Handoff — the mailbox

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-10-09

**Read this first, before any other file, every time you start work here.** More than
one agent works in this repo and nothing signals a switch. This file is how the
previous one tells you what it did and what it broke.

Two slots. **Overwrite your own; never edit the other agent's.** Keep each slot under
~25 lines — this is a mailbox, not an archive. The archive is
[handoff_synopsis.md](handoff_synopsis.md) (session state) and
[planning_log.md](planning_log.md) (why, append-only).

## Verify before you trust it

Prose goes stale; git does not. Every slot records the HEAD it was written at, so you
can check the claim instead of believing it:

```bash
git log <sha-from-the-slot>..HEAD --oneline
git status --short
```

**A slot several commits behind HEAD is normal** - the second agent helps intermittently,
so being behind is expected, not a defect. What matters is whether its claims match git.

If the slot says "committed" and `git log` shows nothing, the work is sitting
uncommitted in your tree — that has happened four times. If `git status` shows files
the slot never mentions, the other agent is **still working right now**: re-read any
file immediately before you edit it, and never `git checkout` a file to discard changes
you did not make.

Both agents commit as the same git author, so **sign your commits** —
`Co-authored-by: Cursor <cursoragent@cursor.com>` or
`Co-authored-by: Claude <noreply@anthropic.com>`. The trailer says *who*; the SHA anchor
above says *what has happened since*. You need both. (The hook used to reject these;
the operator lifted that ban on 2026-08-28.)

One command reads all of it — signed split, uncommitted count, and whether each slot is
behind HEAD:

```bash
py -m scripts.ops agents
```

## Write your slot before you stop

Not after the last edit — *as* the last edit. A slot written from memory next session
is the thing this file exists to replace. State defects before wins; if you found
nothing broken, say that explicitly rather than leaving it implied.

---

## Slot — Claude Code

**Written:** 2026-10-10 · **HEAD at write:** `ecd737c` + the wave 70 commit (`git log -1`) ·
**Tree:** clean after the commit.

**Read before editing:** the run's intent is read ONCE, in discovery -
`core.angle_intent.resolve_intent(topic, thoughts)`: the cue words, else (every text neutral) one
cheap model read that counts only when it quotes the idea (`model_read_from_reply`). It is kept in
`discovery.meta["intent_read"]` (`intent_read_from`); `main._screen_intent` and `run_pipeline`
reuse it - never call the model again. `IntentRead.also` is a second ask (#1096). A hope/plan run
counts its backing facts (`core/facts/stance_support.py`, `features["stance_support"]`). The suite
sets `STANCE_MODEL_READ` and `STANCE_RESEARCH` false; their tests turn them on. mypy **121**.

**Cursor:** `docs/cursor_brief_2026-10.md` has a "Start here (2026-10-10)" block - the prompt the
operator pastes. Shared files touched in wave 70: `main.py` (`_screen_intent`, the stance line under
the facts preview), `core/pipeline.py` (`resolve_intent` in discovery, `attach_stance_research`),
`.env.example` (two flags). #1097 (the mode drop-down) is yours.

**Defects first:**
- CGFtzpiA1so (made public by `go-public` with no id on 2026-10-10) - the operator is to check it.
- Run 120's confirmation source is "LINK"; `verify-claim --run-id 120` lists it again.
- #1088 is an operator call.

**Shipped:** wave 70 - #1096 #1089 #1095 + Cursor's prompt. Highest #1098. Next:
**#1007 · #1021 · #1006 · #1011 · #1060**.

## Slot — Cursor

**Written:** 2026-10-10 · **HEAD at write:** `43f68e0` plus the #1067 commit ·
**Tree:** `.agents/` and `.codex/` untracked; do not commit them.

**Defects first:**
- `footage-licence` replays a fixture. It does not search the network.
- yt-dlp pin not re-measured.
- Stock repeats when the cache has only one clip for that query.
- No brand font file is in the repo. A bright Flux picture is left without text.
- Thumbnail auto-pick runs only when `THUMBNAIL_SCORER_ENABLED` is on.
- A one-paragraph script is not rewritten by the lexicon.
- `voice_delivery` and `tts_model` are registered and not started.
- #1038 and the #217 editor stay open.
- Enter on the Shorts offer now cuts and queues.
- A freeze to the end of the file has a start and no duration.
- The intent card calls `idea_angle` on the UI thread when the topic field
  finishes editing. That is one cheap call, the same one the run makes again
  on the worker.

**Shipped:** #999 `43f68e0`. #1067: the new-video card shows angle 1 and the
read. Enter starts the run with the typed idea. 2 tests failed first. Next:
#1097. `main.py` gets a handoff note before the angle-step payload change.
