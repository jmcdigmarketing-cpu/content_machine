"""
Description extras — AI-content disclosure + alt-monetization CTAs.

YouTube's inauthentic-content policy lists "disclose AI usage" as a top
compliance step. The public Data API does not reliably expose the in-player
"altered/synthetic content" toggle, but YouTube accepts an **in-description
disclosure**, which we can set on every upload. We also append optional
channel-configured monetization CTAs (affiliate / sponsor lines), since
gaming/UFC is a low-CPM niche where ad revenue alone underperforms.

Config (per-channel `config/seo/{channel}.json`, all optional):
  "ai_disclosure":   "<custom disclosure line>"   # overrides the default
  "monetization_cta": ["line one", "line two"]    # appended verbatim

Env toggles:
  AI_DISCLOSURE_ENABLED   = true (default) | false
  DESCRIPTION_SEO_FIRST_LINE = true (default) | false
  FTC_DISCLOSURE          = true (default) | false  # only when monetization_cta is set
  DESCRIPTION_SOURCES     = true (default) | false  # vault source_url + pasted http(s)
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from config.seo import get_seo_profile
from core.logging import get_logger

logger = get_logger("core.description_extras")

DEFAULT_AI_DISCLOSURE = "Made with AI-assisted narration and editing."
DEFAULT_FINANCE_DISCLAIMER = (
    "Not financial advice. For informational purposes only. Do your own research."
)
DEFAULT_FTC_DISCLOSURE = (
    "Some links may be affiliate links. We may earn a commission at no extra cost to you."
)


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def ai_disclosure_line(channel_id: str) -> str:
    """The disclosure line for a channel, or '' when disabled."""
    if not _flag("AI_DISCLOSURE_ENABLED", True):
        return ""
    try:
        custom = get_seo_profile(channel_id).get("ai_disclosure")
    except Exception:
        custom = None
    return (custom or DEFAULT_AI_DISCLOSURE).strip()


def monetization_ctas(channel_id: str) -> list[str]:
    """Channel-configured monetization/affiliate CTA lines (may be empty)."""
    try:
        raw = get_seo_profile(channel_id).get("monetization_cta")
    except Exception:
        raw = None
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def finance_disclaimer_line(channel_id: str) -> str:
    """MoneyWise description disclaimer (separate from AI disclosure)."""
    if (channel_id or "").strip().lower() != "moneywise":
        return ""
    if not _flag("FINANCE_DISCLAIMER", True):
        return ""
    try:
        custom = get_seo_profile(channel_id).get("finance_disclaimer")
    except Exception:
        custom = None
    return (custom or DEFAULT_FINANCE_DISCLAIMER).strip()


def ftc_affiliate_line(channel_id: str, *, affiliate: bool = False) -> str:
    """FTC affiliate disclosure — copy only; #79 is the tracking spike. ``affiliate`` (#1748):
    the description carries an affiliate link, so the line is due with no CTA configured."""
    if not _flag("FTC_DISCLOSURE", True):
        return ""
    ctas = monetization_ctas(channel_id)
    if not ctas and not affiliate:
        return ""
    try:
        custom = get_seo_profile(channel_id).get("ftc_disclosure")
    except Exception:
        custom = None
    return (custom or DEFAULT_FTC_DISCLOSURE).strip()


_AFFILIATES_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "affiliates.json"
)


def affiliate_rows(channel_id: str) -> list[dict[str, Any]]:
    """The channel's `config/affiliates.json` rows (#1748), [] when unread."""
    try:
        with open(_AFFILIATES_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        logger.debug("affiliates.json unread: %s", exc)
        return []
    rows = data.get(channel_id) if isinstance(data, dict) else None
    from core.odds_language import is_gambling_link

    kept: list[dict[str, Any]] = []
    for row in rows or []:
        if not (isinstance(row, dict) and row.get("url") and row.get("keys")):
            continue
        if is_gambling_link(str(row["url"]), str(row.get("label") or "")):
            logger.warning(
                "affiliates.json: %s refused - no gambling link, ever (#1764)", row["url"]
            )
            continue
        kept.append(row)
    return kept


def subscribe_url(channel_id: str) -> str:
    """#1707 (decision 96): the channel's subscribe address, the confirm box open
    (`?sub_confirmation=1`) - "" until the metrics sync has stored the channel's id."""
    try:
        from core.ypp_readiness import load_ypp_numbers

        youtube_id = str((load_ypp_numbers(channel_id) or {}).get("youtube_channel_id") or "")
    except Exception as exc:
        logger.debug("channel id unread: %s", exc)
        return ""
    return f"https://www.youtube.com/channel/{youtube_id}?sub_confirmation=1" if youtube_id else ""


def subscribe_line(channel_id: str) -> str:
    """#1707: "Subscribe: <the subscribe address>" for a long video's description, or ""."""
    url = subscribe_url(channel_id)
    return f"Subscribe: {url}" if url else ""


TAG_PLACES = ("long", "tiktok", "instagram", "facebook")


def amazon_tag(place: str = "") -> str:
    """#1752 (decision 94): the Associates tracking ID for where a link sits - `long` (a long
    video's description) or a bio's link page (`tiktok`, `instagram`, `facebook`) - from
    AFFILIATE_AMAZON_TAGS ("long=name-yt-20,tiktok=name-tt-20"), else AFFILIATE_AMAZON_TAG.
    Amazon's report counts clicks and earnings per ID, so it says which place earned."""
    wanted = (place or "").strip().lower()
    for pair in os.getenv("AFFILIATE_AMAZON_TAGS", "").split(","):
        key, _sep, value = pair.partition("=")
        if wanted and key.strip().lower() == wanted and value.strip():
            return value.strip()
    return os.getenv("AFFILIATE_AMAZON_TAG", "").strip()


def _tagged(url: str, tag: str) -> str:
    """An Amazon link with the Associates tag, "" without one (#1747); any other link as is."""
    if "amazon." not in url.lower():
        return url
    if not tag:
        return ""
    return f"{url}{'&' if '?' in url else '?'}tag={tag}"


DEALS_KEYS = ("black friday", "cyber monday", "deals")
DEALS_LINKS = 3  # #1760 (decision 90): a deals video names several products


def is_deals(title: str, topic: str = "") -> bool:
    """A deals video: its title or topic names Black Friday, Cyber Monday or deals."""
    from core.playlists import _matches

    return _matches(f"{title or ''} {topic or ''}".lower(), list(DEALS_KEYS))


def affiliate_lines(
    channel_id: str, title: str, topic: str = "", *, long_form: bool, script: str = ""
) -> list[str]:
    """#1748 + #1747 (B07.1-2): one "<label>: <link>" for the first matching row, then the FTC
    line - on long-form only, since a Short's description links are not clickable. []
    otherwise, and for an Amazon row before AFFILIATE_AMAZON_TAG is set. #1760: a deals video
    takes up to `DEALS_LINKS`, matched in its script as well, and the `deals_only` rows (the
    consoles); one FTC line under them all."""
    if not long_form:
        return []
    from core.playlists import _matches

    deals = is_deals(title, topic)
    text = f"{title or ''} {topic or ''}" + (f" {script or ''}" if deals else "")
    text = text.lower()
    tag = amazon_tag("long")
    links: list[str] = []
    limit = DEALS_LINKS if deals else 1
    products: set[tuple[str, ...]] = set()
    for row in affiliate_rows(channel_id):
        if row.get("deals_only") and not deals:
            continue
        keys = tuple(str(k) for k in row.get("keys") or [])
        if not _matches(text, list(keys)):
            continue
        if deals and keys in products:
            continue  # #1749: a deals video names products - one edition each
        products.add(keys)
        url = _tagged(str(row["url"]), tag)
        if not url:
            continue
        if not links and not deals:  # #1749: the first match sets how many (GTA 6's two editions)
            limit = max(1, int(row.get("links") or 1))
        links.append(f"{str(row.get('label') or 'Link').strip()}: {url}")
        if len(links) >= limit:
            break
    if not links:
        return []
    ftc = ftc_affiliate_line(channel_id, affiliate=True)
    return [*links, *([ftc] if ftc else [])]


def ensure_seo_first_line(description: str, title: str = "") -> str:
    """First line is a search snippet (topic/title), not hashtags or Subscribe."""
    if not _flag("DESCRIPTION_SEO_FIRST_LINE", True):
        return description or ""
    body = (description or "").strip()
    headline = (title or "").strip()
    if not headline:
        return body
    first = body.splitlines()[0].strip() if body else ""
    weak = (
        not first
        or first.startswith("#")
        or first.lower().startswith("subscribe")
        or first.lower().startswith("http")
    )
    if not weak:
        return body
    if headline in body:
        return body
    return f"{headline}\n\n{body}" if body else headline


def collect_source_urls(
    *,
    channel_id: str = "",
    topic: str = "",
    key_facts: list[str] | None = None,
    extra_urls: list[str] | None = None,
    relevance_corpus: str = "",
    citations: list[str] | None = None,
) -> list[str]:
    """http(s) from operator paste + vault FactRecord.source_url. Deduped, capped.

    ``citations`` (#1589): the fact lines the claim check said backed a claim. When given, a
    key fact's or a vault record's URL is listed only if that fact backed one - run 196 listed
    four Week-6 links that backed nothing it said."""
    found: list[str] = []
    seen: set[str] = set()

    def _backed(text: str) -> bool:
        return citations is None or backs_a_claim(text, citations)

    from core.source_diversity import clean_urls, urls_from_text

    def _add(raw: str) -> None:
        for url in clean_urls([str(raw)]):
            key = url.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(url)

    for line in extra_urls or []:
        _add(str(line))
    for line in key_facts or []:
        if not _backed(str(line)):
            continue
        for url in urls_from_text(str(line)):
            _add(url)
    if channel_id and topic:
        try:
            from core.obsidian_facts import load_fact_records

            # Public citations use the same corpus as the scorer (signals + operator
            # facts), never the angle. `relevance_policy="public"` attaches only
            # confident records so a shared token like "wolverine" cannot put a
            # Marvel URL under a GTA video.
            for rec in load_fact_records(
                topic,
                channel_id,
                limit=24,
                require_distinctive=True,
                corpus=relevance_corpus,
                relevance_policy="public",
            ):
                if _backed(str(getattr(rec, "claim", "") or "")):
                    _add(getattr(rec, "source_url", "") or "")
        except Exception as exc:
            logger.debug("vault source_url collect skipped: %s", exc)
    return found[:8]


_CITE_PREFIX = re.compile(r"^(?:\d{4}-\d{2}-\d{2}\s*[·\-]\s*|as of [^:]{1,30}:\s*)", re.I)


def _cite_key(text: str) -> str:
    """A fact line as the claim check quotes it: no URL, no date or "as of" prefix, one case."""
    from core.source_diversity import urls_from_text

    body = str(text or "")
    for url in urls_from_text(body):
        body = body.replace(url, " ")
    body = _CITE_PREFIX.sub("", body.strip(" -—"))
    return " ".join(body.lower().split()).strip(" -—.")


def backs_a_claim(fact: str, citations: list[str]) -> bool:
    """#1589: `fact` is one of the lines the claim check cited for a supported claim."""
    key = _cite_key(fact)
    if len(key) < 12:
        return False
    for citation in citations or []:
        cite = _cite_key(citation)
        if len(cite) >= 12 and (cite in key or key[:80] in cite):
            return True
    return False


def format_sources_block(urls: list[str] | None) -> str:
    cleaned = [u.strip() for u in (urls or []) if str(u).strip()]
    if not cleaned:
        return ""
    lines = ["Sources:"]
    for url in cleaned[:8]:
        lines.append(url)
    return "\n".join(lines)


# #1051: what sits under the body, in the one order every writer uses. "notes" is the
# single-line block: AI disclosure, finance and affiliate disclaimers, CTAs.
BLOCK_ORDER = ("notes", "sources", "chapters", "footage")
_CHAPTER_START = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?\s+\S", re.M)


def join_blocks(body: str, blocks: list[str]) -> str:
    """The body, then each block that has text, with one blank line between them.

    Three writers each joined their own piece their own way, and the one that wrote most of
    it joined with a single newline - so on every video with sources (10 of the last 40),
    "Sources:" sat glued under the AI disclosure line. This is the only place a block is
    attached to a description.
    """
    parts = [str(p).strip("\n") for p in [body, *blocks] if p and str(p).strip()]
    return "\n\n".join(parts)


def block_order(description: str, channel_id: str) -> list[str]:
    """The `BLOCK_ORDER` names found in a description, in the order they appear."""
    text = description or ""
    found: dict[str, int] = {}
    disclosure = ai_disclosure_line(channel_id)
    if disclosure and disclosure in text:
        found["notes"] = text.index(disclosure)
    for name, needle in (("sources", "Sources:"), ("footage", "Footage:")):
        match = re.search(rf"^{needle}", text, re.M)
        if match:
            found[name] = match.start()
    chapter = _CHAPTER_START.search(text)
    if chapter:
        found["chapters"] = chapter.start()
    return [name for name, _at in sorted(found.items(), key=lambda kv: kv[1])]


def unglue_blocks(description: str) -> str:
    """A "Sources:" or "Footage:" block glued to the line above it gets its blank line (#1206).

    Run 132's description was written on 10-10, before `join_blocks` laid the blocks out, and
    went out on 10-15 with the pre-publish warning and the glue.
    """
    return re.sub(r"(?<=[^\n])\n(?=(?:Sources|Footage):)", "\n\n", description or "")


def layout_problem(description: str, channel_id: str) -> str:
    """Why a description's blocks are not laid out as `join_blocks` lays them, or "".

    Out of order, or a block glued to the line above it (no blank line before it).
    """
    text = description or ""
    order = block_order(text, channel_id)
    expected = [name for name in BLOCK_ORDER if name in order]
    if order != expected:
        return f"blocks are in the order {' > '.join(order)}; expected {' > '.join(expected)}"
    for name, pattern in (("sources", r"^Sources:"), ("footage", r"^Footage:")):
        match = re.search(pattern, text, re.M)
        if match and match.start() and not text[: match.start()].endswith("\n\n"):
            return f'"{name.capitalize()}:" is glued to the line above it'
    return ""


def playlist_line(channel_id: str, title: str, topic: str = "") -> str:
    """#1709 (B05.13): "More GTA: https://www.youtube.com/playlist?list=..." - the series playlist
    a Short joins (`playlists.playlists_for`), when the channel has made it. "" otherwise."""
    try:
        from core import playlists

        names = playlists.playlists_for(channel_id, title, topic=topic)
        if not names:
            return ""
        with open(playlists.store_path_for(channel_id), encoding="utf-8") as handle:
            ids = (json.load(handle) or {}).get("ids") or {}
        playlist_id = str(ids.get(names[0]) or "")
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        logger.debug("series playlist line skipped: %s", exc)
        return ""
    return (
        f"More {names[0]}: https://www.youtube.com/playlist?list={playlist_id}"
        if playlist_id
        else ""
    )


def apply_description_extras(
    description: str,
    channel_id: str,
    *,
    title: str = "",
    source_urls: list[str] | None = None,
    topic: str = "",
    key_facts: list[str] | None = None,
    relevance_corpus: str = "",
    length_choice: str = "",
    script: str = "",
    duration_s: float | None = None,
) -> str:
    """
    Append the AI disclosure and any monetization CTAs to a description.
    Idempotent — lines already present are not duplicated.
    """
    body = (description or "").rstrip()
    try:
        from core.odds_language import strip_betting_ctas, strip_gambling_links

        body, _n = strip_betting_ctas(body)
        body, _n = strip_gambling_links(body)  # #1764: always
    except Exception as exc:
        logger.debug("description betting-cta strip skipped: %s", exc)
    body = ensure_seo_first_line(body, title).rstrip()
    headline = (title or "").strip()
    if str(length_choice) == "4" and headline and body.splitlines()[:1] != [headline]:
        # #1741: a long video's first line is its title - the search phrase (#1856) - always
        body = f"{headline}\n\n{body}" if body else headline
    additions: list[str] = []  # the single-line notes
    sources_block = ""
    chapters_block = ""

    disclosure = ai_disclosure_line(channel_id)
    if disclosure and disclosure not in body:
        additions.append(disclosure)

    finance = finance_disclaimer_line(channel_id)
    if finance and finance not in body:
        additions.append(finance)

    ftc = ftc_affiliate_line(channel_id)
    if ftc and ftc not in body:
        additions.append(ftc)

    for cta in monetization_ctas(channel_id):
        if cta not in body and cta not in additions:
            additions.append(cta)

    # #1748: one affiliate link on a long video (preset "4"), with its FTC line; #1760: a deals
    # video up to three, read from its script too
    for line in affiliate_lines(
        channel_id, title, topic, long_form=str(length_choice) == "4", script=script
    ):
        if line not in body and line not in additions:
            additions.append(line)

    if str(length_choice) != "4":  # #1709: a Short's viewer finds the rest of its series
        series = playlist_line(channel_id, title, topic)
        if series and "playlist?list=" not in body and series not in additions:
            additions.append(series)

    if str(length_choice) == "4":  # #1707: a long video's viewer can subscribe in one click
        subscribe = subscribe_line(channel_id)
        if subscribe and subscribe not in body and subscribe not in additions:
            additions.append(subscribe)

    if _flag("DESCRIPTION_SOURCES", True):
        urls = list(source_urls or [])
        if not urls:
            urls = collect_source_urls(
                channel_id=channel_id,
                topic=topic or title,
                key_facts=key_facts,
                relevance_corpus=relevance_corpus,
            )
        block = format_sources_block(urls)
        if block and "Sources:" not in body:
            sources_block = block

    try:
        from core.chapters import chapter_block
        from core.series.long_form import chapter_keywords

        chapters = chapter_block(
            script,
            duration=duration_s,
            length_choice=length_choice,
            keywords=chapter_keywords(channel_id, topic) if topic else None,  # #1726
        )
        if chapters and "0:00" not in body:
            chapters_block = chapters
    except Exception as exc:
        logger.debug("chapter timestamps skipped: %s", exc)

    # #1051: BLOCK_ORDER, a blank line between blocks.
    return join_blocks(body, ["\n".join(additions), sources_block, chapters_block])


def add_footage_credits(description: str, credits: list[str] | None) -> str:
    """#1019: a "Footage:" block with the credits a clip licence requires; added once."""
    lines = [str(c).strip() for c in credits or [] if str(c).strip()]
    body = (description or "").rstrip()
    if not lines or "Footage:" in body:
        return body
    return join_blocks(body, ["Footage:\n" + "\n".join(lines)])


def persist_footage_credits(run_id: int | None, credits: list[str] | None) -> str | None:
    """Write the credits into the run row's description - the copy `main.py` queues
    (`core.chapters.current_description`). Returns the new description, or None."""
    if not run_id or not credits:
        return None
    try:
        from storage.repositories.content_runs import get_content_run_repository

        repo = get_content_run_repository()
        record = repo.get(int(run_id))
        if record is None:
            return None
        before = str(getattr(record, "description", "") or "")
        after = add_footage_credits(before, credits)
        if after == before.rstrip():
            return None
        repo.update(int(run_id), {"description": after})
        return after
    except Exception as exc:
        logger.warning("footage credits not written to run %s: %s", run_id, exc)
        return None
