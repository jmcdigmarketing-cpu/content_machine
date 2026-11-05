# Decisions, continued (2026-11 onward)

> **Class:** reference · **Status:** living · **Reviewed:** 2026-11-04

[decisions_2026-10.md](decisions_2026-10.md) holds decisions 40-96 and was near its size ceiling
(675 of 800 lines). Decisions 97 onward are here, numbered on. Same rules: code says *what*, this
says *why*. Keep entries short.

---

## 97. Never a death story (2026-11-02)
**Decision:** a headline whose subject is a death is never an idea - not in the menu, not in an
overnight slot, not among a countdown's facts. A death in a title or a first sentence holds the
render, and a description sentence about a death is dropped at upload. A passing mention inside a
script is allowed. **Why:** live on 11-02 a viral fan's death led the Nov 3 GTA 6 countdown (run
226: "has *died*"), sat mid-script in that day's countdown (run 225) and had a draft of its own
(run 229, "GTA 6 Community Mourns Loss of Devoted Fan") - held only because a second read happened
to dislike its first sentence; nothing in the code matched a death. Asked, the operator chose the
stricter option, "Never draft a death story", over "never the hook or title". The redraft (run
231) then had a clean script and a description that still said the fan had died "three weeks
before launch" - so the description is covered too. **Consequence:** `authenticity.death_reason`
/ `is_death_story` at the menu, the overnight gate, the countdown's facts and `ad_limit_reason`'s
four callers; `prepublish.without_death_lines` at upload. Replayed on the stores: 1 of 226 titles,
4 of 1,790 headlines and 3 first lines match, all real deaths; no game title or sport phrase does.

## 98. The night carries the menu's gaming share; a menu is counted once; a deleted video is recorded gone (2026-11-02)
**Decision:** while gaming leads the organic views, a night's drafts - its countdowns and other
dated drafts included - carry `GAMING_FLOOR` of five gaming; a plain headline gives way to the next
gaming idea, never the series or the preview. S15 reads each distinct menu once. A video YouTube no
longer returns is recorded with privacy `gone` (the row stays; nothing is deleted). **Why:**
decision 93's three-of-five floor lived in the interactive menu; overnight's slate (the series,
one preview, then headlines past the outlet gate) offered gaming one row in three every night while
gaming earned 62% of organic views, and `menu_mix` counted each night's menu once per draft. Runs
179, 185 and 186 were deleted in Studio; the sync reported them every night and the shelf still
listed two as "held for a claim" - #1128 had left the record alone on purpose. **Consequence:** a
night with two gaming countdowns already carries the share (3 of 5); after the countdown ends a
three-draft night swaps a headline for gaming. S09 does not count a `gone` record as drift - the
operator deleting a video is not the record drifting.

## 99. A long video's cover cut from its own footage goes up in frames-only mode (2026-11-04)
**Decision:** `YOUTUBE_THUMBNAIL_UPLOAD=frames` uploads a Short's clean frame cover and a long
video's cover cut from its own footage - with its words (L9's "words" arm, a Week in Review's
subject) or none - named `_frame_long.jpg`. Nothing else goes up. **Why:** decision 85 took the AI
images off the covers; its gate was a file name, `_frame_cover.jpg`, which only a Short's cover
carries. Run 230's Week in Review cover was never set (its upload record has no `thumbnails.set`),
and from Nov 6 every long video's - and the L9 words-against-none test - would have gone out on a
frame YouTube picked. A long cover is a frame of the video itself; the words are the test.
**Consequence:** `cover_frames.LONG_SUFFIX`, `thumbnails.is_frame_cover`; a Short's cover keeps no
words.

## 100. Long videos that are not news go public at one weekly time, Sunday 7 PM (2026-11-04)
**Decision:** the Week in Review and a season's explainer go public at the weekly long slot -
Sunday 7 PM in the channel's zone (`LONG_SLOT`) - with no news window or game guard; overnight
compiles the week that morning and leaves out a Short an earlier week's video holds. Dated long
videos (the GTA rows, a card's recap, the deals) keep their own days, and the month's best keeps
the next free slot. The scripts promise the day ("every Sunday"), not the hour. **Why:** B06.6
(#1727). The three Weeks in Review went out Tuesday noon, Tuesday noon and Monday noon - whatever
slot was free - while every long draft's last line said "every Monday". YouTube's API has no
Premiere, so the slot is a scheduled publish. **Consequence:** the GTA 6 launch-week special moves
from Monday Nov 23 to Sunday Nov 22; `LONG_SLOT=off` puts the compile back on Mondays.

## 101. A long video's music bed is generated here, from sines (2026-11-05)
**Decision:** with no track of the operator's in the channel's music folder, a long render gets a
pad generated with ffmpeg - six 64 s variants, taken in turn, looped by the render and ducked under
the voice at the channel's music volume - -32 LUFS alone, about 23 dB under the voice (the
operator, hearing the first cut: "much much quieter"). A Short gets no bed unless a track is added. **Why:** no
track had ever been in `assets/music/tapin`, so no render had a bed (#1735); MusicGen meant a
multi-gigabyte download under a non-commercial licence. Asked, the operator chose "Generate one
with ffmpeg" over adding Audio Library tracks. A pad from sines is nobody else's music and costs
nothing. **Consequence:** `core/music.synth_bed`, `MUSIC_SYNTH_LONG`; a track dropped in the folder
replaces it for every render.

