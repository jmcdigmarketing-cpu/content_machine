# TapIn — the logistics plan

> **Class:** plan · **Status:** living · **Reviewed:** 2026-10-30

How the work actually runs: the money, the operator's week, the footage library, publishing, and
the machine. Why the channel exists is [tapin_philosophy.md](tapin_philosophy.md), and the rules it
holds are [tapin_principles.md](tapin_principles.md). Which change ships next is the bridge's job
([bridge_plan.md](bridge_plan.md), [bridge_calendar.md](bridge_calendar.md)). This page is the
routine the bridge runs on. The how-to for each step is [operator_guide.md](operator_guide.md).

## 1. The money, reeled back

The operator, 2026-10-30: *"I think reeling back on spent money is good given the numbers and
critique."* Decision 85 takes it the rest of the way decision 82 started.

| line | state | since | why |
|---|---|---|---|
| Paid promotion (YouTube Promote, Google Ads) | **off** | 10-27, decision 82 | buys views and subscribers that do not count toward YPP and do not change organic reach |
| AI thumbnail images (Flux, Ideogram, Recraft) | **off** | 10-30, decision 85 | they made every cover look alike, and a frame of our own footage is free |
| The voice (ElevenLabs) | kept | - | the one cost the viewer hears; about $0.20-0.40 a render |
| Drafting and checks (the LLM router) | kept, free tiers first | - | a draft is a median $0.04 |
| Signals (Apify and the free backends) | kept, inside their budgets | - | the breakers and caps in `core/cost_meter.py` stay as they are |

**What has been spent on ads.** A $10 campaign in September, a campaign stopped on Oct 8 (about $40
by the operator's count by then), and the two Oct 26 campaigns ($15.65 together). Three are in the
ledger. The Oct 8 one waits for its final numbers from Studio, and `py -m scripts.ops promotions`
reads them once entered.

**The rule for any new cost.** A numbered decision that names its lane (views, organic subscribers,
long-form hours, money, cost) and the number it moves, per decision 82's gate. Free tools come
first. Money from outside YouTube comes before spending more ([principles](tapin_principles.md) P5).

**The monthly money check** (the first Sunday of the month, about 10 minutes):

```powershell
cd C:\dev\content_machine
py -m scripts.ops spend          # every charge, the ads cap, what this month has spent
py -m scripts.ops cost-tower     # every cost lane in one view
py -m scripts.ops economics      # each video's cost against what it earned
```

Enter any charge the day it happens: `py -m scripts.ops spend add --amount N --what "..." --kind
<kind>`.

### Do now (no code; `.env` on the PC)

```powershell
notepad .env
```

- `YOUTUBE_THUMBNAIL_UPLOAD=off`: no custom thumbnail is uploaded, so YouTube shows a frame of the
  video itself. On a Short you can choose that frame in the Studio app. The key is read by
  `youtube/thumbnails.py`. It is not listed in `.env.example` yet.
- Put a `#` in front of whichever image keys are set: `BFL_API_KEY`, `FLUX_API_KEY`,
  `IDEOGRAM_API_KEY`, `RECRAFT_API_KEY`. The paid image arms are chosen by which keys exist, so
  removing the keys is what stops the spend. Pillow title cards still get made locally for $0 and
  are no longer uploaded.
- `CLIP_MEMORY=true`: the clips a video used are remembered across runs, so the next video reaches
  further into the folder. It is a partial fix until rotation is built (section 3).

## 2. The operator's week

What the machine needs from the operator, and nothing more. The aim, set in
[horizons_2027.md](horizons_2027.md), is **about 15 minutes a day** for the Shorts, plus one sitting
a week for a long-form script.

| when | what | command | about |
|---|---|---|---|
| Every morning | Read the night's drafts and finished videos; say yes or no | `py -m scripts.ops status`, `py -m scripts.ops batch-review --channel tapin`, `py -m scripts.ops shelf` | 10-15 min |
| When a preview toasts | Decide before its decide-by time, or the clean render goes out at its slot (decision 78) | the toast's own command | 1 min |
| A public preview | Pin the comment that asks for the viewer's call (decision 79); the pin is a Studio click | Studio | 1 min |
| Weekly, any evening | Rate the week's videos 1-5 | `py -m scripts.ops review-week` | 10 min |
| Sunday | Watch the Week in Review before it goes out (5-8 min, decision 81) | `py -m scripts.ops shelf` | 10 min |
| Weekly | Read growth: who stayed, organic views and subscribers by subject | `py -m scripts.ops growth` | 5 min |
| Monthly, first Sunday | The money check (section 1), the footage refresh (section 3), this page reread | - | 30 min |
| At a long-form draft | Accept or rewrite the script before it renders (decision 84) | the draft's review | 20-30 min |
| Every 7 days, until the Google app is published | Sign in again, or publish the app once and stop the lapse | `py -m scripts.ops check-youtube` prints the page | 2 min |

**What the operator never has to do:** type a metric, rename a file for the engine's sake, or
remember a past decision. If any of these keeps happening, it goes in the backlog as a defect.

## 3. The footage library

### How a clip gets used today (read on `899ff58`)

- A story picks one folder: a game, or a sport's game (`assets/local_provider.choose_footage`). Its
  clips are listed **in filename order** (`_folder_clips`).
- The fast cut takes at most **12** of them (`assets/fast_cut.pool_without_recent`, `_MAX_POOL`).
  It skips the clips used recently, and **recently** means the last 8 clips of the same process
  (`assets/clip_memory.py`), unless `CLIP_MEMORY=true` keeps them in `data/clip_memory.json`.
- A clip tagged with a team goes only to that team's story. **An untagged clip goes to any story**
  (`assets/clip_tags.clips_for_topic`). That is how FC Barcelona's squad menu ended up behind
  Kane, Real Madrid and Man City.
- A story whose subject has no folder (Valve, Xbox Game Pass) gets a **mix** of owned gameplay from
  any game, as the operator chose on 2026-10-10 over stock.

**So, until rotation is built** ([look_and_feel.md](look_and_feel.md), L3):

- A folder's first 12 files by name are the ones that get used. With more than 12, rename the ones
  you want seen so they sort first, or keep about 12 per folder and swap them monthly.
- Turn on `CLIP_MEMORY=true` (section 1).

### What to submit

| | |
|---|---|
| **Per folder** | 12 or more clips. The fast cut needs at least 3 and takes up to 12 per video |
| **Length** | 30 s to a few minutes each. A long file is cut into 30-second windows, so one 20-minute recording can carry a whole Short |
| **Picture** | 1080p or better, gameplay or play, **action, not menus**. A menu or loading screen makes a dead frame and a bad cover |
| **The bottom band** | Fine to leave in; the bottom 18% is cropped away (`BACKGROUND_CROP_BOTTOM`) |
| **Teams and clubs** | Tag every clip that shows a team: `py -m scripts.ops footage-tag --path <clip> --team "<team>" --apply` |
| **Import** | `py -m scripts.ops footage-add --path <file or folder> --game "<game>" --licence "<terms>" --apply` (dry run without `--apply`) |
| **Gaps** | `py -m scripts.ops footage-gaps` is the shopping list: the recent videos whose topic had no folder and fell to stock, a plain background or a mix of other games. `py -m scripts.ops footage` shows the clips each playlist has |

### Priorities, from the Oct 30 snapshot

1. **Soccer: club-tagged clips** for the clubs the channel covers (Real Madrid, Barcelona,
   Manchester City, Bayern, and whoever the week's stories name). Until a club has tagged clips,
   its stories get untagged action clips only, never another club's menu (L5).
2. **GTA 6 from launch day (Nov 19): your own gameplay.** Before launch, trailer and press footage
   under its terms (B11.11). After launch, fresh captures every few days of the window.
3. **Platform news: screen captures of the platform itself.** The Steam store and library, the
   Xbox and PlayStation dashboards, so a Valve story shows Steam and not a shooter (L6).
4. **Refresh monthly.** Each active folder gets a few new clips on the first Sunday, and the most
   used ones retire (L4 will say which).

## 4. Publishing

- **Cadence.** Set by decisions 81, 83 and 84 and laid out week by week in
  [bridge_calendar.md](bridge_calendar.md):
  - Shorts from the overnight drafts;
  - one marquee preview a night;
  - the GTA 6 countdown (10-29 to 11-18);
  - the three GTA 6 long videos (11-06, 11-12, 11-20);
  - the Week in Review on Sunday.
- **Launch week (Nov 16-22)** can be 5-6 drafts a night. Plan the mornings of Nov 17-21 for about
  30 minutes each.
- **Nothing is promoted.** A video that does well organically is a topic to follow, not a video to
  boost.
- **Crossposts** (Facebook Reels, TikTok) follow wave 136's brief
  ([cloud_brief_wave136.md](cloud_brief_wave136.md)), with the same disclosure and the same cover
  rule.

## 5. The machine

- **The PC** runs the overnight task at 5:00 AM. It must be on and awake: the wake works (S07), and
  a crash leaves a beat that `py -m scripts.ops status` reads (#1468).
- **The sign-in.** While the Google consent screen is in Testing, a sign-in lasts 7 days. Publishing
  the app (the bridge's "Yours" list) ends the weekly chore.
- **Quota.** YouTube's daily units cover uploads, captions, playlists and comments. The reliability
  dashboard is `py -m scripts.ops reliability`.
- **Cloud sessions** have no `data/`. They build from a brief that carries its own fixtures (the
  `cloud_brief_*.md` pages), and anything they need from the PC is written into the brief first.
- **Two agents, one repo.** Read [handoff.md](handoff.md) first, and record a decision before
  building on it.

## 6. Checkpoints for this page

At each bridge checkpoint (Dec 1, Jan 5, Jan 31) reread this page against what actually happened:
- Did the morning stay near 15 minutes?
- Did any cost creep back in?
- Which footage folders went stale?

Correct the page with the date, and record the reason in the planning log.
