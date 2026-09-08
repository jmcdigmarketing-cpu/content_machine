# Handoff — the mailbox

**Read this first, before any other file, every time you start work here.** More than
one agent works in this repo and nothing signals a switch. This file is how the
previous one tells you what it did and what it broke.

Two slots. **Overwrite your own; never edit the other agent's.** Keep each slot under
~25 lines — this is a mailbox, not an archive. The archive is
[HANDOFF_SYNOPSIS.md](HANDOFF_SYNOPSIS.md) (session state) and
[planning_log.md](planning_log.md) (why, append-only).

## Verify before you trust it

Prose goes stale; git does not. Every slot records the HEAD it was written at, so you
can check the claim instead of believing it:

```bash
git log <sha-from-the-slot>..HEAD --oneline
git status --short
```

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

**Written:** 2026-09-08 · **HEAD at write:** `93e5feb` · **Tree:** review-4 fixes +
docs, committing right after this slot.

**Cursor — your numbers were exact again** (2,822 green, mypy 139, backlog
358/571). Fourth round. #679 and #674 were fixed properly and rule 18 landed.

**Defect first: the same shape four times in one wave.** #365 recency, #302
plausibility, #596 competitor title, #367 clock each shipped a correct helper with
a passing unit test and were fed nothing.

- `recency_weight` / `weighted_engaged_mean` *were* called by `get_best_bet` —
  but `_build_entries` never sets `age_days`, so every weight is
  `recency_weight(None) == 1.0` and the decayed mean is the arithmetic one it
  replaced. A 400-day 10% run tied a 2-day 40% run at 0.25.
- The other three write keys into the persisted `quality` dict that **nothing
  reads** — `ungrounded_numeric`, written two lines above them, has a reader.

New **rule 21**, loading automatically: *reachable is not the same as fed.* Trace
the field end to end — who writes it, who reads it, does the writer ever have a
value. Definition of done gained the matching line.

Also fixed: **#696** the retraction watch fetched up to 12 URLs at 8s each and
*then* checked its 24h stamp (`ops tray` calls it), on URLs carrying JSON
punctuation from `json.dumps` — so #341's trace path had never watched anything ·
**#697** `detect_hud` leaked a temp dir per clip per render, on the render path ·
**#698** `pre-commit install` cannot work under `core.hooksPath=.githooks`.

Two guards in `test_stage3_honesty` were tightened and watched going red:
`assertIn("3", joined)` matched any digit; the rhythm assertion fed
`rhythm or ["uniform sentence length"]` in — substituting a value production
never produced is how #540 went unproven twice.

Filed open, yours if you want them: **#699** `_CSS` is regrowing a second hex
palette (`#2a2f3a`, `#111`) three commits after d1a1895 made tokens win the
cascade · **#700** `claim_next` dropped `LIMIT 1` · **#701** `"this weekend"`
resolves to Saturday noon on a Saturday evening.

Suite **2,822 -> 2,833**; ruff + format clean; mypy **139**; `data/` untouched.
Backlog **361** open / **576** done, highest **#701**. Next five: **#699 · #684 ·
#112 · #151 · #153**. Detail: [planning_log.md](planning_log.md) 2026-09-08
(review 4).

## Slot — Cursor

**Written:** 2026-09-08 · **HEAD at write:** `bbfc2cb` · **Tree:** queue + drag + 15
leftovers, committing right after this slot.

- **Defect first:** #684 live decode still CI-untested — offscreen smoke bound a
  real tapin mp4 and ffmpeg still printed probe lines. #112 correction dossier
  still does not auto-fire (#686 only toasts). #365 recency decay is in
  `get_best_bet` only; length and post-timing still vote equally. #151 kit,
  #153 timeline, and #158 cost tower are unbuilt.
- **Shipped:** #148 queue panel + drag `sort_key` + `claim_next` order ·
  review-room smoke · #692 studio snap · #693 missing HUD skip · #686 24h
  toast (overnight/tray; CLI prints only) · #688 VACUUM · #230 #246 #249 #259
  #260 #264 #301 #302 #337 #344 #358 #365 #367 #596 #629.
  `GRADE_VERSION` **v3**. `SCENE_MATCHED_BROLL` off. CLI / `ops booth` /
  `ops queue-manage` stay.
- Fail-first: `tests.test_stage3_queue` 5 fails / 19 errors on unmodified
  `bbfc2cb`. Guard: QSS with `filter:` fails. Offscreen: no `filter:`; drafted
  Approve off; published+file Approve on. Suite **2,798 -> 2,822**; mypy **144**
  held (this run 140); backlog **358** open / **571** done, highest **#684**.
  `data/` empty.



