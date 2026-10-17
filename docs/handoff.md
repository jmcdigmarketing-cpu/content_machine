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

**Written:** 2026-10-17 · **HEAD at write:** my audit commit on `444e2e7` (`git log -1`) ·
**Tree:** your wave 103 files are yours; I added my lines to the shared docs and the corpus in
the working tree too, so your commit keeps them. **Pushed** `54f641b` (your
`29c280c` and `bef5a56`, reviewed, with my corrections): CI's type check passed - 90 errors,
baseline 92.

**Cursor - the audit changed in your work:**
- `config/channels.json` (#497): `color_lut` is out of TapIn and MoneyWise - the 2-point files
  were nearly flat and replaced TapIn's saturation 1.18 / contrast 1.08 (the operator: keep the
  current look, decision §61). Your `RenderLutTests` now asks that the shipped channels keep
  their grade; the golden `grade.cube` case still proves the path. The field is parked in
  `test_no_profile_field_is_unset_on_every_shipped_channel` with its reason.
- `desktop/home.py` (#532): the changelog stamps once per process (Refresh emptied it), and
  `git` runs with `CREATE_NO_WINDOW`. Your `test_home_writes_isolated_launch_state...` deleted
  the operator's `data/launch_state.json` when it existed - it compares it now.
- `tests/__init__.py` refuses to load when `config.settings` came first, and sets
  `CONTENT_SUITE=1`; `storage/db.py` then opens only SQLite or `CONTENT_TEST_DATABASE_URL`.
- **mypy checks the Windows build** (`platform = "win32"`, no `types-beautifulsoup4`;
  decision §62). CI had failed on every push since 10-11. Lower `mypy_baseline.txt` only from
  a count taken with this config.
- Read and left as written in `bef5a56`: `signal_contract`, unit sanity, the booth's tags and
  captions, the licence ledger, text-variant thumbnails, latency rows, the toast sound.

**The operator, 2026-10-17:** "keep overnight renders waiting for me" (§60). Your
`watch_and_publish` keeps to it; `tests/test_grand_audit.py` holds who may call
`apply_go_public` (yours in `core/review_bind.py` is on the list). **Your wave 103 is not
reviewed yet** - I review it when it is committed; `draft_count`'s cap of 8 would stop
overnight drafting while 22 drafts wait.

**Numbers:** the audit filed #1263-#1269; please number yours from #1276.

**Defects first:** none open of mine. Suite 6128 forward and reversed.

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
