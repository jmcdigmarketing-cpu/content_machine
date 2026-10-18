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

**Written:** 2026-10-18 morning · **HEAD at write:** the wave 108 commit (`git log -1`) ·
**Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; CI read after the push.

**Cursor is out of usage for the month** - its queue is Claude's (roadmap next five).

**Wave 108:** `core.runs.script_report.script_of` is the stored script (a run has no `script`
field) - `analytics/hook_learning` and `unconfirmed_check` read it (#1287). Hook learning keeps
the last `HOOK_LEARN_DAYS` (90) and `guidance_from` holds back notes against the rewrite's rules
until n settles (decision 67). `apis.youtube_quota.quota_day` is the Pacific date (#1288).
`nightly_task.set_wake` / `task_wakes` / `wake_timers`; `_powershell` refuses in the suite -
**an old test set WakeToRun on the operator's real task before that guard existed** (#1289,
disclosed). `video/teaser.teaser_argv` (#1264). `render_video.caption_scrim_for` +
`caption_contrast.scrim_alpha`, a `drawbox` before `subtitles` only when needed (#1268).

**Live:** jobs 64-66 sent at 00:03 (156, 158, 161 scheduled). Overnight ran 8:04 AM on wake.
The task now may wake the PC; tomorrow's 5:00 run is the proof.

**Defects first:** none open of mine. #1290 (hook scorer vs stayed) waits on n=21.

**Next:** the roadmap's five (#421 #425 #450 #457 #293), #1291. Suite 6,268, forward and reversed.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
