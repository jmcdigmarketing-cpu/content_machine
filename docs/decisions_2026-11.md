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

## 102. The fast lanes publish without waiting (2026-11-05)
**Decision:** a national final, a numbered card's finish or a marquee story on five outlets within
two hours is drafted, rendered and made public by the worker in about an hour - no review, no
slot. It passes every check an unattended render passes (the claim gate, the title check, the
second read) or it is held; a claim hold raises one toast. At most three a day (news two), never
under 1,600 YouTube units, on battery or while overnight runs. **Why:** the bridge's B03.1, B03.3
and B03.4 (decision 82), taken by the operator as the wave ("Start wave 151"): news was hours old
when it went out, previews were drafted 31 minutes before kickoff, and a result waited for the
noon slot. Countdowns already went public unattended (wave 135); decision 78's 24 hours stays for
everything else. **Consequence:** `FAST_LANE=false` stops it; `FAST_LANE_OUTLETS` sets the news bar.

## 103. The night leads with what moves now; three Shorts a day for two weeks (2026-11-06)
**Decision:** the night's first idea is, in order, a launch-week story on five outlets, an injury
to a marquee name, a story naming a numbered card or its main event in its fight week, a marquee
name's competitor breakout at five times its channel's median. The fast lane also takes a marquee
injury, a fight-week weigh-in or drama story and a marquee press-conference quote on three outlets
within the hour, counted in its news cap of two a day. A Short ends on its last word, with no end
card. From Nov 7 to Nov 20 every title gets the 6 PM slot and overnight renders three, measured
against the two weeks before; a night five ideas pass the gate drafts five. The marquee list
learns from the channel's own Shorts, beside the operator's list. **Why:** the bridge's B01.1, B01.3,
B01.16, B01.17, B02.1, B03.2, B03.7, B12.3, B12.19 and B12.21 (decision 82), taken as the operator's
"next 10" before W4's freeze. **Consequence:** no wake timers (the operator, 11-06) - the worker,
and so the fast lane, runs only while the PC is awake; a final it sleeps through is #1999. The
trial ends with its row; `UFC_FIGHT_WEEK`, `UFC_MATCHUP` and `MARQUEE_LEARN` stop the rest.

## 104. Last night's games at overnight; a Short ends on its loop line (2026-11-06)
**Decision:** overnight drafts last night's national final the fast lane did not make, and a
marquee name's 40-point night, as result Shorts written as news, each with both teams' next games
as facts. A Short ends on a line that leads back into its first and never on a sign-off; long videos
keep theirs. A hook names its subject - a game's teams or a marquee name - in its first three
words, inside the rewrite that already runs. A preview's title says its call as a call. **Why:** the
fast lane missed the TNF final while the PC slept, and the operator wants no wake timers (decision
103); the bridge's B02.2, B02.3, B02.5, B04.16 and B12.6 (decision 82), the operator's "Start wave
153"; run 249's title was found the same afternoon. **Consequence:** `LAST_NIGHT=false` stops the
morning's results.

## 105. One idea a subject a night; never four a day or two within three hours (2026-11-06)
**Decision:** a night drafts one headline idea a marquee subject - the second waits for tomorrow,
except a subject in its launch week - and holds back a headline past 36 hours that fewer than three
outlets still carry. No more than four Shorts go public a day and none within three hours of
another; a dated draft keeps its day and a preview its game. A hook is 12 words or fewer. `ops
promotions` suggests nothing while ads stay at $0. **Why:** the bridge's B01.10, B01.11, B02.10,
B03.16 and B09.6 (decision 82), the operator's "next 20"; measured 11-06: 41 of 58 first sentences
over 12 words, 13 pairs within three hours in 30 days, one day of six. **Consequence:** the weekly
report gains the what-worked note and the format and frame ranking; a Short links its series
playlist.

## 106. Every lane prints its number; a card's "who wins?" Short; crossovers lead (2026-11-06)
**Decision:** each lane of the bridge prints its number and the run of weeks its "done" asks for
under the hours lane - the median Short's first week, stayed share, organic views a day, the best
format's share, organic subscribers a week, money outside YouTube - and the scoreboard gives a Short's
all-in cost against $0.25. A numbered card gets a "who wins?" Short one to three days out, both
sides' case, ending on the honest question. A fresh gaming headline naming a known name from
outside gaming passes the gate on one outlet and leads the plain headlines. **Why:** the bridge's
B01.24-25, B02.21, B02.25, B03.22, B03.25, B04.2, B04.25, B05.25 and B07.25 (decision 82), the
second ten of the operator's "next 20". **Consequence:** a lane is done only when its run lands, so
#1621, #1646, #1721 and #1668 stay open until it does; `config/crossover.json` is the operator's;
`UFC_DEBATE=false` stops the debate.

## 107. A 1 PM draft step for tonight; a winner re-hooked; a known subject passes the gate (2026-11-06)
**Decision:** once a day from 1 PM, in the worker pass, overnight's draft step drafts up to two of
the morning's news for tonight's free slots and uploads each private with its slot's time - public
at 6 or 10 PM with nobody watching, held by the fast lane's checks. A public Short past 300 organic
views is cut once, 14-35 days on, from its second sentence under a new hook, into a free slot in the
next 24 hours, public at its slot like a chapter Short of an approved video. A one-outlet headline
about a subject fans know (100,000+ Wikipedia views in 30 days) passes the topic gate; a name that
just trended and that fans do not know yet gets "Who is ...?". A game's stills are its footage, the
matching edition wins, and another edition under a story is flagged. **Why:** the bridge's B01.9,
B02.8, B03.6, B03.20 and B04.15 (decision 82), before W4's freeze; "nothing by hand" - a draft that
waits for a decision misses tonight. **Consequence:** `MIDDAY`, `REHOOK`, `WHO_IS`, `KNOWN_SUBJECTS`
and `STILL_CLIPS` (each true by default) stop each; no new scheduled task and no wake timers - a PC
asleep from 1 to 5 PM makes nothing that day.

