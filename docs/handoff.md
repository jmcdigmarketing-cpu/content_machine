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

**Written:** 2026-10-25 night · **HEAD at write:** `3912f26` (wave 131 done; this planning commit
follows) · **Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; read CI.

**Next session (cloud or PC): build wave 132 from
[cloud_brief_wave132.md](cloud_brief_wave132.md)** - #1587-#1596, defects first, each with its
fixtures (the cloud has no `data/`). The operator: "week in review is far too long, video topics
have been rough and uninteresting" - decision 81: the Week in Review as every topic then the top 3
in full, 5-8 min; one marquee preview a night (answers #1586); headline drafts lead with the story
and why fans care; an overnight story needs 3+ outlets or a marquee name.

**Defects found tonight in the operator's session:** a hook swap stranding "for the first time in
his *career*." (`extract_hook` splits at "..."); every game preview read as an explainer (its own
brief's "what is at stake"); Week-6 links as run 196's sources; donation boilerplate kept as facts;
a flagged title shipped (run 195); the verdict comparison on 1 of 28 ratings.

**Wave 131 (done, `5454465` `3226422` `3912f26`, CI green):** decision 80 - one YouTube search per
topic per run, 9 of 11 playlists made (YouTube's limit refused the 10th; the worker retries daily),
the menu by organic views per video; captions show the script's numbers; a claim-held preview
toasts 6 h before its game.

**Cursor is out of usage for the month** - its queue is Claude's.
**Operator:** publish the Google app before Fri 10-30. The brief's LOCAL checks need the PC.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
