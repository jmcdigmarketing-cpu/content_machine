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

**Written:** 2026-10-17 early · **HEAD at write:** my wave 102 commit on `bef5a56` (`git log -1`)
· **Tree:** clean of mine; leave `.agents/` and `.codex/`. **Not pushed** - `bef5a56` is not
reviewed yet; the grand audit (the operator's next prompt) reviews it, then pushes everything.

**Cursor - your next fifteen, in this order (the operator asked me to write it):**
1. **#1248** menu option 7 "Watch and publish" (since Oct 1: 38 drafts, 4 rendered overnight, 0
   decisions, 1 public) - `core/ui.prompt_startup_mode` + `main.py`, through `go-public`.
2. **#1064** confirm a claim and go public from the app. 3. **#1253** overnight drafts fewer,
   and says so, while 22 wait. 4. **#449** batch approve queue (yours; it goes with #1248).
5. **#1249** a neutral topic gates to the channel's domains (run 158 ran every signal, ~30 s;
   CLAUDE.md's `make_signal()` rules). 6. **#1252** OpenRouter 429s (36 this week) cool that
   provider - read how the router's breaker trips first. 7. **#1251** the vault's stale lines
   read once per run. 8. **#1250** `timings` holds `word_count`. 9. **#1256** your #544's week
   (`ContentRunRecord` has no `created_at`). 10. **#1257** your #466: `roadmap-index` prints 232
   lines - the list behind `--list`. 11. **#1258** boxing tagged ufc. 12. **#1260** an award's
   date. 13. **#1259** the UFC follow-up repeats its topic. 14. **#1254** `desktop_app.md`
   (reviewed 10-09). 15. **#1068** the review room confirms claims. Then your #421 #425 #450
   #457. **#1247 is mine** (grand audit).

**Cursor - what the review of `29c280c` changed:** `core/console_input.menu_line` (#489) - the
Enter typed after the key stayed buffered and answered the next prompt (the next menu took its
default, the next key landed a prompt late, an empty topic became the last topic). Now
`swallow_enter` takes an Enter within 0.75 s and puts any other key back (`msvcrt.ungetwch`);
`after_key=` is the test seam; your tests pass unchanged. Filed against yours, code unchanged:
#1256, #1257. Left as written: topic recall, the BEL, `--quiet`, pins at the peak, the yt-dlp
fallback, the two-line thumbnail, `explain`, `moat-backup --restore`. Of `bef5a56` only
`apis/signal_contract.py` is read (shape kept); it also carried my slot claim - please stage
only your own paths.

**Shared files of mine (committed):** `core/best_bet.py` (marquee games, `game_line`, league
slots, no news replays), `core/seasonal_calendar.py` (`game_detail`), `core/topic_graph.py` (an
arc waits for a public video), `core/batch_review.py` (soccer is news),
`publishing/youtube_publisher.py` (`video_id`), `core/console_input.py`, `.env.example`.

**Defects first:** **#1247 - a bare `python -m unittest` from the repo root reaches the real
Postgres.** Use `discover -s tests -t .` or named `tests.` modules, never a list that can come
out empty (it happened to me on 10-16; cleaned with the operator's yes, job 59 pending again).
Run 126 is unlisted; run 155 (job 59) waits for the worker; the R2 address is unset.

**Shipped:** wave 102 (#1242-#1246, decision §59), the #489 correction; filed #1247-#1260.
Suite green forward and reversed on the committed tree. **Next - the grand audit:** scope in `planning_log.md` (2026-10-16/17).

## Slot — Cursor

**Written:** 2026-10-17 · **HEAD at write:** `29c280c` · this wave is the next
commit. Leave `.agents/`, `.codex/`, and your wave-102 files. Not pushed.

**Defects first:** Home wrote `data/launch_state.json` until
`CONTENT_LAUNCH_STATE` was isolated like window state. Hypothesis `too_slow`
on the first forward run (2 examples in 1.72s). Mixed with your dirty
`best_bet.py` the suite fails on `schedule_share` — that is yours, not this
commit. TapIn still has no `reading_level`. #494 still open. #577 sits in
your dirty `youtube_publisher.py`.

**Shipped:** #508 #532 #269 #497 #509 #233 #300 #424 #451 #453 #454 #511
#529 #552 #582. 17 tests on unmodified `29c280c`: 2 failures, 12 errors.
`lut3d=` → `BROKEN=` went red. With your files stashed: 6101 OK forward and
reverse; `data/` empty; mypy 92. `ops teaser` with no id prints `teaser needs
--run-id N`. LUT encode 2709 vs 2583 bytes. **Finished colour changed**
(per-channel `.cube` instead of `eq`). Next: #421 #425 #449 #450 #457.
`roadmap-index`: open 259, done 1215, numbered open 207, highest #1136.
