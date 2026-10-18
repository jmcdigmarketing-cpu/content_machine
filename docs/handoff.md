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

**Written:** 2026-10-17 evening · **HEAD at write:** the wave 105 docs commit (`git log -1`) ·
**Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; CI read after each push.

**Cursor is out of usage for the month** - its queue is Claude's (roadmap next five).

**This evening (decisions 63-66 + wave 105), for whoever is next:**
- Crossposting is live (Buffer + R2). No spacing (§63); a game preview goes before its game
  (`crosspost._kickoff_for` reads the draft's `event_at`); the next 10 PM until a platform has
  hours of its own; Reels to 180 s (§64). The worker crossposts a scheduled video once it is
  public (`worker._crosspost_scheduled_live`).
- No YouTube cadence cap unless `MAX_VIDEOS_PER_WEEK` is set (§65) - `CadenceStatus.capped`.
- The idea menu is `best_bet.get_idea_menu` (§66): 5 ideas + 5 previews (`preview_options`,
  UFC cards from `seasonal_calendar.ufc_cards`, ESPN's `mma/ufc` board); `same_story` keeps an
  event an idea names out; times in the channel's zone with the label (`_kickoff`).
- `ops shelf --schedule [--runs] [--apply]` (#1273): public slots two a day for rendered,
  never-uploaded videos. Jobs 61-66 (runs 159 153 154 156 158 161) are queued, Sat 10 PM to Tue
  noon EDT; job 61 was left "running" by an interrupted worker - the next worker run reclaims it.

**Defects first:** none open of mine; #1283-#1285 filed (requeue_upload's private default, the
45-minute reclaim, news stretched past its window by two-a-day slots).

**Next:** the roadmap's five (#421 #425 #450 #457 #257), #1270 (schedule from watch-and-publish),
#1271 (why engagement fell). Suite green forward and reversed on the committed tree.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
