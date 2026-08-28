# Implementation Spec — Quality Fixes §1–§4

**Status: spec / planning-only (no code in this pass).** Code-ready specs for
**§1–§4** of [content_quality_plan.md](content_quality_plan.md): exact prompt text,
FFmpeg filter graphs, and function signatures. (§5 has its own spec:
[spec_background_query_entity_anchor.md](spec_background_query_entity_anchor.md);
§3 is mostly subsumed by it — see §3 below.)

Shared conventions (carried from existing code): every new pass is **opt-in**,
**fail-safe** (returns today's output on any error), **precision-first** for
grounding, and **unit-tested** per [decisions.md](decisions.md) §11. Render-path
filters are marked **⚠ verify on a real render** per the project's standing rule.

---

## §1 — Recency / superlative claim grounding

### 1.0 Acceptance
A script that says *"Emma Frost, the most recent character"* with no dated fact
backing the recency is either softened ("one of the recent characters") by the
existing regen pass or surfaced as a warning. A *supported* recency claim (a dated
fact exists) is left untouched. Non-superlative prose is never altered.

### 1.1 Where it slots in (exact orchestration)
`core/content_engine.py` already runs guards in order (lines 692–719):

```
692  script = _maybe_recenter_on_key_facts(...)
697  script = _maybe_inject_insight(...)
709  ungrounded = find_ungrounded_entities(script, grounding_text)      # entity gate
713  script, ungrounded = _maybe_reground_script(..., ungrounded)        # regen-then-warn
714  if ungrounded: logger.warning(...)
```

The recency guard is a **sibling of `find_ungrounded_entities`** whose flags feed
the **same** `_maybe_reground_script` call — no new LLM round-trip.

### 1.2 P1 — Prompt rule (one edit, do first)
`content_engine.py`, INSTRUCTIONS block, **insert after line 285** (the existing
"just released" rule):

```
- RECENCY/SUPERLATIVE: Never call anything the "newest", "latest", "most recent",
  "brand-new", "first-ever", or "now the [champion/#1]" unless a VERIFIED FACT
  carries an explicit date or "released/added on …" line proving it. Otherwise say
  "a recent…", "one of the new…", or pose it as a question. Ordering and recency
  are facts, not vibes — do not assert them from memory.
```

Bump `PROMPT_VERSION` (provenance already tracked on `content_runs`).

### 1.3 P2 — New module `core/recency_claims.py` (mirrors `fact_grounding.py`)

```python
"""Flag UNSUPPORTED recency/superlative claims.

Entity-grounding (fact_grounding) checks "is this name in the facts?" — it does NOT
check "is 'the most recent' true?". A script can name a real, grounded character and
still invent that it's the *newest*. This flags a recency/superlative assertion when
the facts carry no dated line supporting it, so the existing reground pass can soften
it. FLAGS, never rewrites (same philosophy as fact_grounding).
"""
from __future__ import annotations
import datetime, re

_MARKER = re.compile(
    r"\b(most recent|newest|latest|brand[- ]new|just (?:dropped|released|added|launched|"
    r"announced|revealed)|first[- ]ever|now the (?:champion|leader|number one|#?1)|"
    r"the new(?:est)?)\b",
    re.I,
)
# A dated/recency-typed fact line looks like one of these (reuse fact_recency months).
_DATEISH = re.compile(
    r"\b(20\d{2}|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
    r"today|yesterday|this week|released|launched|added|debuted)\b",
    re.I,
)

def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]

def find_unsupported_recency_claims(
    script: str, facts_text: str, today: datetime.date | None = None
) -> list[str]:
    """Return clauses that assert recency/superlative without a dated fact backing.

    Conservative: a claim is flagged only when (a) a marker appears, AND (b) the
    facts corpus has NO date-ish line at all (so it can't be substantiating any
    'newest' claim). When the facts DO carry dates we defer to entity-grounding —
    precision over recall, like fact_grounding.
    """
    facts_has_date = bool(_DATEISH.search(facts_text or ""))
    if facts_has_date:
        return []  # facts carry recency; don't second-guess specific bindings here
    flagged: list[str] = []
    for sent in _sentences(script):
        m = _MARKER.search(sent)
        if m:
            flagged.append(sent)
    return flagged
```

> Design choice: gate on *"facts contain no dates at all"* keeps false positives
> near-zero (the exact failure mode observed: generic facts, model invents recency).
> A later, higher-recall version can bind each marker to the nearest entity and
> require a date *for that entity* — ship the conservative version first.

### 1.4 P3 — Wire into the existing regen + warn (exact edit)
`content_engine.py`, replace lines 709–719:

```python
from core.recency_claims import find_unsupported_recency_claims  # top of file

ungrounded = find_ungrounded_entities(script, grounding_text)
if _recency_guard_enabled():
    ungrounded = ungrounded + find_unsupported_recency_claims(
        script, grounding_text, datetime.date.today()
    )
if ungrounded:
    script, ungrounded = _maybe_reground_script(script, grounding_text, topic, ungrounded)
if ungrounded:
    logger.warning("Script has %d unsupported specific/recency claim(s): %s",
                   len(ungrounded), ", ".join(ungrounded))
```

`_maybe_reground_script`'s system prompt already says "remove or generalize every
flagged …" — extend that sentence to "… name, recency/superlative claim, or
version". The flagged recency sentences flow through unchanged.

### 1.5 Flags & tests
`RECENCY_CLAIM_GUARD=warn|reground|off` (default `warn`). New
`tests/test_recency_claims.py`:
- generic facts + "the most recent character" → 1 flag.
- facts containing "released June 2026" + same sentence → 0 flags (deferred).
- non-superlative prose → 0 flags (false-positive guard).
- end-to-end: `_maybe_reground_script` accepts a softened rewrite that drops the
  marker (reuse the existing reground test harness).

---

## §2 — ElevenLabs voice rotation

### 2.0 Acceptance
`tapin`/`moneywise` rotate across a curated pool instead of one voice; the same
voice is not used twice in a row; a single `voice_id` still pins (back-compat).

### 2.1 Current
`core/tts.py:47` `resolve_tts_config` returns `profile.tts_voice_id` **before** the
pool when it's set (lines 52–53); `config/channels.json` pins one voice on the two
production channels. `weighted_random_voice` (tts.py:34) is memoryless
`random.choice` → can repeat.

### 2.2 P1 — Config only (zero code, do first)
`config/channels.json`, replace on `tapin` and `moneywise`:

```jsonc
// before
"tts": { "voice_id": "nPczCjzI2devNBz1zQrb", "model_id": "eleven_multilingual_v2" }
// after — curate 2–4 on-brand voices
"tts": { "voice_pool": { "nPczCjzI2devNBz1zQrb": 3, "XjLkpWUlnhS8i7gGz3lZ": 2,
                         "JBFqnCBsd6RMkjVDRZzb": 1 },
         "model_id": "eleven_multilingual_v2" }
```

`resolve_tts_config` already routes a present `tts_voice_pool` through
`weighted_random_voice` (tts.py:55–56). This alone restores rotation.

### 2.3 P2 — Anti-repeat rotation (new `core/voice_rotation.py`)

```python
"""Anti-repeat voice selection: weighted pool, but never the last N voices.
JSON-backed per channel; fail-open (no/corrupt state → plain weighted pick)."""
from __future__ import annotations
import json, os, random
from config.paths import DATA_DIR

_STATE = os.path.join(DATA_DIR, "voice_state.json")

def _load() -> dict[str, list[str]]:
    try:
        with open(_STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save(state: dict) -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(_STATE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass

def pick_voice(channel_id: str, pool: dict[str, int], *, avoid_last: int = 1) -> str:
    state = _load()
    recent = state.get(channel_id, [])
    avoid = set(recent[-avoid_last:])
    candidates = {v: w for v, w in pool.items() if v not in avoid} or dict(pool)
    bag = [v for v, w in candidates.items() for _ in range(max(1, int(w)))]
    choice = random.choice(bag)
    state[channel_id] = (recent + [choice])[-5:]   # keep last 5
    _save(state)
    return choice
```

Modify `resolve_tts_config` (tts.py:55–56):

```python
if profile.tts_voice_pool:
    if os.getenv("VOICE_ROTATION", "weighted") != "off":
        from core.voice_rotation import pick_voice
        return pick_voice(channel_id, profile.tts_voice_pool), model_id
    return weighted_random_voice(profile.tts_voice_pool), model_id
```

`channel_id` is already resolved by the caller (`generate_audio` line 67–68); pass
it down (it's currently dropped into `resolve_tts_config(channel_id)` — already
available). Single `voice_id` path unchanged.

### 2.4 P3 — Brand-consistency guardrail (config discipline, no code)
Curate each pool as a **persona-aligned house set** (gender/tone matching
`channels.json` "persona"); keep a single `voice_id` escape hatch documented for a
channel that wants one signature voice. `config/validate_channels.py:89` already
warns when neither `voice_id` nor `voice_pool` is set — extend it to warn if a pool
has only one entry (defeats rotation).

### 2.5 Flags & tests
`VOICE_ROTATION=weighted|roundrobin|off` (default `weighted`). New
`tests/test_voice_rotation.py`:
- pool of 3 over 20 picks yields >1 distinct voice; `avoid_last=1` never returns the
  immediately-previous voice; corrupt/missing state → still returns a pool member;
  single-entry pool degrades gracefully; `voice_id` still pins.

---

## §3 — Within-video b-roll dedup

**Covered by the §5 spec.** `spec_background_query_entity_anchor.md` §3.5 (the
`exclude`/`variation` kwargs on `AssetProvider.find_video`) and §3.7 (threading a
growing `used` set across beats in `get_scene_matched_background`) *are* the §3 fix —
two beats can no longer return the same clip. The only piece **not** in the §5 spec
is the visual safety net, which is a render filter and lives in §4-C below
(`xfade` so even near-duplicate clips read as intentional motion). Implement §5's
provider threading; §3 needs no separate module.

---

## §4 — Production polish (exact FFmpeg filter graphs)

### 4.0 Acceptance
With flags on, the render gains a ducked music bed, normalized loudness, subtle
motion, and crossfades between scene clips; with flags off it is byte-for-byte
today's command. Missing music/SFX file → silent-bed render (never breaks).

### 4.1 Current
`video/render_video.py:51` `build_render_ffmpeg_command` — 2 inputs (bg, voice),
filter `scale/crop/setpts/subtitles`, maps TTS audio only, **no music/motion**.
`assets/composite.py:83` `build_multi_concat_command` — hard `concat`, `-an`.

### 4.2 A — Music bed + sidechain ducking + loudnorm  ⚠ verify on a real render
Add a 3rd input (per-channel `assets/music/{channel}/*.mp3`, looped) and replace the
filter graph + maps in `build_render_ffmpeg_command`:

```python
# inputs: 0=background, 1=voice mp3, 2=music (only when RENDER_MUSIC and a file exists)
# -stream_loop -1 -i <music>  added before output
filter_complex = (
    f"[0:v]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
    f"crop={TARGET_W}:{TARGET_H},setpts=PTS-STARTPTS,"
    f"subtitles='{subtitle_escaped}'[vout];"
    "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[voice];"
    "[voice]asplit=2[voice_mix][voice_sc];"
    "[2:a]volume=0.28[music];"
    "[music][voice_sc]sidechaincompress=threshold=0.03:ratio=6:attack=5:release=250[duck];"
    "[voice_mix][duck]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[aout]"
)
# -map "[vout]" -map "[aout]"   (instead of -map 1:a:0)
```

- `loudnorm` → consistent perceived volume across videos.
- `sidechaincompress` → music dips when the VO speaks (`release=250` ms feels natural).
- `duration=first` clamps to the voice length; overall `-t duration` unchanged.
- **No-music branch**: when `RENDER_MUSIC` is off or no file, keep today's
  `[...subtitles][vout]` + `-map 1:a:0` exactly (just `loudnorm` optional via
  `RENDER_LOUDNORM`). Branch in Python, not in the filter string.

### 4.3 B — Ken Burns + hook zoom  ⚠ verify on a real render
Insert before `subtitles` in `[0:v]` chain when `RENDER_KENBURNS=on`:

```
zoompan=z='min(zoom+0.0005,1.10)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':
        s={TARGET_W}x{TARGET_H}
```

Hook zoom (`HOOK_ZOOM=on`): a stronger push on the first ~1.5 s only — simplest as a
short `zoompan` with `d=` tied to `1.5*fps` then constant; spec a helper
`_motion_filter(duration)` returning the chain so it's unit-tested as a string.

### 4.4 C — `xfade` transitions between scene clips  ⚠ verify on a real render
Replace the `concat` tail of `build_multi_concat_command` (composite.py:108–113)
with chained `xfade`. With transition `td` (default 0.4 s) and per-clip durations
`d_i`, pad each segment by `td` upstream so the crossfade overlap preserves total
length, then:

```
# labels [v0]..[vN-1] already normalized (fps/scale/crop)
[v0][v1]xfade=transition=fade:duration=td:offset=(d0-td)[x1];
[x1][v2]xfade=transition=fade:duration=td:offset=(d0+d1-2*td)[x2];
...
[x(k-1)][vk]xfade=...:offset=(Σ d_0..d_{k-1} - k*td)[xk];
# final label [x(N-1)] → ...,format=yuv420p[vout]
```

Offset formula: `offset_k = (Σ_{j<k} d_j) - k*td`. Spec a pure helper
`build_xfade_filter(segments, td)` returning the filter string so the **offset math
is unit-tested without ffmpeg**; gate behind `SCENE_TRANSITIONS=xfade|none`
(default `none` until a render confirms it). Fallback to `concat` on any single
clip or when off.

### 4.5 D — Caption theme rotation (small)
`CAPTION_THEME_ROTATE=on`: pick a style preset (color/position/animation) per video
from a curated list keyed by a per-run seed, applied where `subtitles=`/ASS styling
is built (`video/subtitles.py`, `video/caption_timing.py`). Karaoke/keyword-pop
already exist; this only rotates the visual preset. Pure-function `pick_caption_theme(seed)`
→ unit-tested.

### 4.6 E — Data-driven hook archetype rotation (script-side sameness)
The deeper "bland" driver. Add a prompt knob: rotate the **opener archetype**
(question / bold-claim / stat-shock / contrarian) biased by the title-pattern
leaderboard already shipped (`core/title_experiments`, `core/title_features`). A
helper `suggested_hook_archetype(channel_id)` reads the leaderboard and injects one
line into the script prompt ("Open in the {archetype} style"). No new infra — reuses
the A/B title loop. Flag `HOOK_ARCHETYPE_ROTATE=on`.

### 4.7 Flags, tests, caveats
| Flag | Default | Lever |
|---|---|---|
| `RENDER_MUSIC` | `off` | music bed input + amix |
| `MUSIC_DUCKING` | `on` (when music) | sidechaincompress |
| `RENDER_LOUDNORM` | `off` | voice loudnorm |
| `RENDER_KENBURNS` | `off` | zoompan |
| `HOOK_ZOOM` | `off` | first-1.5s push |
| `SCENE_TRANSITIONS` | `none` | `xfade` between scenes |
| `CAPTION_THEME_ROTATE` | `off` | per-video caption preset |
| `HOOK_ARCHETYPE_ROTATE` | `off` | data-driven opener style |

Tests (string-level, no ffmpeg): `build_render_ffmpeg_command` includes the
3-input amix graph + `[aout]` map iff `RENDER_MUSIC` and a music file are passed,
and is **identical to today** when off; `build_xfade_filter` offset math for N=2,3,4;
`pick_caption_theme`/`suggested_hook_archetype` are deterministic for a fixed seed.
**Caveats:** (1) ⚠ each render filter needs one real-render eyeball before its flag
defaults on; (2) **music must be license-cleared** (Content-ID risk) — ship a
curated local library, document attribution; (3) longer encode — keep `-preset fast`.

---

## Cross-cutting sequencing (extends the plan's table)

| Step | Item | Effort | Risk | Notes |
|---|---|---|---|---|
| 1 | §2 P1 voice pool config swap | `[S]` | None | Zero code |
| 2 | §1 P1 superlative prompt rule | `[S]` | Low | One edit + PROMPT_VERSION |
| 3 | §4-A loudnorm only (`RENDER_LOUDNORM`) | `[S]` | Low | Audio consistency, no copyright |
| 4 | §1 P2–P3 recency detector + wire | `[M]` | Low | Mirrors fact_grounding |
| 5 | §2 P2 anti-repeat rotation | `[S]` | Low | data/voice_state.json |
| 6 | §4-A music bed + ducking | `[M]` | **Copyright** | Curated library first ⚠ render |
| 7 | §4-B/C Ken Burns + xfade | `[S–M]` | Low | ⚠ render-verify before default-on |
| 8 | §4-E hook archetype rotation | `[M]` | Low | Reuses title-pattern loop |

Each step is an independent PR with the tests listed above. None changes the
pipeline contract; all degrade to today's behavior when their flag is off.

## Cross-references
- §1: `core/content_engine.py` (692–719, 281–291), `core/fact_grounding.py`,
  `core/fact_recency.py`.
- §2: `core/tts.py`, `config/channels.py` (29–31, 96–98), `config/validate_channels.py`.
- §3: [spec_background_query_entity_anchor.md](spec_background_query_entity_anchor.md) §3.5/3.7.
- §4: `video/render_video.py` (51–104), `assets/composite.py` (83–136),
  `video/subtitles.py`, `core/title_experiments.py`.
