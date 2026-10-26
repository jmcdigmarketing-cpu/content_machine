# Cloud brief — wave 132: more interesting topics, a shorter Week in Review

> **Class:** plan · **Status:** living · **Reviewed:** 2026-10-25

The operator, Sun 2026-10-25 night: *"week in review is far too long, video topics have been rough
and uninteresting as of late. plan plan plan and push to main, might be going cloud tm"* - then, on
the compilation: *"the week in review should cover all topics of this channel as well as a deeper
dive on the top 3. maybe 5-8 mins long not 11."* This page is that wave, for a Claude cloud session
to build from origin's `main` (tomorrow's default), the way wave 128's brief was written
([cloud_brief_2026-10.md](cloud_brief_2026-10.md)).

Every item was measured on the operator's PC the same night; the numbers and strings are below
because **the cloud has none of the PC's data** - no `data/`, no `output/`, no database, no keys.
Each item is a numbered line in [backlog.md](backlog.md) under "Found planning wave 132"; the
operator's four answers are [decision 81](decisions_2026-10.md).

## Start here - the prompt to paste into the cloud session

```text
You are Claude Code in a cloud session on content_machine. Today's default is wave 132.
1. git pull. Read docs/handoff.md first (both slots), then docs/cloud_brief_wave132.md in full:
   it is the order, the files, the test data and the definition of done. Each item's backlog line
   in docs/backlog.md ("Found planning wave 132") is its source; decision 81 is the operator's.
2. Work the wave with the next-five skill (.claude/skills/next-five/SKILL.md) and tdd: every new
   test fails on the unmodified code first; say how many did in the commit. New tests go in
   tests/test_wave132.py.
3. You have no data/, output/, database or keys. Build and test from the brief's fixtures only.
   Leave the brief's LOCAL checks for the PC session and list them in your handoff slot.
4. Done: ruff check . ; ruff format --check . ; python scripts/mypy_ratchet.py (92 or fewer) ;
   python -m unittest discover -s tests -t . -v ; python -m scripts.ops test --order reverse.
5. Commit to main with your session's Co-Authored-By trailer, push, read CI (gh run list).
   Then the docs in the skill's order, your docs/handoff.md slot last.
Nothing outward: no uploads, schedules, playlists, claim confirmations, sign-ins.
```

## Ground rules for this wave

- **Defects first** - items 1-6 are what tonight's runs exposed; 7-10 are decision 81.
- Before editing a file: `python -m scripts.ops regressions <file>` lists the old fixes guarding it.
  A defect gets a case in `tests/regression_corpus.json` - **append in place, never re-serialize the
  file**; a case's `item` must exist in backlog.md. Expectation keys: `equals`, `contains`,
  `not_contains`, `includes_all`, `excludes_any`, `truthy`, `falsy`; `select` picks an index,
  `pluck` a key from each item of a list result (`core/regression_corpus.py`).
- Do not touch `core/cost_meter.py`, `apis/apify_client.py`, the quota state or `data/`. Signals keep
  `make_signal()`'s shape. Topic words come from `apis/topic_tokens` - never a private stopword list.
- Tests: `unittest.TestCase`, no network, no writes to `data/` or `output/`. The suite's env guards
  live in `tests/__init__.py`; a new env switch gets its suite value there and a line in
  `.env.example` (CRLF - `test_wave11` checks every key the code reads is documented).
- The PC's overnight run imports the PC's own checkout, not origin - pushing cannot affect it.

## Measured on the PC (2026-10-25) - why this wave

Organic views of every public TapIn Short, best and worst:

| organic views | stayed | title (run) |
|---:|---:|---|
| 968 | 57% | Cyclops Joins Marvel Rivals: What This Means for the Game's Future (6) |
| 631 | 64% | Ilia Topuria's Rise: What UFC Freedom 250 Means for His Reign (5) |
| 411 | 18% | Ben Affleck Gets Destroyed by 12-Year-Olds in Fortnite, Then Argues Back (126) |
| 356 | 11% | 2027 NBA Finals & Award Predictions: Wembanyama at +200 for MVP (133) |
| 325 | 60% | Modern Warfare 4 campaign praised by Steam players as return to form (170) |
| 305 | 26% | Fans react to GTA 6 launch trailer with hype and cautious optimism (154) |
| 264 | 50% | Dana White's Post-Fight Reaction to Mike Malott's UFC Edmonton Knockout (168) |
| 24 | 17% | Chargers' Pass Defense vs Chiefs' Offense: Key Preview for Oct 18 (165) |
| 11 | 18% | Star Wars Zero Company's Progression Systems Changed to Make New Campaigns More Engaging (161) |
| 2 | 50% | Pokemon's Snorlax and Bewear body pillows designed by sleep therapist signal positive outlook (158) |
| 0 | - | Breaking down Real Madrid's set-piece adjustments that won El Clasico (195) |

- Game previews: 11 public, median 48 organic views; stories: 53, median 63.
- The operator's `review-week` ratings (1-5) agree: 1 for the small news (Pokémon pillows,
  Pacheco, Xbox Game Pass) and the stats preview (Washington-49ers); 5 for the Chiefs-Seahawks
  Sunday Night Football picks; 4 for Jalen Hurts' season-ending news and the GTA 6 trailer.
- **The angles turn a big story small.** For a headline the default frames are
  `primary_storyline, underrated_angle, what_to_watch, impact_analysis, long_term_outlook`
  (`apis/topic_variants.py`, the `else:` branch near line 494), and `core/angle_ranker` weighs
  distinctness 0.40, seed fidelity 0.35, specificity 0.25 - numbers and names. Recent picks:
  "How Cincinnati's tempo keeps Baltimore's young QB off balance" (193), "Embiid's 28.5% Usage Rate
  vs Giannis' 31.2%" (188), "Makhachev's praise highlights mutual respect between teammates" (192),
  "How Evloev's grappling tested Volkanovski's defense" (194, the title fight's result).

## The wave, in build order

### 1. #1587 - a hook swap never strands a fragment

Tonight, two of five scripts read aloud a broken join:

- run 196: `Kansas City fell to 5-1 after a 20-3 loss, and Denver will capitalize on that vulnerable offensive line. for the first time in his *career*. Seattle held Kansas City to three points.`
- run 187: `Jackson scored twice and ended Man City's perfect start, and City's defence will pay for it. and Manchester City's perfect start is gone. The same afternoon, Arsenal beat Everton 2-0 ...`

**Cause.** The scripts use "..." as a spoken pause. `core/hook_score.extract_hook` takes the first
sentence through `core/operator_facts.sentences`, which ends a sentence at "...". Measured on the
PC:

```text
extract_hook("Patrick Mahomes didn't reach the red zone... for the first time in his *career*. Seattle held Kansas City to three points.")
  -> "Patrick Mahomes didn't reach the red zone..."
extract_hook("Jackson scored twice... and Manchester City's perfect start is gone. The same afternoon, Arsenal beat Everton 2-0.")
  -> "Jackson scored twice..."
sentences("Wait... What happened next? He won.") -> ['Wait...', 'What happened next?', 'He won.']
```

`core/content_engine._hook_variants` then replaces only that part (`rest = script[len(current.hook):]`)
and the rest of the old sentence is left behind, starting in lowercase.

**Fix.**
- "..." followed by a lowercase word is not a sentence end, in the hook's sentence reading. Check
  whether `operator_facts.sentences`' other callers want the same rule; "Wait... What happened next?"
  stays two.
- `_hook_variants` refuses a swap whose remaining text starts with a lowercase letter, as a guard.
- The sibling check: `core/script_craft.script_check` names a sentence that starts in lowercase after
  a full stop ("a sentence starts mid-thought"), and overnight's `unattended_block_reason` holds on it.

**Done when:** both extract_hook cases return the whole first sentence; a test swaps a hook into
run 196's original opener and gets no lowercase sentence start; the script check flags run 187's
final text. Corpus cases on `core.hook_score:extract_hook`.

### 2. #1588 - machine text is never read as the operator's ask

`core/facts/event_dates.preview_brief` (called by `core/batch_generation.draft_brief`, used by
overnight and `main.py`) writes:

```text
This game has not been played yet - it is on Oct 25. Write a preview: the matchup, who is in form or hurt, what to watch and what is at stake. Never describe plays, a score or a result as if the game happened.
```

`core/angle_intent`'s explainer cues include `"what is "` and `"what to "`, and discovery reads the
intent from topic + brief (`core/pipeline.py` ~line 680, `resolve_intent(topic, brief)`;
`apis/topic_variants.py` ~line 431 `read_intent(topic, brief)`). Over runs 140-197: 27 drafts read
`default`, **11 `explainer` on the cue "what is"** (every game preview - 181, 183, 188, 193 ...),
3 `comparison` on "vs"/"vs." (194: a headline's "Volkanovski vs. Evloev"), 1 `reaction` (192: a
headline's "classy reaction"). Those are headline words and the machine's own brief, not the
operator asking.

**Fix.** An explicit intent travels with a machine-made draft: `pipeline.run_discovery` and
`generate_variants` accept `intent=`; `generate_draft` passes `"preview"` for a coming game (call-led
lenses: the call, why, what decides it, who is in form, the stakes) and `"news"` (item 9) for a
headline. Cues are read only from words the operator typed. An own idea (`own_idea=True`) keeps
today's read.

**Done when:** the brief above, read as a preview's brief, yields intent `preview` - not
`explainer`; a headline containing "vs." yields `news`; an operator's typed "what is the Steam
Machine" still yields `explainer`. Corpus case.

### 3. #1589 - the description's sources are what backed a claim

Run 196 (Seahawks 20, Chiefs 3, Week 7) published with these "Sources:" - all Week 6, Broncos at
Seahawks:

```text
https://www.denverbroncos.com/news/denver-broncos-vs-seattle-seahawks-how-to-watch-listen-and-live-stream-the-broncos-week-6-game
https://sports.yahoo.com/articles/seahawks-rule-3-players-week-222452387.html
https://www.seahawks.com/news/week-6-injury-report-seahawks-at-broncos
https://www.si.com/nfl/seahawks/onsi/final-seahawks-broncos-injury-report-clarifies-situation-both-sides
```

The vault scan had attached the four lines as "confident" on "Seahawks" alone (bullet entity +0.30,
bullet cosine +0.20, anchor +0.12), and `core/description_extras.collect_source_urls` lists the URLs
of every key fact. The claim check backed all 12 of the script's claims from web results and the
ESPN signal - none from these four.

**Fix.**
- `collect_source_urls` lists a key fact's URL only when that fact backed a claim in the run's claim
  check (the verification already pairs each claim with its backing line).
- `core/vault/relevance.score_vault_fact`: when the topic names a game (two teams of one league), a
  vault line that names one of them and a third team (here "Broncos") is about another game -
  uncertain at best, never auto-attached as confident.

**Done when:** the four lines above are not confident for the topic "Sunday Night Football: Jaxon
Smith-Njigba, Seahawks defense dominate Chiefs, win 20-3"; a key fact that backed no claim leaves
no URL in the block. Corpus case on the vault rule.

### 4. #1590 - donation lines are page boilerplate

Auto-research kept these as facts on run 195 (El Clasico):

```text
We hope you found this article worthwhile. Before you close this tab, please consider supporting The Press and the future of independent community journalism.
Our commitment is to fund independent journalism that serves the public interest.Humanity, curiosity and honesty guide us, and our work is rooted in solidarity
```

`core/link_facts._JUNK_MARKERS` has "subscribe", "newsletter", "sign up" but nothing for a donation
ask. Add markers such as "consider supporting", "independent journalism", "before you close this
tab", "support our journalism", "become a member", "donate".

**Done when:** `core.link_facts:is_page_boilerplate` is truthy for both lines and falsy for "Kylian
Mbappe scored his 100th goal for Real Madrid in a 2-1 win at Barcelona on Sunday". Corpus cases.

### 5. #1591 - a title the facts do not back is retried once

Run 195's angle was "Breaking down the set-piece adjustments that won Real Madrid the El Clasico";
the claim check marked "Mourinho's set-piece tweaks won the Clasico." unsupported and the title
check said `title claim not backed by the facts: Real Madrid's El Clasico win came via set-piece
adjustments.` The title shipped anyway: "Breaking down Real Madrid's set-piece adjustments that won
El Clasico under Mourinho" - its own script led with Mbappé's 100th goal and a 2-1 comeback.

`core/content_engine.py` (~line 2620) only logs `lint_title_grounding`'s warnings; the retry right
below it (#877) covers a title that does not match its script.

**Fix.** When `lint_title_grounding` flags the title, generate once more from the script and the
backed facts, without the angle's wording; keep the retry only when its own title check is clean;
otherwise keep the first and its warning (overnight already holds a flagged title, #1150).

**Done when:** with `generate_title` and `lint_title_grounding` stubbed, a flagged first title is
replaced by a clean retry and kept when the retry is also flagged.

### 6. #1596 - the verdict comparison runs on the videos that were rated

`data/verdicts.json` holds 28 ratings for TapIn (15 entered tonight), yet `review-week` printed
"1 rated video(s) with views; rate 2 more". `core/success/verdicts._scored` ranks with
`core/success/videos.comparable_views`, which takes the first measure at least `COMPARABLE_MIN`
(8) videos have - the 7-day views, which 38 of 112 videos carry, mostly older ones; the recent rated
videos have lifetime views but no 7-day figure, so 1 of 28 lands in the ranking.

**Fix.** For the verdict report, take the first measure (7-day, then lifetime organic, then window)
under which at least `MIN_RATED` (3) rated videos rank, still one measure per ranking (#940). Say
which measure in the heading. Two old rows (10-08) carry log text as their title - display only;
leave the data alone, note it under LOCAL.

**Done when:** fixture: 30 videos with lifetime views, 10 of them with 7-day views, ratings on 6
videos of which 1 has a 7-day value -> the report ranks on lifetime views and counts 6 rated.

### 7. #1592 - Week in Review: every topic, then a deep dive on the top 3, 5-8 minutes (decision 81)

`video/week_compile.plan_week` stitches every public Short of the week whole. This week it would be
11 Shorts, 13:13; the one compilation so far (run 172) has 1 view.

**The new shape.**
1. **The rundown** - every Short of the week except the top 3, in publish order: its opening, cut at
   a sentence end. A chapter each, titled with the Short's title.
2. **The deep dives** - the week's top 3 by organic views (`views`, already on each item), whole,
   counted down #3, #2, #1; chapters "Deep dive: <title>".

**Sizing.** Target 5-8 minutes (300-480 s):
- clip = clamp((480 - deep-dive seconds) / rundown count, 12, 25) seconds, then moved to the end of
  the sentence nearest that time;
- under 300 s in total, clips grow (up to the whole Short);
- still over 480 s at 12 s a clip, the lowest-viewed rundown items drop;
- `MIN_SHORTS` (5) still decides whether there is a compilation at all.

**The cut.** A render's word timings are beside its audio: `<run.mp3_path>.words.json`, a list of
`{"word", "start", "end"}` relative to the audio. The Short's video starts its voice at the item's
`offset` (already computed - `hook_offset`). Cut at `offset + end` of the last word of the sentence
nearest the target (a word ending in `.`, `!` or `?`). No sidecar: cut at the target. Keep the
cut ≥ 10 s - YouTube's chapters need 10 s each.

**ffmpeg.** `segment_argv(src, dst, offset=...)` gains a duration (`-t`); `_render` passes it for
rundown clips; deep dives stay whole. The description's chapters follow the new order; the title
still names the most-viewed subjects (`compilation_title`).

**Fixture - this week's Shorts, in publish order (title, organic views, seconds after the offset):**

```text
Modern Warfare 4 campaign praised by Steam players as return to form                      325  65.3
Dana White's Post-Fight Reaction to Mike Malott's UFC Edmonton Knockout                   264  78.9
Washington vs 49ers preview: San Francisco's 5-0 start faces test                          48  72.6
Pokemon's Snorlax and Bewear body pillows designed by sleep therapist signal positive...    2  72.4
Larissa Pacheco's UFC snub leaves fighter scrambling for new opportunities                 16  75.3
Jalen Hurts out for season with blood clots, Eagles' playoff hopes in jeopardy             63  72.1
Fans react to GTA 6 launch trailer with hype and cautious optimism                        305  68.7
Star Wars Zero Company's Progression Systems Changed to Make New Campaigns More Engaging   11  74.6
Coach Conversation: Volkanovski vs Evloev Preview | MMA Analysis                           29  78.1
Picks gone wrong: Oct 19 board under fire after 4 of 5 misses                              14  70.7
Xbox Game Pass subscribers react to Final Fantasy 7 Remake addition and upcoming games      7  64.1
```

Deep dives: Dana White (78.9), GTA 6 (68.7), Modern Warfare 4 (65.3) = 212.9 s. Rundown: the other
8 at min(25, (480 - 212.9) / 8) = 25 s each = 200 s. Total ≈ 413 s (6:53). Test `plan_week` with
`week_shorts` and `_duration` patched; a words-sidecar fixture for the sentence cut.

**Done when:** the plan above comes out (order, clip lengths within ±3 s of the sentence cut, total
between 300 and 480 s, chapters ≥ 10 s each); a week of 5 Shorts grows its clips; a week of 25 drops
the lowest-viewed rundown items. LOCAL: the PC's dry run `py -m scripts.ops week-compile --channel
tapin`.

### 8. #1593 - overnight drafts at most one preview a night, marquee only (decision 81)

`core/batch_generation.collect_topics` interleaves the menu's ideas and previews (decision 66: "an
idea, then a preview, in turn") and overnight drafts 3. `core/best_bet.preview_options` fills its
"marquee" kind from `suggested_games`, whose `marquee_note` accepts a national broadcast
(`_NATIONAL_TV`), a league note (London, a holiday game) **or** "a team you made videos about" -
which is how a 1 PM CBS Bengals-Ravens game (run 193) became a preview.

**Fix.**
- `preview_options` tags each preview with its kind; for marquee games, also why
  (`national` / `league` / `team`).
- `collect_topics` takes the ideas first plus **at most one** preview, and only one of these: a
  national broadcast or a league note; or a numbered UFC card (`UFC 3##`, not "UFC Fight Night").
- A team-you-covered game, a Fight Night, an award and the other games stay in the menu for the
  operator.
- With no qualifying preview, the slot goes to the next idea.

This answers #1586 (NFL brings 32 organic views a Short): NFL stays, prime time only.

**Fixture - tonight's previews:**

| preview | when and where | qualifies? |
|---|---|---|
| Dallas Cowboys at Philadelphia Eagles | Mon Oct 26 8:15 PM EDT, ESPN | yes - national |
| UFC Fight Night: Bonfim vs. Brady | | no |
| Ballon d'Or 2026 | | no - an award |
| UFC Fight Night: Moicano vs. Nolan | | no |
| Cincinnati Bengals at Baltimore Ravens | CBS, the team rule | no |

**Done when:** three draft slots from 5 ideas + those 5 previews give 2 ideas + Cowboys-Eagles; with
no qualifying preview, 3 ideas.

### 9. #1594 - a headline draft leads with the story and why fans care (decision 81)

The operator chose: a headline draft - overnight's and a menu pick's - leads with what happened to
the biggest name and what it means to fans. It is **not a take**: #1084's neutral-unless-asked
rule stands, and breakdown lenses stay for ideas the operator types; "M" on the angle screen
still switches modes.

**Fix.**
- A `news` intent in `core/angle_intent` (item 2 passes it), with its own frames in
  `apis/topic_variants.py` and lens line in `_LENS_EXAMPLES`. Suggested frames:
  - `the_story_itself` - what happened, with its biggest name, plainly;
  - `why_fans_care` - what it changes for that team's or game's fans;
  - `the_reaction` - what the players, coaches, community said;
  - `what_happens_next` - the next game, card, patch or date it sets up;
  - `the_stakes` - the title, playoff spot, career or franchise on the line.
- `core/angle_ranker.rank_angles` under `news`: seed fidelity counts the headline's subject and its
  event words, and outweighs specificity. A mechanics template loses a fixed penalty, like
  `_LISTICLE_LEFTOVER_PENALTY`: "How X's ... ", "Breaking down ...", "... neutralized ...",
  "... usage rate ...".
- Record the frame (already in `meta["angle_frames"]`, #1021). The weekly report adds organic views
  by frame once five videos carry one.

**Fixtures - tonight's angle lists, from the operator's runs:**

```text
headline: Sunday Night Football: Jaxon Smith-Njigba, Seahawks defense dominate Chiefs, win 20-3
  1 Jaxon Smith-Njigba's breakout game shifts Seahawks WR timeline
  2 Seahawks defense sets tone early against Chiefs offensive struggles
  3 What this win means for Seattle's playoff push moving forward
  4 Smith-Njigba's chemistry with Geno opens new dimension in passing game
  5 How Kansas City adjusts after Sunday Night Football setback
headline: Real Madrid finally show their potential under Jose Mourinho in convincing El Clasico win over Barcelona
  1 Real Madrid's defensive structure clicks under Mourinho in El Clasico statement
  2 How Real Madrid's midfield control neutralized Barcelona's pressing in El Clasico
  3 What Mourinho's tactical shift means for Real Madrid's Champions League ceiling
  4 The human toll: Real Madrid players speak on Mourinho's trust after El Clasico
  5 Breaking down the set-piece adjustments that won Real Madrid the El Clasico
```

**Done when:**
- under `news` (judge off), SNF's #2 ranks first, and El Clasico's #2 and #5 rank in the bottom two;
- the angle prompt for a `news` read carries the five frames and not `underrated_angle`;
- an own idea with no cue still reads `default`.

LOCAL: tonight's menu's four headlines through the angle step (one cheap call each).

### 10. #1595 - an overnight story needs 3+ outlets or a marquee name (decision 81)

`core/best_bet.rank_by_coverage` (#1300) already counts `outlets` (distinct sources carrying the
story in 48 h) and ranks by it, but a one-outlet story still fills a slot on a thin day - Pokémon
body pillows (2 views), Star Wars Zero Company (11), Larissa Pacheco (16).

**Fix.** In `collect_topics`, an overnight `trending` idea needs `outlets >= 3`, or to name a subject
on the channel's marquee list. Smaller stories stay in the menu for the operator. A night with too
few drafts fewer - no padding. The `series` idea ("Picks, graded") and follow-ups are not headlines
and are not gated.

**The list.** A new `config/marquee.json`, `{channel_id: [names]}`, edited by the operator, matched
the way the playlists map is (`core/playlists._matches`). Seed TapIn from its ≥100-view Shorts and its
playlist franchises:

```text
Marvel Rivals, GTA, Grand Theft Auto, Call of Duty, Modern Warfare, Fortnite, Minecraft, Roblox,
Elden Ring, Nintendo Switch, PlayStation, Xbox, Steam Machine,
Topuria, Makhachev, Jon Jones, Aspinall, Pereira, Dana White, McGregor, Volkanovski, Holloway,
Du Plessis, Dvalishvili, Chimaev,
Mahomes, Chiefs, Cowboys, Eagles, LeBron, Lakers, Wembanyama, Luka Doncic, Giannis, Curry
```

**Fixture - tonight's ideas and their outlets:**

| idea | outlets | passes? |
|---|---:|---|
| Justin Gaethje gets told Alexander Volkanovski's fight IQ would be 'too much' for him after UFC 333 | 4 | yes |
| Call Of Duty: Modern Warfare 4's First DLC Is Out Now, Honors A Real Soldier Who Sustained Gruesome Injuries | 5 | yes |
| Luka Doncic Scores 52 In Win At Jazz | 2 | yes - a marquee name |
| Sunday Night Football: Jaxon Smith-Njigba, Seahawks defense dominate Chiefs, win 20-3 | 4 | yes |
| Pokemon's Snorlax and Bewear body pillows designed by sleep therapist signal positive outlook | 1 | no |

**Done when:** that table holds as a test; `config/marquee.json` is documented in `config/` with the
other maps; `ops status`' Tonight line or overnight's line says how many stories the gate held back.

## LOCAL checks - for the PC session, not the cloud

- `py -m scripts.ops all`'s **feeds** step exited 1 on 10-25 - read why.
- Two TapIn rows in `data/verdicts.json` (q6_QBAUrtiQ, CGFtzpiA1so, 10-08) carry log lines as their
  titles - fix the stored titles with the operator's yes.
- `py -m scripts.ops week-compile --channel tapin` (dry run) on the new shape; then Monday's real one.
- Tonight's menu through the gate and the `news` frames (items 9-10), and one overnight night's
  drafts.
- The verdict report after item 6 with the 28 real ratings.

## When the wave is done

The docs, in the next-five skill's order:
1. backlog ticks for #1587-#1596;
2. this page archived (`Status: archived`, `Superseded by: roadmap.md`, a line on what was built);
3. the roadmap's next five;
4. a planning-log entry;
5. the synopsis roll;
6. your `docs/handoff.md` slot last, listing the LOCAL checks above.
