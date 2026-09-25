# Run 76 — what happened, what shipped, what is still open

> **Class:** snapshot · **Status:** frozen · **Reviewed:** 2026-09-25

Live run, 2026-09-13. Option 1, TapIn, Standard cost, typed GTA 6 thesis,
Extended length, `paste` facts, Proceed? y. Aborted at TTS. Wave 14 shipped
the abort plus the next five plus #744/#745. This file is the archive; the
mailbox points here.

**Typed seed, verbatim:**

> GTA 6 Analysis/Predictions!! Will it be the best game every? What does meeting
> the hype mean, is a goy candidate a failure? Long form predictions and content
> analysis so far

## Today's issues (the log, not the intention)

- **TTY bleed.** Windows PowerShell painted `\033[s` / `\033[u` and left
  `~1,600)` / `-- Start --pload(s) left this reset` on every menu line. Pin
  defaulted on for any TTY (#667).
- **TTS abort.** Script was 5,720 chars vs a 5,000 cap (~14% / 720 chars).
  `main.py` asked "render anyway?"; the operator said `y`; `run_media_only`
  still raised `RuntimeError: TTS character cap: 5,720 chars > 5,000` (#740).
  `--force` on `auto_generate` had the same hole. Worker stayed unforced.
- **Paste / chrome.** Prompt showed `` `paste` ``; mode entry required an exact
  `paste`. The backticked token was stored as fact 1. Share / Follow Us /
  `ffaaa` / Like (1) / Related Tags were `TIER_OPERATOR` pinned at 2.0 and
  filled the 100-line budget (#741).
- **100.0 listicles.** All five angles scored 100.0 (composite is per-topic;
  signal reuse is working as designed). `"best "` inside "best game every?"
  selected `ANGLE_LIST`; the generator used honourable-mention / closest-call
  templates. Only pick 3 (criteria) was close to the thesis (#742). Editorial
  scores 0.54-0.58 could not tell hype from honourable mention (#744).
- **Option 1 brief.** Typed thesis was the search seed; `creative_brief` stayed
  empty. #664 only covered option 5. The writer never saw an EDITORIAL ANGLE
  block (#743).
- **Gates vs packed facts.** Claim verifier window was 6,000 chars while packing
  used 11,769. "Jason and Lucia" (fact 75) and "$744 million" (fact 52) were in
  the script prompt and absent from the verifier. Grounding flagged
  Start / Read / Compare / Restricted — English verbs, not entities (#745).
  Report card grounding 0.0 -> C (70). Title/script check printed `unavailable`.
- **Title drift.** Public title was the GameSpot drones piece, not the selected
  criterion angle. Still #534.
- **Wiki `Gta` / Trends `Goy`.** Wikipedia candidate `Gta` (678d); Trends
  proxied `Goy` from the typo in "goy candidate".
- **Autocomplete 400.** YouTube autocomplete returned HTTP 400.

## What wave 14 shipped

Operator call: 5,720 vs 5,000 is **non-consequential** — warn, do not abort.
Cheap angle judge uses the existing `complete(tier="cheap")` chain. No
Anthropic/Haiku paid sub. Cursor chat APIs are not a production LLM.

| Item | Measurement |
|---|---|
| #740 | `tts_char_cap_reason("x"*5720)` is `None`; warn fires; 5,751 still hard-blocks; `run_media_only(..., force=True)` does not raise; Extended (`length_choice="4"`) floor is `max_words * 6` so 8,000 chars pass. Interactive `y` sets `force=True`. `auto_generate --force` too. Worker stays `force=False`. **Behaviour change:** 5,001 chars no longer hard-blocks. |
| #742 | Run 76 seed is not `ANGLE_LIST`. `"top 5 heavyweights"` and `"ranking every GTA protagonist"` still are. |
| #667 | On `win32`, pin is off unless `CONTENT_UI_PIN=1`. CSI bleed itself is unfixed if opted in. |
| #745 | Verifier budget is `operator_key_fact_char_budget()` (12,000). Start/Read/Compare/Restricted are not ungrounded specifics. |
| #741 | `` `paste` `` enters paste mode. Share / `ffaaa` / chrome are dropped, not pinned. |
| #743 | `brief_for_typed_topic` on the seed includes "meeting the hype"; `_build_prompts` emits EDITORIAL ANGLE. |
| #744 | Criterion/hype angle outranks honourable-mention (0.4993 > 0.2223) with `llm_judge=False`. Cheap judge fail-open keeps that order when `complete` raises. |

## LLM options (no paid Haiku)

Cheap-tier order is unchanged: OpenRouter free -> Ollama (if a model is already
installed) -> Groq -> DeepSeek. **Do not add Anthropic to that chain.** Ollama
is local/free — `ollama pull` is a download, not a subscription. Hugging Face
GGUF via `ollama pull` is the documented no-sub local option if cheap-tier is
empty here. Cursor chat APIs are not wired and must not be.

If the cheap judge is a no-op on this machine, point `OPENROUTER_API_KEY` at a
free slug or install a small Ollama model; the deterministic ranker still
separates the run 76 pair without it.

## What stayed open

Wave 15 closed **#534 #748 #746 #747 #738**. Remaining from this run:

- **#749** — Wikipedia still queries `GTA` token-joins, not `Grand_Theft_Auto_VI`.
- **#345** — heuristic title/script overlap cannot catch a wrong actor who is
  named in the script.
- GameSpot/Forbes 403, MSN headline-only, IGDB/Steam no unreleased GTA 6 page
  (expected). Caption measurement (#730 / #739) unchanged.

## Audit (Claude Code, 2026-09-13, on `b872736`)

Every measurement in the wave 14 table above reproduced: 5,720 → no refusal +
grace warning, 5,750 passes, 5,751 blocks, Extended cap 12,000, ranker
0.4993 > 0.2223, verifier budget 12,000. Google Suggest really does 400 on the
173-char seed and 200 on the 80-char trim. Suite 3,131 OK, mypy 139, ruff clean.

Five defects the wave tests could not see — they asserted only run 76's strings,
so a deletion beside each fix stayed green. All fixed, test-first
(`tests/test_wave15_audit.py`, 6 of 10 red on `b872736`; the other 4 guard what
the fixes must keep):

| Where | Defect | Fix |
|---|---|---|
| `fact_grounding._LEADING_STOPWORDS` | #745 *replaced* what/why/how/who/which/that/this/these (run 66) with Start/Read/Compare/Restricted. Entities read "Why Jason Duval", "Who Jon Jones". Verdicts unchanged (common words), labels wrong. | Restored; the four verbs kept. |
| `youtube_meta` #748 fallback | Proper-noun extraction on a Title Case title: "Rockstar Fights Drones And Hackers…" came back `failed` against a script saying exactly that. | Title words the script writes in lower case are folded first; a name the script never mentions still fails. |
| `operator_facts.is_article_chrome` #741 | Bare substring `affiliate` dropped real facts ("Amazon's affiliate program cut commission rates"); `about the author` matched "about the authorities". | Word-bounded disclosure phrases only. |
| `pipeline.run_discovery` #744 | Cheap LLM judge on every discovery with no off switch; the suite's discovery tests made 8 real `complete()` calls. | `ANGLE_LLM_JUDGE` (default on, documented); suite sets it off. |
| `angle_ranker._thesis_terms` | `is\b` had no leading boundary, so "This…" opened a question stem. | `\b` added. |

Seen, not fixed (small): `_WIKI_STOP` drops a capitalised `Will`/`Long`, so
"Long Beach port strike" → `Beach_Port_Strike` (belongs with #749). A fact line
that starts "Paste the…" enters paste mode (the text is still kept). The title
prompt's forced pin can be a contraction ("won't") — measured titles were fine.
