# Decisions, continued (2026-10 onward)

> **Class:** reference · **Status:** living · **Reviewed:** 2026-10-13

[decisions.md](decisions.md) reached its size ceiling at decision 39 (docs_standard.md §7).
Decisions 40 onward are here, numbered on. Same rules: code says *what*, this says *why*.
Keep entries short.

---

## 40. Overnight may render, up to a number the channel sets (2026-10-11)
**Decision:** `ops overnight` renders up to `overnight.renders` drafts (tapin: 2; default 0) and
queues each one **unlisted**. It takes only a draft nothing is flagged on: no unsupported claim,
an `ok` authenticity verdict, no conflicting facts, no ungrounded name, no weak hook, no label
in the title, still inside its freshness window. It never queues public; the operator watches
and runs `go-public`. `OVERNIGHT_RENDERS` overrides the channel and the suite pins it to 0.
**Why:** this reverses "overnight stays render-free" (wave 27). That rule kept unattended runs
from paying for a voice; it also meant 69 runs stopped at a draft, because the morning review
that was meant to render them was not being run. The operator chose it: "yes, up to 2 a night".
**Consequence:** a night can spend ElevenLabs characters for two videos with nobody watching.
The checks above are the whole guard - loosen one and say so here.

## 41. A parked channel stays set up and out of the way (2026-10-11)
**Decision:** `"parked": true` in `channels.json` takes a channel out of the picker and takes its
own feeds out of `ops doctor`; `--channel <id>` still reaches it and deleting the flag restores
it. MoneyWise is parked. **Why:** it had made no video, and its dead finance feed was failing
the doctor for the channel that is worked. Nothing is deleted, so nothing has to be rebuilt.

## 42. A clean script is three things, and what cannot be backed is cut (2026-10-11)
**Decision:** a script is clean when it keeps the operator's idea and stance on every sentence,
says nothing the facts do not back, and uses the operator's typed points. A sentence still
unsupported after the one rewrite is **cut and named** on the review screen, as long as the
script keeps its length (`CUT_UNSUPPORTED`, at most two sentences). The whole check is stored
on the run as `script_clean`, and overnight renders only a script it calls clean.
**Why:** the operator's words - "my idea and stance rule", "nothing unsupported", "my typed
thoughts, used closely", and for a sentence that cannot be backed, "cut it, tell me which".
Hedging it ("reportedly") was the alternative and was not chosen.
**Consequence:** a script can come out shorter than it was written. A cut is never silent.

## 43. The mix of niches stays (2026-10-11)
**Decision:** no lean toward UFC in what gets drafted. **Why:** the operator's call. UFC's
median was 185 seven-day views over 10 videos against gaming's 90 over 30 - a difference, on
ten videos. Asked again when either side has thirty.

## 44. The morning has its own command (2026-10-11)
**Decision:** `ops morning` is the morning review (sync, what overnight rendered, the shelf,
the drafts). `ops all` stays the weekly batch and does not call it. **Why:** the operator asked
why the morning review was not in `ops all`; it was in no batch at all. A daily step inside a
weekly batch would either run weekly or make the weekly one ask a yes per draft.

## 45. A game draft renders before its game or waits (2026-10-13)
**Decision:** a draft written from a schedule pick carries its game's start (`event_at`).
Overnight leaves it for a person once the game has started, when its title or script states a
result for a game not yet played, and when its start is not known - a topic named like a
fixture ("A at B") with no time waits too. **Why:** on 10-13 overnight rendered two game
drafts and both were wrong - run 139 called a Thunder win hours before tip-off, run 136
previewed a Texans game two days after it was played. The operator chose "render only before
the game" over never rendering them and over not drafting them. **Consequence:** a result is
read by words ("win over", "dissected") with history ("last season", a year) and what is still
to come ("will", "if", a question) left out. It misses a result said another way; the claim
check and the title check are still behind it.

## 46. Overnight stops at three finished videos waiting (2026-10-13)
**Decision:** `OVERNIGHT_SHELF_MAX` (default 3; 0 = no limit). Overnight renders nothing while
that many finished videos are not public, and stops mid-run when a render reaches it.
**Why:** four were waiting on 10-13 with no upload task installed and an expired sign-in;
decision 40 would have added two a night and spent the voice characters for each. The
operator's call. **Consequence:** rendering resumes on its own when the shelf drops - a video
goes public, or is retired.

## 47. The research brief is not evidence (2026-10-13)
**Decision:** the claim check is not shown the research brief as a fact it can cite. The brief
still frames the script. **Why:** the brief is written by a model from the same facts. When it
restated them, the checker cited the brief as the plainest line, and the rule that a brief
"backs nothing strict on its own" (#966) then called every one of those claims unsupported -
5 of 5 on a replay of run 137, with the sources two lines away. That, not thin facts, is most
of why drafts were blocked. **Consequence:** a claim only the brief carries is unsupported, as
#966 intended. When the brief is the only text there is, it is still shown and still backs
nothing strict.

## 48. One model writes the whole script (2026-10-13)
**Decision:** `SCRIPT_BODY_TIER` defaults to `premium` again: one call writes the hook and the
body. `cheap` restores the split of #374. **Why:** the operator's call, on the measurement.
From run 134 a free-tier model wrote every body - a local 8B model on runs 136-138, 136 being
the one rendered (a fact told twice, a garbled last line). A run cost about a cent before the
split and about a cent after it. **Consequence:** roughly $0.002 more per script. This
reverses a default the other agent set; the split is one setting away.

## 49. An unbacked sentence is cut even when the script ends a little short (2026-10-13)
**Decision:** the cut of #1139 may leave a script at 85% of its minimum length. The stored
check says how many words short it is, and the review line prints it. Cuts made for stance or
repetition keep the strict minimum. **Why:** run 141's one cut left 148 words against 150 and
was refused, so the draft waited with the sentence in it. The operator chose a clean script
two words short over a flagged one. **Consequence:** a video can run a few seconds under its
length preset. Never by more than 15%.

## 50. A typed idea is drafted as angle 1 and kept (2026-10-13)
**Decision:** `ops script-check --idea` writes the idea the way angle 1 does in `main.py` -
the idea's own wording, no generated angle, no experiment directive - and saves it as a draft
that `batch-review` can render. **Why:** the command had passed the first *generated* angle
and three scripts were reported to the operator as "your ideas" that were not written from
them. A proof that does not take the operator's path proves nothing about it.

## 51. Old drafts are set aside, not kept waiting (2026-10-14)
**Decision:** at the start of each overnight run a waiting draft past twice its
freshness window (2 days for news, 7 for the rest) is marked `expired` in its own record
and leaves the waiting count. Nothing is deleted; `ops batch-review --expired` lists them.
`OVERNIGHT_EXPIRE_DRAFTS=false` keeps every draft waiting. **Why:** the operator's call;
the waiting count grew every night with drafts that would never render. **Consequence:**
the first run sets aside about 20 of 35 - more than the 6 "past their window" the question
named, because a draft blocked for a claim was counted under the claim, not its age.

## 52. A scheduled game is drafted as a preview (2026-10-14)
**Decision:** the schedule stays in the overnight batch as it is (the operator's call, "keep
as is"). A schedule pick whose game is ahead is drafted from a brief that says the game has not
been played, names the day, and asks for the matchup and what to watch - never plays or a
score. The brief goes to the angles and to the script; it is not counted as the operator's
points. **Why:** 9 of 9 batch drafts since 10-11 were schedule games, and the 10-14 three came
back as recaps of games two days away; the title check held them, but each cost a run.
**Consequence:** a generated angle that still narrates the game is held by the title check, as
before. The first draft under the rule (run 152, Ravens at Browns, game on 10-18) is a preview.

## 53. The morning shows open corrections and offers the sign-in (2026-10-14)
**Decision:** `ops morning` lists each open correction note once - video, claim, page - and,
when the YouTube sign-in has ended and a person is at the console, asks whether to sign in now
(Google's page opens; the sync runs after). Both are the operator's calls. A correction is
checked only against a page that names the claim's subject, retractions included. **Why:**
32 notes sat in the vault's `_reports` folder that no screen showed, and none of them was about
its claim: 4 of 5 pairs had been read against pictures, the fifth against an article about
someone else. The sign-in had been dead two days with the fix printed each morning.
**Consequence:** the older notes are counted on the morning screen, not listed, and not
rewritten. A nameless retraction notice no longer files - it was pinned on the run's first
claim and recorded that claim as reversed.
