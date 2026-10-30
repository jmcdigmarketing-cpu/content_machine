# TapIn — the principles

> **Class:** charter · **Status:** living · **Reviewed:** 2026-10-30

The rules TapIn holds when they cost views, money or speed. [tapin_philosophy.md](tapin_philosophy.md)
says what the channel is for. This page says what it will and will not do to get there. Each
principle has the reason for it, what it means in practice, and where the engine already enforces
it. Where nothing enforces it yet, the page says so. A principle changes only by a numbered
decision.

## P1. Truth before speed

**Why.** A sports or gaming fan forgives a late video. They do not forgive a wrong score, an
invented quote or a "confirmed" rumour, and neither does YouTube's misinformation policy.

**In practice.**
- Every number and quote in a script is grounded in a source the run read.
- A claim the checks cannot confirm waits for the operator.
- A preview never states a result.
- A mistake that went public is corrected in public, and `py -m scripts.ops corrections-open`
  lists the open ones.

**Enforced by.** The grounding and claim checks before render; held drafts; the corrections notes.

## P2. Our own pictures

**Why.** The covers looked alike because they were AI images from one prompt per genre, never
our footage ([studio_snapshot_2026-10-30.md](studio_snapshot_2026-10-30.md)). Google's ads review
flagged "insufficient original content". And a viewer who sees Barcelona's menu behind a Man City
story learns the channel does not look at its own videos.

**In practice.**
- A cover is a frame of the video's own footage, with no words (decision 85).
- No AI-generated people, no stock faces, and no picture of a real person we did not film or
  license.
- Never another game's or another team's footage behind a story: an untagged clip goes only to a
  story that names no team.
- Every clip carries its licence (`py -m scripts.ops footage-add --licence`).

**Enforced by.** The footage chooser refuses another game's folder (#955), and team tags keep a
tagged clip to its team. **Not yet:** covers from frames, and keeping untagged menus out of club
stories. Both are on [look_and_feel.md](look_and_feel.md)'s build list.

## P3. Odds are information, never an invitation

**Why.** Betting talk is the fastest way to look like an ad for a sportsbook. Google limited the
channel's Performance Max campaign for "Online gambling". "Wembanyama at +200 for MVP" kept 11% of
its viewers.

**In practice.**
- A line may explain why the market favours a fighter or a team ("favored", "the market"),
  never "will win".
- No betting call to action, no odds in a title or a cover, no sportsbook links.
- A video with betting talk is never promoted, whatever its numbers.

**Enforced by.** `core/odds_language.py`, which applies the market voice and strips betting calls
to action. **Not yet:** a title check for odds. The +200 title went out.

## P4. Gaming and sports are equals

**Why.** The operator, 2026-10-30: TapIn is both (decision 85). The fan is one person
([philosophy](tapin_philosophy.md)).

**In practice.**
- Equal identity, measured mix. Both worlds share one look, one voice and one cover rule, and
  both get their marquee nights.
- The day's ideas still follow what viewers watch: organic views per video by domain (decision
  80), at least two gaming ideas in five while gaming leads (decision 79), and one marquee preview
  a night (decision 81).
- A sport that earns few views gets fewer slots, not a lesser place in the channel's identity.

## P5. Money in before money out

**Why.** Paid reach does not count toward the bar and does not change organic reach. The Oct 26
campaigns bought about 37k views and 29 subscribers for $15.65, and none of it counts
(decision 82). The paid thumbnail images made every cover look alike (decision 85).

**In practice.**
- No paid promotion and no paid images.
- Money is spent only where the viewer hears or sees the difference (the voice) or where it saves
  the operator real time.
- Every charge goes into `py -m scripts.ops spend` the day it happens.
- A new paid tool needs a numbered decision naming its lane and the number it moves (decision 82's
  gate). Free tools come first.
- Money from outside YouTube (affiliate links, other platforms) comes before any increase in
  spending.

## P6. The viewer's time is the currency

**Why.** A viewer decides in about three seconds, and a long video is judged minute by minute.

**In practice.**
- The first second earns the next one, so no channel intro (decision 79).
- No "tap in for more" closer. End on the last word, so the Short loops (B02).
- No filler sentence.
- The Week in Review runs 5-8 minutes, not 13 (decision 81).

## P7. Say AI plainly

**Why.** The scripts and voice are machine-made with a person deciding. Viewers and platforms are
owed that, and a channel caught pretending loses both.

**In practice.**
- The disclosure line goes on every upload and crosspost.
- No made-up presenter. Nothing pretends a person is on camera who is not.

**Enforced by.** `core/description_extras.ai_disclosure_line` and `publishing/prepublish.with_disclosure`.

## P8. Credit the source

**In practice.** The outlets a script leans on are named. Footage credits go in the description
(`core/description_extras.add_footage_credits`). A quote is attributed or it is not used.

## P9. Respect fighters, players and fans

**Why.** The audience is fans of the people in the videos.

**In practice.**
- An injury, a loss or a retirement is told with care ("Jalen Hurts out for the season" is news,
  not a punchline).
- A take is a call someone can argue with, never an insult.
- No rage bait, and no title the video does not pay off.

## P10. Original or nothing

**Why.** YouTube's reused-content rule and Google's original-content review both judge whether
the work is ours.

**In practice.**
- The script, the voice, the edit and the call are ours.
- Footage is the backdrop, never the story. A clip is never reposted whole.
- A chapter Short is cut from our own long video.

## P11. The operator decides

**In practice.**
- Automation makes the operator's yes or no cheap and does not take it away.
- What goes public unanswered is narrow and named: clean renders at their slot (decision 78) and
  chapter Shorts of a public video (decision 77).
- A held draft waits.

## P12. A principle changes only by a numbered decision

**In practice.** If growth seems to need breaking P1, P2, P3 or P10, the answer is to grow another
way. Any other principle can change, but only by a numbered decision in
[decisions_2026-10.md](decisions_2026-10.md) that records the operator's words and the number that
moved them.

## What we refuse

- Buying views, subscribers or engagement, by ads or by any other means.
- Betting tips, sportsbook links, odds in titles.
- AI-generated people and stock faces on covers.
- Another team's or another game's footage behind a story.
- Titles or covers the video does not pay off.
- Reposting someone else's clip whole.
- Mocking injuries, losses or fans.
- A number we could not ground.
