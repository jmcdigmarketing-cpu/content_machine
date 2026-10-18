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

**Written:** 2026-10-17 late night · **HEAD at write:** the wave 107 commit (`git log -1`) ·
**Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; CI read after the push.

**Cursor is out of usage for the month** - its queue is Claude's (roadmap next five).

**Wave 107:** `seasonal_calendar.event_for(title)` matches a headline to the week's games and
UFC cards (`_EVENTS`, filled by `fetch_week_topics`; 3 days back, 14 ahead). `spaced_queue.preview_event`
uses it when a draft has no `event_at` and the video was made before the event; `slot_for_run`
reads the run's own title when none is passed; `stale_renders.shelf_rows` marks a started one
`event_started` (retire line, stale) and `shelf_schedule` still lists it as skipped (#1286). `channel_health.engagement_why` (#1271).
Menu 7's `s` calls `go_public.apply_schedule_public` - private + `publishAt`, only from
`go_public` (the grand-audit test holds that) (#1270). `drafts_line` names the decisions left
before overnight drafts again (#1272). The booth's `/save-facts` (#257).

**Queue:** jobs 64-66 pending (156 Mon noon, 158 Mon 10 PM, 161 Tue noon EDT). Run 160 is
listed "its game has started" - the operator's to retire.

**Defects first:** none open of mine.

**Next:** the roadmap's five (#421 #425 #450 #457 #293). Suite 6,245, forward and reversed.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
