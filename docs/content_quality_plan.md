# Content Quality & Variety Plan — 2026-06-25

**Scope: documentation & planning only — no code in this pass.** Five issues
observed on live runs, each traced to a real call site, each planned *within the
lens of automation* (no human-in-the-loop step). Companion to
[assessment.md](assessment.md) (weaknesses #1 recency, #4 visual depth) and
[audit_2026-06-25.md](audit_2026-06-25.md).

| # | Operator symptom | Root cause (file) | Fix class |
|---|---|---|---|
| 1 | "Emma Frost = the *most recent* Marvel Rivals character" | claim-grounding gap (`core/fact_grounding.py`) | Grounding framework |
| 2 | Same voice every video | channel pins one `voice_id` (`config/channels.json`) | Config + rotation |
| 3 | GTA VI video played the **same stock clip twice in a row** | no cross-beat dedup (`assets/manager.py:204`) | B-roll selection |
| 4 | Videos feel **bland / samey** now the process is dialed in | TTS-only render, hard cuts, no music/motion (`video/render_video.py:67`) | Production polish |
| 5 | **Static keywords** → a Ronaldo video pulls generic "football/sports" footage, same clip every time | entity discarded for a hardcoded literal (`assets/background_query.py:93`) | Query construction |

> **Code-ready implementation specs** (exact prompt text / filter graphs / function
> signatures): §1–§4 → [spec_quality_fixes_1_to_4.md](spec_quality_fixes_1_to_4.md);
> §5 → [spec_background_query_entity_anchor.md](spec_background_query_entity_anchor.md).

---

## 1. Recency / superlative hallucination control

### Symptom
A script asserted a character was *"the most recent"* addition to Marvel Rivals.
Even if that character **is** a real (grounded) character, the **"most recent"
claim** is an unverified temporal assertion the model invented.

### What already guards this (be fair to the framework)
The anti-hallucination spine is genuinely strong already:
- `core/content_engine.py` prompt: *"Do NOT introduce hero names not named in
  VERIFIED FACTS"*, *"Do NOT state who is champion … from memory"*, and an
  analysis-format rule banning *"just released" / "biggest update yet"* framing
  (lines ~185–199, 285).
- `core/fact_grounding.py` flags ungrounded proper-noun specifics post-generation.
- `core/fact_recency.py` drops future-dated completed-action "facts".
- `_maybe_reground_script` regenerates once to strip flagged specifics.

### The precise gap
Every guard above checks **entity grounding** ("does this name appear in the
facts?") — none checks **claim grounding** ("is this *superlative / recency*
assertion supported by a dated fact?"). "Emma Frost" passes entity-grounding; the
word **"recent"** next to it is unchecked. The model fills the *ordering/recency*
slot from stale training memory.

### Plan (precision-first, reuses existing passes)

**P1 — Prompt rule (cheapest, do first).** Extend the existing "just released"
ban (content_engine ~line 285) into an explicit **superlative/recency clause**:
*"Never call anything the newest / latest / most recent / first-ever / now-the-X
unless a VERIFIED FACT carries an explicit date or 'released on' line proving it.
Otherwise write 'a recent…' / 'one of the new…' or pose it as a question."* No new
code — a prompt edit. Catches the majority at the source.

**P2 — `core/recency_claims.py` detector (planned, mirrors `fact_grounding`).**
A pure, unit-tested, precision-first detector: regex for recency/superlative
markers (`most recent|newest|latest|just (dropped|released|added)|first ever|the
new\b|now the (champion|leader)`) bound to a nearby noun phrase. A claim is
**supported** only if the facts corpus contains a date/recency-typed line for that
entity inside a freshness window (e.g. ≤ N days). Unsupported → flag (never
rewrite inline — same philosophy as fact_grounding).

**P3 — Route flags into the existing regen, don't add a pass.** Feed P2's flags
into `_maybe_reground_script`'s flagged-specifics list so the *one* existing regen
softens "the most recent character" → "one of the recent characters" / question
framing. Reuse, no new LLM round-trip.

**P4 — Demand a recency-typed fact when the topic implies it.** When the
topic/angle itself contains a recency marker ("newest hero", "latest patch"),
require at least one **dated** fact from a recency source (`web_search` news, dated
RSS) before allowing a superlative; else fall back to the existing THIN FACTS /
hypothetical framing. Ties into `core/fact_recency.py`.

**Flags:** `RECENCY_CLAIM_GUARD=warn|reground|off` (default `warn`, matching the
cautious rollout of grounding-regen). **Tests:** supported-superlative passes;
unsupported "most recent" flags; non-superlative prose untouched (false-positive
guard). **Tradeoff:** over-aggressive matching could soften legitimate claims —
keep precision-first like `fact_grounding`, ship as `warn` first.

---

## 2. ElevenLabs voice rotation (pool, not "the one")

### Symptom & immediate cause
Every video uses one voice. The rotation machinery **already exists** —
`core/tts.py` has `VOICE_REGISTRY`, `weighted_random_voice()`, and
`resolve_tts_config()` which uses `tts_voice_pool` when present. But
`config/channels.json` pins a single voice on the production channels:

```
default   → voice_pool {3 voices}      ✅ rotates
tapin     → voice_id  "nPcz…"          ❌ single — short-circuits the pool
moneywise → voice_id  "nPcz…"          ❌ single
```

`resolve_tts_config` returns `profile.tts_voice_id` *before* it ever reaches the
pool (tts.py:52–53). So the "retainer" is one line of config away.

### Plan

**P1 — Config only, zero code (do first).** Replace `voice_id` with `voice_pool`
on `tapin` / `moneywise` (curate the right voices per channel — e.g. finance vs
gaming tone). The existing weighted-random path takes over immediately.

**P2 — Anti-repeat rotation (planned code).** `random.choice` can pick the **same
voice twice in a row**, which reads as "no rotation." Add a persisted last-used
record (`data/voice_state.json`, per channel) and exclude the last 1–2 voices from
the next draw — a true rotating retainer, not memoryless random. Optional strict
`VOICE_ROTATION=roundrobin` for deterministic cycling.

**P3 — Brand-consistency guardrail.** Rotating *every* video trades brand voice
recognition for variety. Recommended middle path: a curated **per-channel house
set** (2–4 on-brand voices), gender/tone-locked to the persona
(`channels.json` "persona"), rotated with anti-repeat. Keep a `voice_id` override
escape hatch for a channel that wants one signature voice.

**Flags:** `VOICE_ROTATION=weighted|roundrobin|off`. **Tests:** pool resolves to >1
distinct voice across N calls; anti-repeat never returns the immediately-previous
voice; single `voice_id` still pins (back-comp). **Tradeoff:** variety vs brand
recognition — documented above; default to the house-set compromise.

---

## 3. Duplicate back-to-back B-roll (GTA VI)

### Root cause
`assets/manager.get_scene_matched_background` (line ~204) loops scenes and calls
`get_stock_background_asset(sc.query, channel_id)` **with no exclusion set**.
`video/scene_plan.plan_scenes` builds each query as `f"{topic} {kw}"`; when two
beats share a keyword — or a beat has no keyword and falls back to the bare topic
("GTA VI") — the queries are identical, the provider returns its identical top
result, and `build_multi_concat_command` concatenates the **same clip twice in a
row**.

### Plan

**P1 — Cross-beat dedup (the core fix).** Thread a `used: set[str]` (clip
path/provider-id) through the scene loop and pass it to
`get_stock_background_asset(..., exclude=used)`; the provider returns the next
unused result instead of the same top hit. Add each chosen clip to `used`. Purely
additive, fail-safe (no distinct clip → fall back as today).

**P2 — Query diversification.** In `plan_scenes`, de-duplicate beat keywords so two
beats don't emit the identical query; when `_beat_keyword` repeats, fall back to
the next-salient term rather than the bare topic.

**P3 — Provider paging.** `get_stock_background_asset` requests a small result page
(e.g. top 5) and the manager picks the first not in `used` — robust even when
queries legitimately overlap.

**P4 — Visual safety net (shared with §4).** Even with distinct clips, hard cuts
between similar gameplay look repetitive — `xfade` crossfades (see §4) make near-
matches read as intentional motion, not a glitch.

**Tests:** two identical-query beats yield two distinct clip paths; exclusion set
honored; exhausted-results path still falls back cleanly. **Tradeoff:** more
provider calls per render (mitigated by the existing asset cache).

---

## 4. "Bland / samey" videos — production polish within automation

### Root cause
The render is deliberately minimal: `build_render_ffmpeg_command`
(`video/render_video.py:67`) maps **TTS audio only** (stock audio muted), a single
`scale/crop/subtitles` video chain, **hard cuts**, **no music, no SFX, no motion,
no loudness normalization**. Combined with one voice (§2) and generic, sometimes-
repeating b-roll (§3), every video has the same sonic and visual signature. All
the missing levers are **deterministic FFmpeg filters — fully automatable.**

### Plan — grouped by lever (each opt-in + fail-safe, like scene-matched b-roll)

**A. Audio bed + dynamics** *(biggest perceived-quality jump)*
- **Background music**: add a 3rd input (per-channel mood folder, e.g.
  `assets/music/{channel}/`), mixed under the voice with **sidechain ducking**
  (`sidechaincompress`) so music dips when the VO speaks. Insertion point:
  `build_render_ffmpeg_command` filter graph + a `-i music` input + `amix`.
- **Loudness normalization**: `loudnorm` on the voice for consistent perceived
  volume across videos (currently raw TTS levels).
- **SFX accents**: short whoosh/impact on scene cuts and the hook (library SFX,
  timed to scene boundaries already known from `plan_scenes`).
- ⚠ **Copyright/Content-ID note**: use a royalty-free / license-cleared library
  only; document the source in attribution. This is the one lever with a platform
  risk — plan a curated local library, not scraped audio.

**B. Motion** *(kills the "static clip" feel)*
- **`zoompan` (Ken Burns)**: slow push/pan on otherwise-static background — one
  filter, big effect.
- **Hook zoom-in**: the roadmap already lists this as an "optional flourish"
  (Phase Q) — a punch-in on the first 1–2 s.
- (Beat-synced cuts already ship via scene-matched b-roll.)

**C. Transitions**
- Replace the hard concat in `assets/composite.build_multi_concat_command`
  (line ~83) with **`xfade` crossfades** between scene clips — smoother and
  doubles as the §3 P4 safety net.

**D. Caption variety**
- Karaoke highlight + keyword pop already exist (`CAPTION_STYLE`, Phase Q). Add a
  small **per-video caption theme rotation** (color/position/animation from a
  curated set) so captions aren't visually identical every time.

**E. Script-side sameness** *(the deeper "bland" driver)*
- Persona, stance, and insight injection already exist — the sameness is often
  **structural**: same hook archetype, same opener cadence. Plan a **hook/opener
  archetype rotation** (question / bold-claim / stat-shock / contrarian) biased by
  the title-pattern leaderboard (`core/title_experiments`) so variety is
  *data-driven*, not random. Pairs with the A/B title loop already shipped.

**Flags (all default-off, fail-safe):** `RENDER_MUSIC=on`, `MUSIC_DUCKING=on`,
`RENDER_LOUDNORM=on`, `RENDER_SFX=on`, `RENDER_KENBURNS=on`, `HOOK_ZOOM=on`,
`SCENE_TRANSITIONS=xfade|none`, `CAPTION_THEME_ROTATE=on`. **Tests:** ffmpeg
command builders include the right filters/inputs when flagged and are unchanged
when off; missing music/SFX file → falls back to today's silent-bed render (never
breaks). **Tradeoffs:** longer render time (mitigate with `-preset`), and the
copyright caution in (A).

---

## 5. Static keywords → generic, repeating footage ("Ronaldo" pulls "football")

> **Full implementation spec:**
> [spec_background_query_entity_anchor.md](spec_background_query_entity_anchor.md)
> — code-ready signatures, near-final code, env flags, and the test plan for this
> section.

### Symptom
A Ronaldo video pulls generic football/sports stock — not Ronaldo footage — and
the **same clip every time**. The subject the video is *about* is dropped from the
search; a hardcoded category template takes its place.

### Root cause (the smoking gun)
`assets/background_query._rule_based_query` (`assets/background_query.py`):

```
if category == "sports":
    return "basketball football sports arena gameplay"   # line 93 — entity discarded
if category == "gaming":
    return "video game gameplay esports"                 # line 95 — same
```

Three compounding static layers:
1. **`infer_domain` is a hardcoded keyword whitelist** (`apis/topic_scorer.py:143`)
   covering nba / nfl / ufc / finance / gaming — **no soccer/football, tennis, F1,
   etc.** "Ronaldo" matches nothing → domain falls through.
2. **`_DOMAIN_QUERIES`** (`background_query.py:38`) is a fixed template dict; the
   entity is only weakly appended for the *known* domains, and there's no soccer
   entry anyway.
3. **The category fallback returns a literal string** that *replaces* the topic —
   `_extract_entities` does grab "Ronaldo" (line 65) but the sports branch
   **throws it away** and returns the generic. Then `@lru_cache` (line 130) +
   deterministic provider top-result ⇒ the *identical* clip every run.

> The LLM query path (`_llm_query`, default-on, entity-aware) is actually the
> *right* design — but it's only a preference over `rule_q`, and it falls back to
> this static literal whenever the LLM is off/fails or its output trips the
> abstract-term filter. The rule-based floor is what needs fixing.

### Principle
**The subject entity always anchors the query; domain/category is only a
*qualifier suffix*, never a *replacement*.** "Cristiano Ronaldo soccer" — never
"basketball football sports arena gameplay". A keyword qualifies a query *only when
it's bound to the topic's actual subject*, mirroring the signal relevance gate
(RAWG token-overlap) the project already applies elsewhere.

### Plan

**P1 — Entity-first rule query (the core fix).** Rewrite `_rule_based_query` so
the extracted entities **lead** and templates **qualify**: `f"{entities} {domain
qualifier}"`. The category literals become a *suffix appended to the entity*, used
as a qualifier — never a standalone return that drops the subject. If no entity is
found, *then* fall back to a generic (that's the only time generic is correct).

**P2 — Stop unknown subjects collapsing to generic.** When `infer_domain` returns
unknown/neutral **but an entity exists**, trust the entity + lean on the
entity-aware LLM query, rather than the static sports/gaming literal. (Quick
complementary win: add the missing sports — soccer/football, tennis, F1 — to
`infer_domain` and `_DOMAIN_QUERIES`; durable win is not depending on the whitelist
being complete.)

**P3 — Topic-binding gate.** Enforce that the lead entity in the footage query is a
token actually present in the topic (the user's exact ask: "Ronaldo" qualifies a
query *only* in conjunction with a Ronaldo topic, not any football/world-cup
video). Reuse the token-overlap discipline from `apis/rawg_api.py`'s relevance
gate.

**P4 — Controlled variation (anti-"same clip every time").** Even entity-anchored,
`@lru_cache` + result[0] returns one clip forever. Introduce *bounded* variation:
rotate among the top-K provider results (seeded by date/run) and/or vary a small
qualifier set ("highlights" / "match" / "stadium") so successive Ronaldo videos
differ. **Cross-video clip memory**: remember recently-used clip IDs per subject
(a superset of §3's within-video dedup) so the next Ronaldo video doesn't reuse the
last Ronaldo clip.

**P5 — Scene-matched parity.** `video/scene_plan.plan_scenes` already anchors on
`f"{topic} {kw}"` (good) — ensure the **subject entity persists across all beats**
while each beat adds a *differentiating* sub-keyword, so beats stay Ronaldo-specific
but distinct. Shares the §3 dedup machinery.

**Flags:** `BACKGROUND_QUERY_VARIATION=on` (P4 top-K rotation),
`BACKGROUND_ENTITY_ANCHOR=strict` (P3 topic-binding). **Tests:** a soccer/Ronaldo
topic yields a query that *contains* "Ronaldo" and never the bare generic literal;
unknown-domain + entity doesn't collapse to the static string; two runs of the same
topic can return different clips (P4); no-entity topic still falls back cleanly.
**Tradeoff:** entity-anchored queries occasionally return thinner stock results than
a broad generic — keep the generic as a *last-resort* fallback, and let the existing
provider chain (local → Pexels → Pixabay) absorb misses.

---

## Sequencing (risk-ordered; all automation-safe)

| Step | Item | Effort | Impact | Risk | Notes |
|---|---|---|---|---|---|
| 1 | §2 P1 — voice `voice_pool` config swap | `[S]` | High | None | Zero code; immediate |
| 2 | §5 P1 — entity-first background query | `[S–M]` | High | Low | Stops generic/repeat footage |
| 3 | §3 P1 — b-roll cross-beat dedup | `[S–M]` | High | Low | Fixes the visible glitch |
| 4 | §1 P1 — superlative/recency prompt rule | `[S]` | High | Low | One prompt edit |
| 5 | §5 P3 — topic-binding entity gate | `[S]` | Med | Low | "Ronaldo" only on Ronaldo topics |
| 6 | §4-A — music bed + ducking + loudnorm | `[M]` | High | **Copyright** | Curated library first |
| 7 | §4-B/C — Ken Burns + xfade transitions | `[S–M]` | Med | Low | Pure FFmpeg |
| 8 | §5 P4 — query variation + cross-video clip memory | `[M]` | Med | Low | Anti-"same clip every time" |
| 9 | §1 P2–P3 — recency-claim detector + regen | `[M]` | High | Med | Mirror fact_grounding |
| 10 | §2 P2 — anti-repeat voice rotation state | `[S]` | Med | Low | data/voice_state.json |
| 11 | §4-E — data-driven hook archetype rotation | `[M]` | Med | Low | Uses title-pattern loop |

**Principles carried from the existing code:** every new lever ships **opt-in**,
**fail-safe** (degrade to today's behavior on any error, like scene-matched
b-roll), **precision-first** (grounding guards warn before they rewrite), and
**unit-tested** per [decisions.md](decisions.md) §11. None changes the pipeline's
contract — they make the existing output sharper, more grounded, and less samey.

---

## Cross-references
- Recency: [assessment.md](assessment.md) §weakness-1; `core/fact_grounding.py`,
  `core/fact_recency.py`, `core/content_engine.py`.
- Voice: `core/tts.py`, `config/channels.json`, `config/validate_channels.py`.
- B-roll: `assets/manager.py`, `assets/composite.py`, `video/scene_plan.py`.
- Background query: `assets/background_query.py`, `apis/topic_scorer.py`
  (`infer_domain`), `assets/category.py`; relevance-gate pattern in
  `apis/rawg_api.py`.
- Polish: `video/render_video.py`, roadmap Phase Q "dynamic emphasis".
