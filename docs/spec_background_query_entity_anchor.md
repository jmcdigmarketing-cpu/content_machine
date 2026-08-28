# Implementation Spec — Entity-Anchored Background Queries

**Status: spec / planning-only (no code in this pass).** Implements **§5** of
[content_quality_plan.md](content_quality_plan.md) to a code-ready level: exact
files, signatures, near-final code, back-compat, env flags, and a test plan an
implementer can execute verbatim.

---

## 0. Goal & acceptance criteria

**Problem.** A "Cristiano Ronaldo" topic pulls generic football/gaming stock — the
**same clip every run** — because the subject entity is dropped in favor of a
hardcoded domain/category template.

**Done when:**
1. The resolved background query for `"Cristiano Ronaldo Champions League"`
   **contains the subject** ("Cristiano Ronaldo") and never the bare literal
   `"basketball football sports arena gameplay"` / `"video game gameplay screen"`.
2. A topic whose domain is unknown to the whitelist no longer collapses to the
   **channel's default-domain** template when a subject entity is present.
3. A keyword qualifies the query **only when bound to the topic** (token-overlap
   gate) — "Ronaldo" never anchors a non-Ronaldo video.
4. Two runs of the same topic can return **different clips** (bounded variation),
   and a new Ronaldo video does not reuse the **last** Ronaldo clip.
5. All behavior is **opt-in + fail-safe**: any failure path returns today's query;
   no render breaks. Full unit coverage; ruff/mypy clean.

**Non-goals.** Changing the provider chain order, the hybrid/scene-matched compose,
the LLM-query design (it stays the preferred path), or render filters (that's §4).

---

## 1. Current behavior (exact trace)

For topic `T = "Cristiano Ronaldo Champions League"`, channel `tapin` (domain
`gaming`):

```
render → assets.manager.get_background_asset
  → get_stock_background_asset(T)
    → _find_from_chain(T, detect_category(T)=?, chain)
       detect_category(T): no nba/nfl/.../gta keyword → "general"        [assets/category.py:1]
      → provider.find_video(T, "general", channel_id)                    [assets/manager.py:77]
        → query = assets.category.search_query(T, "general", ch)
          → resolve_background_query(T, "general", ch)                   [assets/background_query.py:130]
             llm_q = _llm_query(...)        # entity-aware IF enabled & not abstract
             rule_q = _rule_based_query(T, "general", ch):
                domain = infer_domain(T, ch)
                   no soccer branch → falls to channel default → "gaming"[apis/topic_scorer.py:260]
                domain "gaming" ∈ _DOMAIN_QUERIES → base="video game gameplay screen"
                entities=["Cristiano Ronaldo"] but base path returns
                   "Cristiano Ronaldo gameplay screen"  (weak) OR generic[background_query.py:87-91]
             query = llm_q or rule_q;  abstract? → rule_q                [background_query.py:139-144]
        → @lru_cache  ⇒ identical query every run                       [background_query.py:130]
        → Pexels: per_page=5, returns FIRST non-abstract vertical       [pexels_provider.py:35-57]
        → find_cached(query, name) ⇒ identical cached clip every run    [pexels_provider.py:27]
```

**Three static failure points** (all must be addressed):
- **F1 — entity discarded for a literal.** `_rule_based_query` sports/gaming
  branches (`background_query.py:93,95`) return fixed strings; the `general`
  fallback (line 97) is topic-derived but weak.
- **F2 — channel-default domain leak.** `infer_domain` returns the *channel's*
  domain when the topic matches no keyword (`topic_scorer.py:260`), so an
  off-domain subject inherits the wrong template. No soccer/tennis/F1 branch.
- **F3 — deterministic selection.** `@lru_cache` + `find_cached(query)` + "first
  result" ⇒ the same clip forever for a given topic.

---

## 2. Design principles (invariants the code must hold)

1. **Subject-anchored.** The extracted subject entity always leads the query;
   domain/category is a **suffix qualifier**, never a replacement.
2. **Whitelist-independent.** An unknown domain with a present entity must NOT fall
   to a channel-default template — trust the entity (+ the entity-aware LLM query).
3. **Topic-bound.** A token qualifies the query only if it appears in the topic
   (reuse the `rawg_api` token-overlap gate).
4. **Bounded variation.** Vary among already-fetched top-K results and remember
   recently-used clips per subject; never unbounded randomness.
5. **Fail-safe + opt-in.** Every new branch degrades to the current query/clip on
   any error or when its flag is off.

---

## 3. Component changes

### 3.1 New module — `assets/entity_extract.py`

Generalises the hardcoded `_extract_entities` (`background_query.py:65`) into a
reusable, tested subject extractor (no team-name allow-list).

```python
"""Extract the salient *subject* of a topic for footage search.

Subject = the proper-noun phrase the video is about ("Cristiano Ronaldo",
"Marvel Rivals", "GTA VI"). Used to anchor background-query construction so the
footage is about the subject, not a generic domain template.
"""
from __future__ import annotations
import re

# Multi-word proper noun ("Cristiano Ronaldo", "Champions League"), then single
# capitalised words. ALL-CAPS acronyms/initialisms (GTA, UFC) kept separately.
_PROPER = re.compile(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+")
_CAPWORD = re.compile(r"\b[A-Z][a-zA-Z]{2,}\b")
_ACRONYM = re.compile(r"\b[A-Z]{2,5}\b")
_VERSION = re.compile(r"\b[A-Z][A-Za-z]*\s*(?:[0-9]{1,3}|[IVX]{1,4})\b")  # GTA VI, FIFA 25

_STOP = frozenset({
    "The", "This", "That", "Video", "Trendy", "Finals", "Best", "Top", "New",
    "Why", "How", "What", "When", "Who",
})

def extract_subject(topic: str) -> str:
    """Best single subject phrase, or '' when none is confident."""
    topic = (topic or "").strip()
    if not topic:
        return ""
    for m in _PROPER.findall(topic):              # prefer multi-word proper nouns
        if m.split()[0] not in _STOP:
            return m
    for m in _VERSION.findall(topic):             # "GTA VI", "FIFA 25"
        return m.strip()
    caps = [w for w in _CAPWORD.findall(topic) if w not in _STOP and not w.isupper()]
    if caps:
        return caps[0]
    acr = [a for a in _ACRONYM.findall(topic)]    # last resort: a known-ish acronym
    return acr[0] if acr else ""

def subject_tokens(topic: str) -> list[str]:
    """All entity tokens for the topic-binding gate (lowercased, deduped)."""
    found: list[str] = []
    for m in (*_PROPER.findall(topic), *_CAPWORD.findall(topic), *_ACRONYM.findall(topic)):
        for tok in m.split():
            low = tok.lower()
            if low not in found and tok not in _STOP and len(low) > 1:
                found.append(low)
    return found
```

### 3.2 `apis/topic_scorer.py` — separate "confident" inference from channel-default

`infer_domain` currently conflates *topic-derived* domain with *channel-default*
fallback (line 260). Add a non-breaking sibling that reports the source. **Do not
change `infer_domain`'s signature** (many callers).

```python
def infer_domain_confident(topic, channel_id=None) -> tuple[str, bool]:
    """(domain, from_topic). from_topic=False means it fell back to the channel
    default and must NOT drive footage templates."""
    topic_lower = (topic or "").lower()
    # ... existing keyword branches, returning (dom, True) on each match ...
    # soccer/football quick win (still cheap, still hardcoded but complete):
    if _mentions(topic_lower, ["soccer", "football", "fifa", "uefa", "premier league",
                               "la liga", "champions league", "world cup", "messi",
                               "ronaldo", "mbappe", "haaland"]):
        return ("soccer", True)
    # ... tennis / f1 similarly (optional) ...
    dom = infer_domain(topic, channel_id)           # may be the channel default
    from_topic = dom not in ("neutral", _channel_default_domain(channel_id))
    return (dom, from_topic)
```

> `infer_domain` keeps returning the channel default for *weighting* (unchanged).
> Footage construction uses `infer_domain_confident` and ignores a non-`from_topic`
> domain. Add a `"soccer"` (+ optional `tennis`/`f1`) entry to `_DOMAIN_QUERIES`.

### 3.3 `assets/background_query.py` — entity-first rule query (fixes F1+F2)

Rewrite `_rule_based_query`; keep `resolve_background_query` and `_llm_query` shape.

```python
from assets.entity_extract import extract_subject, subject_tokens
from apis.topic_scorer import infer_domain_confident

# Generic qualifiers appended to a SUBJECT — never returned standalone.
_DOMAIN_SUFFIX = {
    "nba": "basketball highlights", "nfl": "football highlights",
    "ufc": "mma fight", "soccer": "soccer match highlights",
    "gaming": "gameplay", "tennis": "tennis match", "f1": "formula 1 race",
}
_CATEGORY_SUFFIX = {"sports": "sports highlights", "gaming": "gameplay"}

def _rule_based_query(topic: str, category: str, channel_id) -> str:
    subject = extract_subject(topic)
    domain, from_topic = infer_domain_confident(topic, channel_id)
    qualifier = ""
    if from_topic and domain in _DOMAIN_SUFFIX:
        qualifier = _DOMAIN_SUFFIX[domain]
    elif category in _CATEGORY_SUFFIX:
        qualifier = _CATEGORY_SUFFIX[category]

    if subject:                                   # INVARIANT 1: subject leads
        return f"{subject} {qualifier}".strip()
    if qualifier:                                 # only generic when NO subject
        return qualifier
    # final fallback: topic words (today's behavior)
    words = [w for w in re.findall(r"[a-z0-9]{3,}", topic.lower())
             if w not in ("the", "and", "for", "with", "video", "trendy", "about")]
    return " ".join(words[:5]) or topic[:40]
```

Result for the Ronaldo case: `"Cristiano Ronaldo soccer match highlights"` — subject
anchored, soccer-qualified, never the gaming/literal generic.

### 3.4 Topic-binding gate (Invariant 3)

Generalise the rawg overlap helper rather than duplicate it. In
`apis/rawg_api.py`, `_sig_tokens` already exists; **export it** (rename usage, keep
behavior) or add a thin `core/text_match.py` with `sig_tokens()` and:

```python
def entity_in_topic(entity: str, topic: str, *, threshold: float = 0.5) -> bool:
    """True iff most of `entity`'s significant tokens appear in `topic`."""
    et, tt = sig_tokens(entity), set(sig_tokens(topic))
    if not et:
        return False
    return sum(t in tt for t in et) / len(et) >= threshold
```

`resolve_background_query` (strict mode only) drops a subject that fails
`entity_in_topic(subject, topic)` before building the query — so an entity injected
from elsewhere can't anchor an unrelated video. Default `warn` (log only) first.

### 3.5 Variation + exclude threading (fixes F3)

**ABC change** — `assets/base.py`:

```python
@abstractmethod
def find_video(self, topic, category, channel_id=None, *,
               exclude: set[str] | None = None, variation: int = 0) -> Optional[AssetResult]:
    ...
```

`exclude` = clip `source_id`s already used; `variation` = rotation offset into the
top-K. **Pexels** (`pexels_provider.py`) — the fetch already returns 5; change only
the selection:

```python
def find_video(self, topic, category, channel_id=None, *, exclude=None, variation=0):
    exclude = exclude or set()
    query = search_query(topic, category, channel_id)
    cached = find_cached(query, self.name)
    if cached and _cached_source_id(cached) not in exclude:   # skip excluded cache
        return AssetResult(path=cached, provider=self.name, query=query, source_id="cached")
    # ... request per_page=5 (already) ...
    candidates = [v for v in videos
                  if not is_abstract_stock_text(...) and str(v.get("id")) not in exclude]
    if not candidates:
        return None
    video = candidates[variation % len(candidates)]          # bounded rotation
    # ... download/register/return as today ...
```

`variation` is derived deterministically per render so a *given* video is stable but
*successive* videos differ: `variation = day_of_year + scene_index` (or a per-run
seed). `PixabayAssetProvider` and `LocalAssetProvider` take the same kwargs;
`Local` may ignore `variation` but must honor `exclude`. All callers pass nothing →
defaults preserve today's behavior (back-compat).

### 3.6 Cross-video clip memory — `assets/broll_history.py` (new)

```python
"""Remember recently-used clip ids per (channel, subject) so successive videos on
the same subject don't reuse the same footage. JSON-backed, capped, TTL'd."""
# data/broll_history.json: {"tapin::cristiano ronaldo": [{"id": "12345", "ts": ...}, ...]}

def recent_clip_ids(channel_id: str, subject: str, *, within_days: int = 30) -> set[str]: ...
def record_clip(channel_id: str, subject: str, source_id: str, *, cap: int = 20) -> None: ...
```

Fail-open (missing/corrupt file → empty set). Flag `BROLL_HISTORY=on`.

### 3.7 Wire into the manager

- **Scene-matched** (`assets/manager.get_scene_matched_background`, line ~204):
  build a `used: set[str]` across beats; pass `exclude=used | recent_clip_ids(...)`
  and `variation=scene_index`; after each pick `used.add(clip.source_id)` +
  `record_clip(...)`. This also subsumes §3 (within-video dedup).
- **Single background** (`get_stock_background_asset`): pass
  `exclude=recent_clip_ids(channel, subject)` and a per-run `variation`; `record_clip`
  on success.

Thread `exclude`/`variation` through `_find_from_chain` (add the two kwargs,
default `None`/`0`, forward to `provider.find_video`).

---

## 4. Environment flags

| Flag | Default | Effect |
|---|---|---|
| `BACKGROUND_ENTITY_ANCHOR` | `on` | entity-first rule query (§3.3); `off` = today's `_rule_based_query` |
| `BACKGROUND_TOPIC_BIND` | `warn` | `strict` drops topic-unbound subjects (§3.4); `warn` logs; `off` skip |
| `BACKGROUND_QUERY_VARIATION` | `off` | top-K rotation (§3.5) |
| `BROLL_HISTORY` | `off` | cross-video clip memory (§3.6) |
| `BACKGROUND_QUERY_LLM` | `true` (exists) | unchanged; remains preferred path |

Rollout: ship `ENTITY_ANCHOR=on` + `TOPIC_BIND=warn` first (pure quality, low risk);
enable `VARIATION`/`BROLL_HISTORY` once the anchor change is validated on real runs.

---

## 5. Test plan

New `tests/test_background_query_entity.py`:
- `extract_subject("Cristiano Ronaldo Champions League") == "Cristiano Ronaldo"`
- `extract_subject("GTA VI trailer breakdown")` → `"GTA VI"`; `extract_subject("trendy video")` → `""`
- `_rule_based_query("Cristiano Ronaldo ...", "general", "tapin")` **contains** `"Ronaldo"`
  and **not** `"video game gameplay"` (F1+F2 regression — the headline bug).
- unknown-domain + subject does not return a channel-default template (F2).
- no-subject topic still falls back to qualifier/topic words (back-compat).
- `infer_domain_confident("Messi ...", "tapin")` → `("soccer", True)`;
  `infer_domain_confident("random thing", "tapin")` → `(_, False)`.

`tests/test_entity_topic_bind.py`:
- `entity_in_topic("Cristiano Ronaldo", "Ronaldo signs new deal")` → True
- `entity_in_topic("Ronaldo", "World Cup final preview")` → False

`tests/test_broll_variation.py`:
- provider with 3 candidates: `variation=0,1,2` return distinct `source_id`s;
  `exclude={id0}` never returns `id0`; all-excluded → `None` (clean fallback).
- `broll_history.record_clip` then `recent_clip_ids` returns it; cap + TTL honored;
  corrupt file → empty set (fail-open).

`tests/test_scene_plan.py` (extend): scene loop passes a growing `exclude`; two
identical-query beats yield distinct clips (ties to §3).

CI: `ruff check . && ruff format --check .` clean; new modules typed for mypy.

---

## 6. Risks, fallbacks, sequencing

| Risk | Mitigation |
|---|---|
| Entity-anchored query returns thinner stock results | Keep qualifier suffix; provider chain (local→Pexels→Pixabay) absorbs misses; generic remains the *no-subject* fallback |
| `extract_subject` false positive (caps mid-sentence) | `_STOP` list + prefer multi-word proper nouns; `warn`-mode topic-bind catches drift before `strict` |
| ABC signature change breaks a provider | Keyword-only args with defaults; update all three providers in the same change; tests assert back-compat call (no kwargs) |
| Variation re-introduces an abstract clip | Abstract filter runs *before* candidate selection (unchanged) |

**Build order:** 3.1 → 3.2 → 3.3 (ship, validate) → 3.4 → 3.5 → 3.6/3.7. Each is an
independent PR with its tests, per [decisions.md](decisions.md) §11.

---

## 7. Manual validation (post-implementation)

```bash
# query-resolution unit check (no network)
python -m pytest tests/test_background_query_entity.py -q
# eyeball the resolved query for a cross-domain subject
python -c "from assets.background_query import resolve_background_query as r; \
print(r('Cristiano Ronaldo Champions League','general','tapin'))"
# expect: contains 'Cristiano Ronaldo', not 'video game gameplay'
```

Then a real render on a Ronaldo topic with `BACKGROUND_QUERY_VARIATION=on` twice;
confirm two different clips and subject-relevant footage.
