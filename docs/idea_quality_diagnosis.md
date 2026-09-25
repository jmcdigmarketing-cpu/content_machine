# Why the ideas are bad — a diagnosis

> **Class:** snapshot · **Status:** frozen · **Reviewed:** 2026-09-25

**Written:** 2026-08-30 · **HEAD:** `73671ce` · **Branch:** `consolidate/2026-08-27`

**2026-09-13, live run 76 (addendum, not a rewrite).** The operator typed a
four-question GTA 6 thesis at option 1 best-bet. All five angles scored **100.0**.
`"best "` selected `ANGLE_LIST`, so 1/2/4/5 were honourable-mention templates and
only 3 was close. Option 1 still does not set `creative_brief` (#664 was option 5
only). Editorial scores were 0.54-0.58 — Jaccard cannot rank a thesis. A Haiku or
27b swap does not fix that while the listicle table is selected; see
[planning_log.md](planning_log.md) 2026-09-13 run 76 and **#740–#745**. The Aug 30
claim that option 5 discards the idea is **stale** (#664). The claim that
composites do not rank is **still true**.

The operator asked: *"is there any particular reason as to why the video ideas have been
so terrible recently? it seems like its struggling trying to fit the 'enter your own'
ideas into the initial markup of the project being about and for hot takes."*

This traces that. Defects first. Every claim carries a citation; where the evidence
contradicts the question's premise, that is said plainly rather than smoothed over.

---

## The short answer

The mechanism the operator suspected is real, and it is worse than suspected — option 5
does not use their idea at all. It uses it as a **search string** and then discards it.

But two corrections change what the fix is:

1. **The project was never chartered as a hot-takes machine.** Nothing in
   [vision.md](vision.md), [positioning.md](positioning.md),
   [project_brief.md](project_brief.md), [strategy_2026H2.md](strategy_2026H2.md) or
   [decisions.md](decisions.md) frames it that way. `config/channels.json` does not
   either — the MoneyWise persona is literally *"calm, plain-spoken, mildly sceptical of
   hype — explains, never sells"* (`config/channels.json:109-172`). The hot-take framing
   is an **accretion**: six layers, each added for a defensible local reason, that
   compose into a machine which can only produce one shape of video. There is no
   "initial markup" to fight. There is a pile of small decisions to unpick.

2. **Underneath the framing problem is a bigger one.** The step that picks which idea to
   make is not actually picking. On two separate recorded runs all five candidate angles
   scored **identically** — 100.0 and 92.14 — so "Enter = best" returned an arbitrary
   one. That explains "the idea it gave me was terrible" more directly than any prompt
   wording does, and it is unfixed.

---

## 1. Option 5 diverges from the discovery pipeline at exactly one line

`main.py:266` hands the operator's idea to `_run_new_video_flow` — **the same function
option 1 uses**. The entire divergence is `main.py:317-319`:

```python
if seed_topic:
    # Idea intake (option 5) — user already gave the idea; skip best-bet.
    topic = seed_topic
```

Everything after that line is byte-identical for both paths: the same discovery, the
same angle generation, the same trend scoring, the same single script prompt, the same
six rewrite passes, the same gates, the same report card.

Three further losses happen at intake:

- A **one-line typed idea** gets `is_rich=False` (`core/idea_intake.py:101`), so
  `creative_brief` stays `""` and **no creative direction reaches the script prompt at
  all**. Only a multi-line paste keeps its thesis (`main.py:255-263`).
- On the **YouTube-link branch** (`main.py:238-254`) the operator is asked *"Your
  angle/idea for OUR take"* — and that answer is string-concatenated into the search
  seed. `creative_brief` is never set on this branch. The stated angle reaches the
  search engine and never reaches the writer.
- `_seed_from_title` (`core/idea_intake.py:71-77`) silently truncates the title at the
  first colon. The clause after the colon is usually the thesis.

---

## 2. Cause A — the selection step is not selecting

This is the largest cause and the least documented.

`core/pipeline.py:114-133` scores each of the five generated angles with
`apis/topic_scorer.composite_score`. But the signals it reads are the **topic's**, not
the **angle's** — five different editorial framings of the same subject return the same
signal profile, so they return the same number.

Recorded twice, independently:

> **Live-run 71** ([debugging.md](debugging.md)): *"Variant scoring produced no ranking.
> All five angles scored exactly **100.0**, so `Choose 1-5 (Enter = best)` offered a tie
> dressed as a ranking."*

> **Run 72** (`output/tapin/reports/intelligence_gta_6…json`): all five variants at
> **exactly 92.14** — including *"Vice City map size reveals Rockstar's ambitious scope
> creep problem"* and *"economy design teases a post-grind monetization revolution"*.

Candidate 323 responded to this honestly but did not fix it: `core/ui.py:587-611` now
prints *"this is a tie, not a ranking. Pick on editorial judgement"* and falls back to
pre-clamp raw scores for ordering. **The message is accurate. The selection is still
arbitrary.** When the operator presses Enter they are not receiving the best of five
angles.

And the score does not predict outcomes anyway. From the one real outcome dataset
(`output/tapin/reports/…accuracy`): *"Of 10 flagged publishes, 4 met or beat channel
average engaged-rate (27.8%) — hit rate 40%."*

| composite | topic | views | engaged |
|---|---|---|---|
| **100.0** | Fresh Revelations from Summer Game Fest 2026 | 40 | **0.168** |
| **100.0** | Overlooked Gems: The Forgotten Elements That Made COD Zombies Legendary | 26 | **0.134** |
| 86.8 | Marvel Rivals Takes the Gaming World by Storm | 23 | **0.134** |
| **68.2** | Why Darius Acuff Jr Deserves More Attention Than He's Getting | 34 | 0.240 |

The lowest-scored topic on record beat two 100.0s. Three of the four worst performers
scored 86.8–100.0. **#351 confidence intervals** in [roadmap.md](roadmap.md) is the open
item that would make this visible.

---

## 3. Cause B — six layers that force one shape

### 3.1 The angle tables contain no non-take option

`apis/topic_variants.py:138-145` — any non-gaming, non-reaction topic:

```python
angle_types = [
    "primary_storyline",
    "underrated_angle",
    "controversy",
    "impact_analysis",
    "long_term_outlook",
]
```

Gaming under 3 repeats gets `meta_or_balance_take` / `community_controversy`
(`:131-137`); over 3 it pivots to `whats_broken_needs_fixing` / `community_wishlist` /
`is_it_still_worth_playing` (`:122-129`).

**There is no explainer, story, list, tutorial, retrospective, comparison, or news table
anywhere in the file.** The prompt then mandates the frame (`:283`, `:265-266`):

> `- Describe the TAKE or focus — NOT a clickbait headline.`
>
> `— a factual read, a contrarian counter-take, a forward prediction, a human/stakes angle, an analytical breakdown`

A contrarian counter-take is one of five **compulsory** lenses. And when a franchise has
been covered three times, `freshness_block` (`:251-257`) adds:

> `Instead: focus on ANALYSIS, PREDICTION, COMMUNITY debate, or CRITIQUE.`

### 3.2 The operator's words barely reach the decision

[`core/angle_intent.py`](../core/angle_intent.py) was added 2026-08-28 in response to
run 73, and its docstring states the problem exactly:

> *"`generate_variants` chose angle types from the channel domain and a repeat counter
> and never looked at the topic string at all. A reaction video was not something the
> operator could ask for."*

The fix works — but it recognises **one** alternative intent. `_REACTION_CUES` is 22
phrases; everything else returns `ANGLE_DEFAULT` and falls into the take machinery. A
calm idea — *"the hidden cost of index fund concentration"*, *"how the offside rule
actually works"* — is structurally indistinguishable from a request for a hot take.

This is already filed: **#533 Angle intents beyond reaction** — *"explainer, tier-list,
tutorial, debunk; `core/angle_intent.py` is built for exactly this"* `[M]`
([backlog.md](backlog.md)).

### 3.3 The winner replaces the idea

`core/pipeline.py:493-501` — the selected variant becomes `result.topic`, and `:524-547`
passes it to the script prompt as `TOPIC`, while the operator's idea is demoted to
`SEED TOPIC (user/channel intent — stay on this subject)`
(`core/content_engine.py:264-268`).

The only seed protection is `anchor_preservation_penalty`, and it fires solely for 16
hardcoded franchise strings (`core/channel_context.py:12-29`: `grand theft auto, marvel
rivals, call of duty, gta vi, … ufc`). **Outside that list the penalty is 0.0 and
nothing stops a variant from drifting off the idea entirely.** It preserves the entity;
it never preserves the intent.

There is no candidate 0 for "the idea I typed" in `display_variants`
(`core/ui.py:574-611`).

### 3.4 The script prompt orders a take, unconditionally

One prompt serves both paths (`core/content_engine._build_prompts`). Load-bearing lines:

| ref | text |
|---|---|
| `content_engine.py:227` | `NO both-sidesing. Do NOT write "some argue X, while others believe Y". State what YOU think and why.` |
| `:233` | `The EDITORIAL ANGLE is the spine; facts are ammunition for it. … A viewer should walk away remembering the ARGUMENT, not a list of stats.` |
| `:258` | `Include at least one explicit STANCE beat…` |
| `:259` | `Build to a strong closing line — a hot take, implication, or open question that drives comments.` |
| `:361` | `TAKE A SIDE. Commit to one clear stance or prediction…` |

Against that, exactly one counterweight (`:228`): *"The topic is the assignment: if it
says 'recap / results', RECAP WHAT HAPPENED — do not drift into think-piece
territory."* Five orders to one.

Feeding it, `core/research_brief.py:39` defaults `recommended_format = "short_debate"`,
and the brief renders `Controversy (0-1)` and `Debate angles` into every prompt
(`:48-56`). The fallback brief hardcodes `controversy_score=0.4` (`:98`).

The MoneyWise persona sits in the same prompt as advisory context
(`core/channel_persona.py:92-96`, *"write in this channel's established voice"*). The
persona describes; the rules above command. **The commands win.**

### 3.5 For `tapin`, eight unvalidated beliefs ride ahead of everything

`core/content_engine.py:318-326` injects `playbook_block(channel_id)` from the operator's
Obsidian vault into every script prompt. `core/obsidian_facts.py:559` caps it at
`limit=8`, and selection is **file/bullet order, not relevance** (`:538-556`).

`playbook.md` opens with two "Narratives that work" sections. So the eight that survive
are 8/8 hot-take rules:

> - "Fraud" / overrated-callout narratives outperform straight recaps
> - Rankings and tier-list framings outperform highlight reactions
> - Prediction/analysis angles age better than "just happened" news framing
> - "Snubbed / disrespected" angles (rankings, pay, matchmaking) drive comments
> - Rivalry and beef framing beats neutral previews
> - "X changed everything for the division" implication hooks invite debate
> - Underdog/upset stories travel further than favorite-wins stories
> - "Is X dead?" / decline takes drive defensive engagement

And **100% of the same file's later sections are truncated away** — its "Hook rules"
(*"Open with a specific fact, number, or contradiction"*) and its "Hard rules
(anti-hallucination)" (*"Never invent a fight result, record, event date, patch
number…"*, *"Competitor video titles show what's trending, NOT what's true"*). The eight
strongest framing instructions in the tapin prompt are narrative heuristics; the file's
own discipline rules never arrive.

The file says of itself, dated 2026-06-17:

> *"These are human-authored beliefs; the Analytics Intelligence Agent will eventually
> confirm/refine them with real performance data — update when it does."*

It never did. **These are guesses being executed as doctrine.**
`playbook_block('moneywise')` returns `''`, so this failure mode is tapin-only — which
is also why tapin output skews harder to the take than MoneyWise's does.

### 3.6 The grader pays for the result, and contradicts three other components

`core/video_grade.py:35-41`:

```python
_WEIGHTS = {"hook": 0.28, "authenticity": 0.28, "grounding": 0.22, "topic": 0.12, "thumbnail": 0.10}
```

`core/authenticity.py:112-140` awards `original_insight` — 35 of 100 — on substring match
against a list that contains the literal string **`"hot take"`**, plus `"overrated"`,
`"mark my words"`, `"calling it now"`, `"bold prediction"`.

`core/hook_score.py:36-61` awards **+15** for `"nobody"`, `"secret"`, `"the truth"`,
`"nobody's talking"`, `"won't believe"`; **+10** for `"changes everything"`,
`"biggest"`, `"banned"`; and **−8** for opening as a question.

Now compare against what the rest of the system bans:

| phrase | `hook_score` / `authenticity` | elsewhere |
|---|---|---|
| `nobody's talking about` | **+15** | banned headline template, `topic_variants.py:291`; `_SLOP_PATTERN`, `title_generator.py:20` |
| `changes everything` | **+10** | `_SLOP_PATTERN`, `title_generator.py:29` |
| `hot take` | **+35 authenticity** | banned in angles, `topic_variants.py:292`; `No "My Hot Take" framing`, `title_generator.py:83` |

[`tests/test_gate_agreement.py`](../tests/test_gate_agreement.py) was written after run 74
for exactly this bug class — *"A gate that rewards what another gate forbids does not
measure anything; it launders the defect into an A grade."* But it only compares
`_INSIGHT_MARKERS` against `_FILLER_PHRASES` and one `Banned verbatim:` prompt line. It
never reads `hook_score._CURIOSITY` or either `_SLOP_PATTERNS` list. **The bug it was
written to prevent exists twice more in the same codebase.**

Net: **56% of the report card is decided by two substring lists that reward vocabulary
the rest of the system bans**, and a further 12% by the trend score of an angle the
operator did not write.

### 3.7 And it self-heals in the wrong direction

`_maybe_inject_insight` (`core/content_engine.py:564-604`, **default ON**) fires when
`core.authenticity.has_insight` is false — i.e. precisely when a script is calm and
measured — and spends an LLM call bolting on *"a clear opinion, prediction, or 'why this
matters' take"*. A well-made explainer is detected as a defect and repaired into a take.

---

## 4. Cause C — two adjacent defects the run record surfaced

### 4.1 Hedging passes for grounding

`_maybe_rewrite_unsupported_claims` restates unsupported claims as attributed speculation
and re-verifies. Traces 73 and 75 store both versions:

> run 75 pre: *"they **confirmed** no microtransactions and no generative AI at launch."*
>
> run 75 post: *"**reports claim** they confirmed no microtransactions and no generative
> AI at launch."* — claim support 0.833 → 0.917

> run 73 pre: *"Fans call it 'undercooked,' but **that's** intentional minimalism."*
>
> run 73 post: *"Fans call it 'undercooked,' but **some speculate it's** intentional
> minimalism."*

Run 58 is the pathological case — claim support **30%**, and four consecutive sentences
carrying *"Reports claim… Unconfirmed, but… supposedly… the rumor is that… reportedly…
allegedly."*

[decisions.md](decisions.md) §25 documents this and leaves it open: *"read `12/12` as 'no
bare assertions left', not 'all claims true'."* Note the loop closes on itself — the
vault playbook instructs *"Prefer 'reports suggest' over stating an unverified specific
as fact"*, so the machine is following the operator's own policy faithfully.

### 4.2 Domain misclassification drives topic drift

Run 48. The operator typed *"WAYYYYYY too early final standing projections for 2027,
award races included"*. Recorded `domain: gaming`. The script:

> *"These teams are winning now, but the cracks are showing. Early **2027 standings in
> Marvel Rivals** have some squads sitting pretty, but I'm calling fraud on at least two
> of them… the squad that was dominating with a specific **dive comp**?"*

Published title: *"These 2027 NBA Contenders Are Already Cracking"*. Claim support
**0.0**; 10 unsupported claims. [debugging.md](debugging.md) §8 records the root cause.
It is not fully fixed: `domain: gaming` is still recorded on **7** sports runs in the
dossiers (54, 58, 59, 61, 62, 63, 65 — McGregor, two World Cup matches, Rodri,
Usman/DDP, an MMA rankings piece).

---

## 5. What the run record actually shows about option 5

**The recorded grades do not show option 5 producing worse videos than option 1.**

Across 25 graded runs, inferring path from the shape of the recorded seed string:

| path | runs | mean report card |
|---|---|---|
| operator-typed seed | 48, 51, 55, 56, 58, 59, 61, 62, 63, 64, 66, 73, 74, 75 | **≈ 78.6** |
| discovered headline | 49, 52, 54, 57, 60, 65, 68, 69, 70, 71, 72 | **≈ 78.2** |

Both spreads run D52 → A94. The single highest grade on record (run 75, **A 94**) is
operator-typed; the single lowest (run 69, **D 52**) is discovered.

**This does not mean the operator is wrong.** It means the report card cannot see what
they are reacting to. The same report card:

- graded **A 91** on run 71, whose title was factually wrong — *"GTA 6 Leak Forces
  Rockstar to Subpoena…"* when the operator's own key fact said Take-Two.
  `generate_title` runs after every gate and **no check reads the title it returns**
  ([debugging.md](debugging.md));
- graded **A 87** on run 74 — 277 words against a 300-word floor, hook scoring 61, and
  authenticity **100/100** earned partly by a phrase `persona_lint` flagged in the same
  log four lines earlier;
- cited *"18 verified fact(s)"* as substance on run 71, when that corpus included three
  1990s Wolverine games and four unrelated vault bullets.

A caveat worth fixing: **`data/traces/*.json` does not record which menu option a run
came from.** The table above is inferred from typos and exclamation marks. That should be
instrumented so the question is answerable from data next time.

---

## 6. Verbatim examples, for the record

**Banned-phrase era (2026-07-07, run 34)** — every emphasised phrase is on the ban list
at `core/content_engine.py:226`:

> *"In the aftermath of UFC Freedom 250, the mixed martial arts community finds itself
> **at a crossroads**, **grappling with the fallout**… challenging **the very
> foundations** of officiating… highlight **systemic issues**… **As the dust settles**,
> **it's essential to understand** why… This lack of consensus **underscores a critical
> need** for standardized officiating guidelines."*

**Banned filler still shipping 2026-08-21 (run 42)** — `persona_lint` and the script
prompt both ban it:

> *"…brings a dazzling new look and tactical gameplay changes. **But here's the thing:**
> some players argue that these characters might disrupt the game's balance entirely."*

**No-stance hedge (run 42, close):**

> *"The community remains divided. On one hand… On the other hand… **In the end, whether
> these new characters break the game or breathe new life into it is a question that only
> time will answer.**"*

That paragraph violates `NO both-sidesing` (`:227`), the banned `only time will tell`
family (`:362`), and the ban on generic closes (`:363`) — three prompt rules in four
sentences, shipped.

**Worst grade on record (run 69, D 52)** — a 31-word opener, then invented institutional
detail:

> *"The GTA 6 leaks are a recurring nightmare for Rockstar, and the latest one has a
> leaker literally taunting the company. But here's the twist…"*
>
> *"They're the result of a persistent, decentralized network of hackers and insiders who
> exploit every weak point in Rockstar's security… often from testers or devs who leak
> snippets to prove they're in the know."*

**And the counter-example that proves the fix direction works.** Run 73 selected *"GTA 6
Community Predicts Toxic Meta Before Launch — Why They're Wrong"* from a topic the
operator typed as *"GTA 6 looks amazing!!!"*. After `angle_intent.py` landed, run 75
selected *"GTA 6 feels like it skipped the hype train entirely"* — hook **92**, report
card **A 94**, the best on record. One intent, correctly detected, moved the output more
than any prompt edit in the project's history.

---

## 7. Where the evidence lives

`data/traces/*.json` is the thinnest of three stores — no hook, no script, no grade, and
no record of which menu path produced the run. Only 73 and 75 carry script text.

| store | path | holds |
|---|---|---|
| run dossiers (36) | `%OBSIDIAN_VAULT_PATH%\tapin\_runs\*.md` | **the real corpus** — full script, hook, letter grade, fact source |
| intelligence reports (3) | `output/tapin/reports/*.json` | scoring rationale, variant ties, real published outcomes |
| run traces (28) | `data/traces/47-75.json` | topic in/out, quality dict, cost, signals |

`data/operator_minutes.json` is 50 zeros. `data/performance_memory/` and
`data/channel_memory/` are empty directories. **There is no operator ratings or
rejections file anywhere in the repo** — every piece of recorded operator feedback lives
as prose in [planning_log.md](planning_log.md) and [debugging.md](debugging.md). That is
why this question needed a code trace to answer.

---

## 8. What follows from this

Ordered by weight of evidence, not by ease:

1. **Break the selection tie** — score the angle, not just the topic. Until five angles
   return five numbers, every other fix is judged on an arbitrary pick.
2. **Rank the playbook instead of truncating it** (`core/obsidian_facts.py:559`) — the
   smallest change with the largest single effect on tapin framing. Reuse
   `core/fact_selection.py`'s ranking rather than inventing a second one.
3. **Generalise `angle_intent.py` into a real format dimension** (#533, expanded) that
   steers the angle table, the research brief's `recommended_format`, the script prompt's
   take block, and the gates — so an explainer is not ordered to take a side, and is not
   scored inauthentic for declining to.
4. **Make option 5's idea authoritative** — always populate `creative_brief`, offer the
   typed idea as candidate 0.
5. **Extend `test_gate_agreement.py`** to `hook_score._CURIOSITY` and both
   `_SLOP_PATTERNS` lists.
6. **Instrument the trace** with menu path and detected intent.
7. **Revisit `playbook.md` itself.** It is the operator's file, it is provisional by its
   own declaration, and it is currently the strongest framing input in the system. Either
   the analytics loop confirms those eight beliefs or they should stop being executed as
   doctrine. The outcome data available today — hit rate 40%, composite uncorrelated with
   engagement, priors built on n=1 — does not confirm them.

Direction and horizon: [strategy_next_level.md](strategy_next_level.md).
