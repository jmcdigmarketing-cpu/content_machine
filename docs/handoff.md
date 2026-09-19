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

**Written:** 2026-09-19 · **HEAD at write:** `acf88ed` · **Tree:** wave 23 committing, then
pushing. CI was green on `acf88ed` (run 35453421895).

**Defects first - three more found by looking at a re-rendered preview, all fixed:**
- **#789** a third of the GTA clips are night driving (luma 26-40 before the grade); 22% of preview
  frames were near-black. Shots under 45 are re-drawn from another file: 5%.
- **#790** karaoke lines wider than the frame: WrapStyle 2 never wraps, 4 words at 90 px overflow.
  Split to `karaoke_max_chars(size)`. Hidden while #783 kept captions tiny.
- **#791** the AI disclosure (bottom, MarginV 280) sat on the first caption (bottom, 260). Top now.
Still visible: top-of-frame HUD bars in some GTA shots - filed **#788**.

**Operator ask, shipped:** #785 crop, not skip - every shot drops the source frame's bottom 18%
(`BACKGROUND_CROP_BOTTOM`). #787 a long gameplay file is 30 s windows, so one 20-minute download
feeds a Short; `ops footage-add --path --game --licence [--source] --apply` imports it (muted H.264,
license.yaml). #786 narrowed: `footage` field on playlist rows (NFL->Madden 26, etc.); `ops footage`
shows the gaps. #600 `core/post_publish_check` - nightly, once per upload at 48h; `POST_PUBLISH_CHECK`
is pinned off in tests/__init__. First live pass: 24 videos, none flagged (wrote
data/post_publish_tapin.json - that is the real store, on purpose).

Suite **3,322 -> 3,351**; mypy **139**; ruff clean; mutate-gates 45/45. Backlog **322 open / 704
done**, highest **#791**. Next: operator's footage files, playlist re-consent, 05:00 drafts; #788.

**Cursor:** `candidate_clips` tries the folder name, then the playlist `footage` alias, and only
then the LLM pick - `resolve_background_query` no longer runs when a keyword matches.

## Slot — Cursor

**Written:** 2026-09-13 · **HEAD at write:** `2421e15` · **Tree:** wave 15 committing.

- **Defect first:** Wikipedia still queries `GTA` token-joins, not
  `Grand_Theft_Auto_VI` (#749). Heuristic title/script cannot catch a wrong actor
  who is named in the script (#345). The forced-overage publish test was green on
  unmodified code because nothing fed the cap yet; it guards the feeder.
- **Shipped #534 #748 #746 #747 #738.** Title keeps an angle phrase. Title/script
  check falls back to a real verdict. Wiki no longer invents `Gta`/`Goy`.
  Autocomplete 400 is skip-with-reason. Publish list reads persisted
  `tts_char_count`.
- Next five: **#739 · #730 · #345 · #543 · #732**.
- Suite **3,123 -> 3,131**; mypy **139**; ruff clean; backlog **327 open / 658 done**,
  highest **#749**.

