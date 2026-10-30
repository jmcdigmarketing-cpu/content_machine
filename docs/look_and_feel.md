# TapIn — the look and feel

> **Class:** plan · **Status:** living · **Reviewed:** 2026-10-30

What a TapIn video looks and sounds like, why it looked the way it did on 2026-10-30, and the
build list that gets it there. It starts from the operator's words:

> "i dont like how each video has the same thumbnail when i submitted multiple clips for each."

and their answer when asked what a cover should be: **"Best frame, no words"** (decision 85). The
evidence is [studio_snapshot_2026-10-30.md](studio_snapshot_2026-10-30.md). The principles behind
it are [tapin_principles.md](tapin_principles.md) P2 (our own pictures) and P6 (the viewer's time).
No code changes with this page. The build list (L1-L10) is for a later wave.

## What the operator saw

- **Covers that look alike.** The custom thumbnails are an AI-made young man beside the title, on
  a coloured gradient. The Seahawks and Modern Warfare 4 rows show the same kind of picture.
- **Different videos, one frame.**
  - Two GTA 6 Shorts (character switching, economy design) open on the same dark car.
  - Three soccer Shorts (Kane, Real Madrid, Man City) sit on the same FC Barcelona squad menu.
- **Footage that is not the story.** A cartoon shooter behind Valve's Steam AI story, Minecraft
  behind Xbox Game Pass, a stock desk shot behind Star Wars Zero Company.

## Why it looks like this

Read on `899ff58`, without running anything.

1. **The covers come from a prompt, not from the footage.** `assets/flux_thumbnail._build_flux_prompt`
   builds one image prompt per genre:
   - "video game scene, neon gaming aesthetic, action screenshot style" for anything with "game",
     "gta", "cod" or "marvel";
   - "MMA octagon, fight night energy, intense sports portrait" for fights;
   - "bold editorial photo" for the rest.

   Every GTA story gets the same request, so every GTA cover looks alike. `generate_dual_thumbnails`
   picks a paid image provider whenever its API key is present, and the second arm
   ("face_forward") asks for a subject-led picture. That is the face.
2. **The footage comes from a short, fixed list.**
   - A folder's clips are listed in filename order (`assets/local_provider._folder_clips`), and the
     fast cut takes at most 12 (`assets/fast_cut.pool_without_recent`, `_MAX_POOL`).
   - "Recently used" covers only the last 8 clips of the same process unless `CLIP_MEMORY=true`
     (`assets/clip_memory.py`), and it is off by default.
   - So videos rendered in different runs draw from the same first files, and a folder's files past
     the twelfth are likely never seen. Count them on the PC to confirm.
3. **An untagged clip goes to any team.** `assets/clip_tags.clips_for_topic` uses the clips tagged
   with the story's team, else the untagged ones. A Barcelona menu with no tag is fair game for
   any club.
4. **A subject with no folder gets a mix.** Valve or Xbox Game Pass name no owned game, so the
   story cuts owned gameplay from other games (the operator's 2026-10-10 choice over stock B-roll).
   That avoids stock footage, but the pictures are unrelated to the story.
5. **The Studio tile is a frame of the video.** For a Short, YouTube shows a frame, captions and
   all. Two videos whose first shots come from the same few clips can show the same tile.

## The look, decided and proposed

**Decided** means the operator chose it (a decision number). **Proposed** means this page suggests
it and the operator confirms or changes it.

### The cover (decided, decision 85)

- **A frame of the video's own footage, with no words.** Any video, Short or long.
- **Which frame:**
  - taken from the source shots **before** the captions are burned in, so it is clean;
  - sharp, not motion-blurred, and bright enough (the fast cut already redraws dark shots under
    `_MIN_LUMA`);
  - with the subject in it: a car, a fighter, a player or a character, never a menu or a loading
    screen;
  - **never a frame another video used.**
- **Until it is built:** `YOUTUBE_THUMBNAIL_UPLOAD=off` ([logistics_plan.md](logistics_plan.md)
  section 1). YouTube shows its own frame of the video, captions included, and on a Short the
  operator can choose the frame in the Studio app. That already beats a made-up face.
- **Long-form:** decision 84's covers from our own frames in GTA 6's colours stand. Whether a long
  video's cover carries words is a test, not a default. #1731's "face and three words" loses its
  face (no AI people, P2), and its three words are tested against none.

### The footage (proposed)

- **Every clip in the folder is used before any clip repeats.** Least recently used across runs,
  remembered on disk, with no cap by filename.
- **Matched to the story:**
  - a team's story uses that team's tagged clips;
  - an untagged clip goes only to a story that names no team;
  - a menu or UI clip never backs a club's story.
- **Platform news shows the platform.** Steam, Xbox and PlayStation screen captures, not another
  game's gameplay.
- **Fresh.** A clip used in many videos in a month moves to the back, and each active folder gets
  new clips on the first Sunday of the month.

### The first second (proposed, with B02)

- **The cover and the first frame agree.** The Short opens on the shot the cover was taken from,
  so the feed, the Studio tile and the cover tell one story.
- The subject is on screen and in the first three words (B02).

### Pace, captions, ending (decided earlier, kept)

- **Cuts.** 3-8 seconds, irregular, landing on phrase ends. The operator reversed a steady rhythm
  on 09-19.
- **No channel intro** (decision 79: 21% stayed with it, 44% without).
- **Captions** show the script's numbers, not the voice's words (wave 131). The per-word highlight
  stays.
- **The ending.** End on the last word, not on a dark still, so a Short loops (B02.1). No "tap in
  for more".

### One look for both worlds (proposed, decision 85's "equally")

- **One caption accent colour for gaming and sports alike.** On 10-30 the highlight varied: red on
  most tiles, yellow on some GTA ones. The operator picks the colour, and it becomes the end card's
  and long-form covers' accent too.
- **One voice.** The ElevenLabs voice for both worlds, kept under decision 85.
- **One cover rule.** The same frame rule for a GTA Short and a UFC Short.
- **The channel page shows both worlds.** The franchise playlists (decision 80) ordered by organic
  views per video, and a banner made from two of our own frames, one game and one sport.

### Titles (decided earlier, kept)

- The story told plainly, biggest name first (decision 81).
- No odds in a title (P3).
- A title the video pays off (P9).

## What retires

- AI images for covers: Flux, Ideogram and Recraft (decision 85). The keys come out of `.env` now,
  and the code paths go with L7.
- The generic per-genre image prompt, and the drawn figure the "face_forward" arm paints when it
  has no cutout.
- Untagged menus behind club stories (L5).

## The build list (for a later wave; no code with this page)

Each item names its lane (decision 82). None gets a backlog number until a wave takes it, so the
backlog's ceiling and `tests/test_bridge.py` stay whole. The nearest existing items are named so
nothing is built twice.

| # | what | lane | done when | near |
|---|---|---|---|---|
| L1 | **Cover from our own frame.** Candidate frames from the video's own source shots (before captions), scored for sharpness, brightness and a subject in frame; the best unused one goes up with `thumbnails.set` | views | `py -m scripts.ops thumbnail-check` shows our frame on each new upload | #1869, decision 84 |
| L2 | **No two videos share a cover.** A cover ledger keeps each cover's image hash; a near-duplicate is refused and the next frame taken | views | two GTA 6 Shorts in one week have different covers | - |
| L3 | **Every clip in rotation.** Least recently used across runs, persisted by default; the fast cut's 12 are the 12 least recently used, not the first 12 by name | views | a folder of 30 clips shows all 30 used before any third use | #1045 |
| L4 | **What each clip did.** Per folder: each clip's uses in 30 days and the clips never used; the monthly refresh reads it | cost | `py -m scripts.ops footage-ledger` (or `ops footage`) lists unused and overused clips | - |
| L5 | **No other club's menu.** A club story with no clip tagged for that club uses untagged *action* clips only, never a menu or UI clip; `py -m scripts.ops footage-gaps` names the club to record | views | the Kane, Real Madrid and Man City stories would not have drawn the Barcelona menu | #955 |
| L6 | **Platform footage.** Platform folders (Steam, Xbox, PlayStation) chosen for platform news before the mix | views | a Valve story cuts Steam, not a shooter | - |
| L7 | **The paid image arms retire.** Dual thumbnails without Flux, Ideogram or Recraft; the face_forward arm and its drawn figure go; `py -m scripts.ops pick-thumbnail` chooses between frames | cost | no image API call in a week's runs | decision 85 |
| L8 | **The first shot is the cover's shot.** A Short opens on the shot its cover came from | views | the Studio tile, the feed's first frame and the cover match | B02 |
| L9 | **Long-form covers, tested.** Decision 84's own frames; three words against none, judged on click-through and who stayed | hours | the test settles on 2+ long videos per arm | #1731, #1869 |
| L10 | **See the cover before it goes out.** The review booth shows the new cover beside the last ten, so a repeat is seen before publishing | views | `py -m scripts.ops booth` shows the strip | - |

**Order.**
- **L3 and L5 first.** They fix the footage every frame is taken from.
- **Then L1, L2 and L7 together.** The cover itself.
- **Then L8, L10, L4, L6 and L9.**
- L1 and L8 need footage worth showing, so the [logistics_plan.md](logistics_plan.md) section 3
  shopping list runs alongside.

## How this page stays true

- A **decided** line changes only by a numbered decision.
- A **proposed** line becomes decided when the operator answers, and the decision's number goes
  next to it.
- The "why it looks like this" section is dated code reading. When L1-L8 ship, it is rewritten
  with the commit they shipped in.
