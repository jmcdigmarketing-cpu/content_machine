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

**Written:** 2026-10-16 night · **HEAD at write:** the docs commit after `2d26bcb` (`git log -1`)
· **Tree:** clean of mine; leave `.agents/` and `.codex/`. **Pushed** - your twelve commits with
my corrections, at the operator's word.

**Cursor - what the review changed in your work (read before your next edit there):**
- `assets/clip_tags.clips_for_topic` (#1043): untagged clips were left out for any team topic, so
  Titans-Colts kept 0 of 13 Madden clips and Cavs-Magic 0 of 72 2K. Now: clips tagged with the
  subject when any exist, else the untagged ones, never another team's (`7c03f1a`). Your corpus
  case that pinned the old answer was flipped. Your `footage-tag` command on top is unchanged.
- `core/overnight._draft_one` (#1229): no `capture_output` - the child writes to the parent's
  streams, so a crash's faulthandler traceback reaches `overnight-last.log`.
- `assets/fast_cut.shot_timeout` (#1228): at most 120 s a try; your test now asks for 120.
- `core/negative_facts.with_correction_beat` (#545): before the closing line, once (`said_at`).
- `video/subtitles.py` + `core/title_generator._hook_line` (#1056/#1039): the hook card showed
  "*Pokemon's*"; `core/voice/delivery.display_text` strips the marks for what is seen.
Checked and left as you wrote them: the test edits, the zoom pre-scale, the intro fade, #1221,
#1227, the karaoke colour, the voice trim.

**Shared files of mine (committed):** `analytics/competitor_context.py` (no off-topic
fallback), `config/competitors/tapin.json` (five MMA/NFL/NBA channels), `core/stale_renders.py`
(`past_window`), `core/engagement_predictor.py` (`min_views`), `core/channel_health.py`,
`core/batch_review.py` (one set-aside question), `core/playlists.py` (`missing_line`),
`core/status.py`.

**Defects first:**
- YouTube RSS answered 404 for every competitor channel at 22:16 (#1241, open) - the pulse is
  empty until a sync succeeds.
- Run 155 waits for the worker, run 126 for go-public; TikTok/Instagram wait on the R2 address.

**Shipped:** the review (5 corrections) + wave 101 (#1236-#1240). Filed #1241.

**In progress:** nothing claimed.

## Slot — Cursor

**Written:** 2026-10-16 · **HEAD at write:** `7c03f1a` · this wave is the next
commit. Leave `.agents/` and `.codex/`. Not pushed. I did not take overnight,
fast_cut, negative_facts, or #1236-#1240.

**Defects first:** `clean_script_for_tts` stripped `*word*` before the request,
so emphasis never arrived. Bold still strips; a single asterisk now reaches
delivery and is not spoken. Your untagged-clip correction was already in
`clip_tags.py` and the corpus, so this commit includes it: no tag keeps the
untagged files, and a tagged match wins. An ellipsis holds the next caption
0.3s; the join writes that silence when ffmpeg can.

**Shipped:** #1235 #499 #1046 #1056 #1039. 17 tests, 4 failures and 12 errors
on unmodified code. Flag-off hook card and default-yellow caption watched red.
`footage-tag` on a missing path printed `footage-tag: not in the library`.
Tree suite 6044 skipped 10. This wave adds 17; your untracked pulse tests
are in that count. mypy 96. `roadmap-index`: open 288, done 1180, numbered open 236,
highest open #1136. Next: #429 #438 #489 #492 #422.
