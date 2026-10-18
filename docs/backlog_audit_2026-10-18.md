# Backlog audit — 2026-10-18

> **Class:** snapshot · **Status:** frozen · **Reviewed:** 2026-10-18

The operator, 2026-10-18: "go through the backlog as well and make sure everything needs to be
there, adds value to the project, and wont be replaced or altered by a later entry." The backlog
held 258 open items against 44 public videos. Each one was read and given one of four
answers, and the rules that decided them are now [hands_off_plan.md](hands_off_plan.md)'s theme
E:

- **kept** - it names a measured defect or an operator ask, and nothing later replaces it;
- **merged** - a later or more precise entry carries it; the closed one names that entry;
- **retired** - it has no exit criterion, a decision overruled it, or it adds nothing at this
  channel's size (69 subscribers, 147 organic Shorts views a week); reopen with a reason;
- **shipped** - the code already does it; the closing note says where.

Closed items keep their numbers and text in [backlog.md](backlog.md), ticked with
`closed 2026-10-18 - ...`, so a regression-corpus case or an older doc that cites one still finds it.

**188 closed** - 92 merged, 83 retired, 13 shipped. **70 kept.**

| Item | Answer | Into | Why |
|---|---|---|---|
| instagram_figures signal — still templated only; catalog e | retired |  | a disabled, templated signal; the paid-signal bill is #1071's |
| Free-backend probe for Twitter/X, if the signal is ever wort | retired |  | twitter is retired (enabled: false) and nothing plans to restore it |
| Free-backend probes — TikTok/Twitter equivalents (only if th | merged | #1071 | the free-backend question is #1071's |
| Third-vertical groundwork: AI Tools / Tech — channel profile | merged | #1079 | a third channel is decided with data, once (#1079) |
| Tighten the mypy baseline (the other half of the old combin | retired |  | the blocking ratchet (scripts/mypy_ratchet.py) holds the count; it may only fall |
| C-follow-ups — LLM-proposed directives; optional auto-apply  | retired |  | no measurement or exit criterion; hook learning (#985) and the experiment ledger cover a gate-winner |
| Thumbnail scoring → CTR (needs impressions/CTR in the metric | merged | #1058 | CTR into the learning loop is one item, and it needs the Reporting API on |
| Full operator dashboard / Channel Command Center [XL] | merged | #169 | tracked in desktop_app.md Stage 6 (Portfolio), which closes it |
| Tavily / broad web research; Bluesky direction signal [M] | retired |  | auto-research (#863) reads the web for facts at $0; no measurement asks for a paid search API or a Bluesky signal |
| Multi-language (single script → localized TTS) — low priorit | retired |  | low priority for a US sports and gaming channel at 69 subscribers; reopen with a decision |
| Recommender simulation harness — synthetic histories so the  | merged | the unnumbered recommender backtest | the same E1 question, volume-gated the same way |
| Hook-score vs retention calibration (E1) — 0–100 heuristic | merged | #1290 | the measured version: r=-0.41, retuned once 21 videos settle it |
| Pillow remains fallback [S] | retired |  | a note, not a task |
| Backtest recommender accuracy vs. realised engagement once v | merged | the unnumbered recommender backtest | a duplicate of the first entry |
| instagram_figures — still templated only; catalog enabled | retired |  | a duplicate of the instagram_figures entry above |
| git remote — repo initialised locally; create private | shipped |  | the repo pushes to GitHub and CI runs on every push |
| Tighten the mypy baseline (~94 errors → fix the real ones, e | retired |  | a duplicate; the blocking ratchet replaced it |
| Annotate/retire the remaining best-effort broad except Exce | retired |  | no exit criterion; fail-open handlers are the rule for signals (CLAUDE.md) |
| Raise test coverage on render + publish paths [M] | retired |  | no exit criterion; every defect gets its own fail-first test and corpus case |
| Multi-language — single script → translated script + loc | retired |  | a duplicate of the multi-language entry above |
| Ingest a long video / VOD / podcast (file or URL) → transcri | merged | the unnumbered clip-from-source | the same programme (Phase R) |
| Reuse the scoring / hook / caption stack from Phases P–Q. [ | merged | the unnumbered clip-from-source | a note on how Phase R is built |
| Observability — structured run traces + timing dashboard | shipped |  | promoted to Pillar 1: run traces in data/traces, ops traces and ops explain |
| Multimodal rendered-video review [L] (later) — sampl | merged | the unnumbered router vision path | a duplicate |
| Clip-from-source (Phase R) + subject-tracked auto-refram | merged | the unnumbered clip-from-source | a duplicate |
| Avatar mode, upscaling (Real-ESRGAN/RIFE), storyboard shot | merged | the unnumbered avatar mode entry | a duplicate |
| Governor follow-ups (O12 candidates) — YouTube units und | merged | #376 | YouTube units under a planner are #376 |
| Free-backend probes (optional) — TikTok/Twitter equivale | merged | #1071 | a duplicate of the free-backend question |
| MoneyWise depth wave (domain_expansion.md, ROI 9.5) | merged | the unnumbered MoneyWise depth wave | a duplicate; MoneyWise is parked (decisions_2026-10 §41) |
| Third-vertical groundwork: AI Tools / Tech (ROI 9.0) — n | merged | #1079 | a duplicate |
| Engineering hygiene — CI coverage reporting (non-blockin | retired |  | the mypy ratchet and the reversed-order suite are CI-blocking; coverage reporting has no decision behind it |
| TikTok publisher — TIKTOK_CLIENT_KEY/SECRET present; | retired |  | superseded by the Buffer route (#1188-#1199), which posts TikTok and Instagram with the PC off |
| Instagram Reels / Meta — META_APP_ID/SECRET, INSTAGRAM_ | retired |  | superseded by the Buffer route (#1188-#1199), which posts TikTok and Instagram with the PC off |
| Per-platform caption/hashtag shaping from existing SEO + Tik | shipped |  | #1197: captions and first lines per platform, A/B'd |
| Cross-platform performance back into the learning loop (unif | shipped |  | #1196: per-platform recommenders |
| Thumbnail scoring → CTR [M] | merged | #1058 | a duplicate |
| Prompt performance analysis (after provenance shipped) [M] | merged | the unnumbered prompt/asset ranking | a duplicate |
| Asset effectiveness ranking from assets history [M] | merged | the unnumbered prompt/asset ranking | a duplicate |
| Full operator dashboard + Channel Command Center [XL] | merged | #169 | tracked in desktop_app.md Stage 6 (Portfolio), which closes it |
| Tavily / broad web research [M] | retired |  | a duplicate of the Tavily entry above |
| Bluesky direction signal [S] | retired |  | a duplicate of the Bluesky entry above |
| Reuse scoring from assets history for background selection | merged | the unnumbered prompt/asset ranking | the same asset-history question |
| #32 | merged | #1074 | core/ui.py moves with the next sub-packages |
| #40 | retired |  | videos are made by overnight and batch-review now, not at the interactive report card |
| #48 | merged | #991 | a series format is #991 |
| #51 | merged | #1079 | the input of a third channel, decided once (#1079) |
| #54 | merged | #356 | the consumer of the stored retention curve |
| #111 | retired |  | Shorts have no end screens or cards |
| #119 | retired |  | decisions §26 drops stock footage for owned gameplay |
| #144 | retired |  | superseded by the Buffer route (#1188-#1199), which posts TikTok and Instagram with the PC off |
| #146 | merged | desktop_app.md | tracked in desktop_app.md Stage 5 (Packaging), which closes it; scheduled tasks run the worker and overnight today |
| #149 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #154 | merged | desktop_app.md | tracked in desktop_app.md Stage 5 (Packaging), which closes it |
| #155 | merged | desktop_app.md | tracked in desktop_app.md, the application programme |
| #156 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #157 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #159 | merged | the unnumbered MoneyWise depth wave | MoneyWise is parked (§41); one item holds it |
| #160 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #161 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #162 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #163 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #164 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #165 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #166 | merged | the unnumbered $0 TTS switch | the ear test belongs to the switch |
| #167 | merged | the unnumbered recommender backtest | the same backtest, volume-gated |
| #169 | merged | desktop_app.md | tracked in desktop_app.md Stage 6 (Portfolio), which closes it |
| #174 | merged | desktop_app.md | tracked in desktop_app.md Stage 5 (Packaging), which closes it |
| #175 | merged | desktop_app.md | tracked in desktop_app.md, the application programme (the palette, #521) |
| #176 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #177 | merged | desktop_app.md | tracked in desktop_app.md Stage 6 (Portfolio), which closes it |
| #178 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #179 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #180 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #181 | merged | #1058 | thumbnail learning needs CTR first |
| #189 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #192 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #193 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #194 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #195 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #196 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #197 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #199 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #201 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #202 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #203 | merged | #376 | the uploads-left number belongs to the unit planner |
| #204 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #205 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #206 | shipped |  | ops overnight-plan says why each draft waits |
| #207 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #208 | shipped |  | go-public's watch-and-publish pass: now / at its slot / keep / set aside |
| #210 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #211 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #212 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #213 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #214 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #215 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #216 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #217 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #218 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #219 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #220 | retired |  | a drawing of a number the CLI and the operator pages (Back-Home List, Story) already print; the desktop programme designs its panels from its own Stage 3 list |
| #293 | merged | desktop_app.md | tracked in desktop_app.md Stage 5 (Packaging), which closes it |
| #343 | retired |  | re-checking is cheap at two videos a day, and a second fact cache would hide stale facts |
| #349 | retired |  | voice facts (#450) and the booth take the operator's facts |
| #359 | merged | #1079 | a third channel's priors, decided with it |
| #361 | retired |  | comments are a handful a video; nothing to learn from yet |
| #363 | merged | #535 | the same embedding question |
| Ollama model pull (optional) — ops doctor ollama FAIL  | retired |  | an operator note; ops doctor prints it |
| #375 | retired |  | Ollama is optional; the router's free chain is DeepSeek and OpenRouter |
| #377 | retired |  | ops economics and cost-tower show the spend; no gap against an invoice was measured |
| #384 | retired |  | ops incidents and reliability rank failures, and §19's retire rule decides |
| #387 | merged | #464 | recorded fixtures are the enabling asset |
| #390 | retired |  | two paid signals are left; nothing to short-circuit |
| #397 | retired |  | rosters come from the live Wikidata lookup (#963) |
| #398 | merged | #464 | recorded fixtures are the enabling asset |
| #399 | merged | #1290 | hook shapes against who stayed is #1290 and #985's learning |
| #401 | merged | the unnumbered $0 TTS switch | part of the switch |
| #408 | merged | the unnumbered MoneyWise depth wave | MoneyWise's vocabulary, parked with it |
| #410 | merged | the unnumbered $0 TTS switch | part of the switch |
| #413 | merged | #464 | the same reproducibility question |
| #421 | retired |  | a render takes about 30 seconds |
| #425 | merged | the unnumbered clip-from-source | its scoring half |
| #436 | retired |  | no strike to date; policy_runbook.py holds the process |
| #461 | merged | #460 | one typed settings object; the env-key test already checks documentation |
| #465 | merged | #35 | one migration story |
| #469 | merged | #79 | non-ad revenue, one spike with a kill criterion |
| #470 | retired |  | no newsletter audience; reach is TikTok and Instagram through Buffer |
| #471 | retired |  | no audio audience; reach is TikTok and Instagram through Buffer |
| #472 | merged | #1057 | re-cuts of past winners |
| #474 | retired |  | viewer questions are a handful; the mailbag (#114) reads them |
| #476 | merged | desktop_app.md | tracked in desktop_app.md Stage 6 (Portfolio), which closes it |
| #477 | retired |  | one channel; ops economics shows its margin |
| #478 | merged | #1079 | a third channel's kit, decided with it |
| #480 | retired |  | nothing is published; no reason recorded |
| #483 | merged | #1077 | the main menu redesign |
| #494 | retired |  | traces, ops explain and ops postmortem reprint a run |
| #501 | merged | #1290 | a re-cut needs a hook score that predicts; today it runs backwards |
| #507 | merged | #730 | caption placement over on-screen text |
| #510 | retired |  | long-form is 10 hours of 4,000; #138 comes first |
| #516 | merged | #445 | resume from the ledger |
| #517 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #518 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #519 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #520 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #521 | merged | desktop_app.md | tracked in desktop_app.md, the application programme |
| #522 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #524 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #526 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #528 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #530 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #531 | merged | desktop_app.md | tracked in desktop_app.md Stage 5 (Packaging), which closes it |
| #536 | retired |  | another manual step; the operator asked for fewer |
| #538 | retired |  | the hook-variant pass (#987) already writes and keeps variants |
| #546 | shipped |  | core/length_recommender learns the length from engagement history (ops recommend-length) |
| #556 | retired |  | voice facts (#450) and the booth correct facts |
| #576 | retired |  | no measured overhead |
| #577 | shipped |  | publishing/snippet_update and ops fix-description edit a description without a re-render |
| #592 | retired |  | the signal cache exists, and CLAUDE.md forbids a second |
| #594 | retired |  | no measured need |
| #597 | retired |  | low value at 69 subscribers |
| #603 | merged | #434 | the Data API does not expose claims; a pre-check is what can be built |
| #604 | retired |  | multi-language is retired above |
| #606 | shipped |  | ops channel-go-live and the prepublish checks gate an upload |
| #611 | retired |  | a render takes about 30 seconds |
| #613 | merged | #1074 | core/ui.py moves with the next sub-packages |
| #614 | merged | desktop_app.md | tracked in desktop_app.md Stage 3 (Panels), which closes it |
| #615 | merged | #391 | one HTTP client |
| #616 | merged | desktop_app.md | tracked in desktop_app.md Stage 5 (Packaging), which closes it |
| #617 | merged | #35 | one migration story |
| #618 | merged | #35 | one migration story |
| #620 | merged | #446 | undo for destructive commands |
| #621 | retired |  | one PC |
| #622 | retired |  | one PC |
| #624 | retired |  | no measured contention |
| #628 | retired |  | CI runs the suite forward and reversed |
| #668 | retired |  | cosmetic; Windows Terminal works without the profile |
| #673 | merged | #650 | one real-console smoke check |
| #858 | merged | #863 | one measurement of fact intake on real runs |
| #900 | merged | #889 | one listening check |
| #914 | retired |  | renders run on Windows; CI does not render |
| #952 | retired |  | superseded by the Buffer route (#1188-#1199), which posts TikTok and Instagram with the PC off |
| #993 | merged | #1290 | what the variants teach is read against who stayed |
| #1029 | shipped |  | #985's hook learning feeds the openers that held best to the rewrite (fixed wave 108) |
| #1049 | merged | #1058 | CTR learning is one item |
| #1069 | shipped |  | desktop Stages 0, 2 and 4: one token set renders the app chrome and the assets |
| #1070 | merged | desktop_app.md | tracked in desktop_app.md, the application programme |
| #1078 | shipped |  | overnight renders up to its cap, batch-review is the morning queue and overnight-plan says why the rest wait; the app half is Stage 3 |
| #1295 | shipped |  | wave 110: a game preview with no free slot before kickoff goes out as it uploads (core/spaced_queue, _ASAP_LEAD) |
