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

**Written:** 2026-09-19 · **HEAD at write:** `813a826` · **Tree:** wave 22 committing, then
pushing. CI was green on `813a826` (run 35411994692).

**Defects first - two in every recent render, found by rendering a preview and looking at it:**
- **#783** karaoke captions were burned at a tenth of their size: `caption_force_style` (FontSize=18,
  sized for SRT's 288-px default) was applied to the ASS, which declares 1920 px. Run 77 is live on
  YouTube like that. An .ass burn now keeps only the skin's box/outline/shadow keys.
- **#784** `vignette=PI/4:0.280` - the second positional is x0, so the vignette centre sat at the
  left edge and blacked out the right third of every frame since 464c71b.
**Look at a frame before you trust a render change.** Tests passed through both.

**Operator ask, shipped:** #782 fast-cut backgrounds (`assets/fast_cut.py`, a shot every ~2.5 s
from the topic's game folder; default on, `BACKGROUND_FAST_CUT=false` restores the two-shot
hybrid; the suite pins it off because render tests mock one ffmpeg call). `ops preview-render
--path <mp3>` re-renders a voiced Short at $0. #601 playlists (`config/playlists.json`,
`core/playlists.py`) wait on the operator's one re-consent (`py -m youtube.oauth_setup`). #781 one
retry on a fresh client before the YouTube latch arms. Drafts 88-90 rejected on the operator's call.

Suite **3,296 -> 3,322**; mypy **139**; ruff clean; `data/` untouched by tests; mutate-gates 45/45.
Backlog **323 open / 698 done**, highest **#786**. Next: operator watches the preview, re-consents
for playlists; then **#785 · #786 · #600**.

**Cursor:** `_post_upload_extras` takes `channel_id=` now. `render_vertical_video` joins its
`output_filename` under `<audio dir>/../video` - pass a bare name, use the returned path.

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

