"""Read the pages the pipeline already found, for the chosen angle (#848).

Run 98: the web_search signal returned six results with URLs, and nothing ever opened
them - the only pages read were the ones the operator pasted by hand. This reads the
top result pages after the angle is chosen, keeps the lines that touch the angle or
topic (`fact_selection.flag_off_topic`, the same lenient rule pasted links get), and
attaches them as a `web_research` signal.

Deliberately small in authority:
- web tier, never operator; never pinned; saved to the vault only with
  `AUTO_RESEARCH_SAVE=true`, and then to `_link_facts/` at link tier (#862);
- score 0, so the composite and the angle tie never move;
- no new paid call: it reuses the search that already ran;
- bounded: `AUTO_RESEARCH_URLS` pages under `AUTO_RESEARCH_DEADLINE_S`, a per-URL
  3-hour cache so the regenerate loop does not refetch; never raises.

On by default (operator decision 2026-09-26); `AUTO_RESEARCH_ENABLED=false` turns it off.
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Any

from apis.cache_manager import build_key, get_cached, set_cache
from apis.signal_contract import STATUS_OK, make_signal
from core.logging import get_logger

logger = get_logger("core.auto_research")

SIGNAL_NAME = "web_research"
_CACHE_TTL = 3 * 60 * 60


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(os.getenv(name, str(default)) or default)))
    except ValueError:
        return default


def _deadline_s() -> float:
    try:
        return max(0.1, float(os.getenv("AUTO_RESEARCH_DEADLINE_S", "20") or 20))
    except ValueError:
        return 20.0


def _candidate_urls(signals: dict[str, Any], exclude: set[str]) -> list[dict[str, str]]:
    sig = (signals or {}).get("web_search") or {}
    if not (isinstance(sig, dict) and sig.get("active")):
        return []
    data = sig.get("data") or {}
    results = data.get("results") if isinstance(data, dict) else None
    from core.link_facts import _is_blocked_url

    out: list[dict[str, str]] = []
    for r in results or []:
        if not isinstance(r, dict):
            continue
        url = str(r.get("url") or "").strip()
        low = url.lower()
        if not url.startswith("http") or url in exclude:
            continue
        if "youtube.com" in low or "youtu.be" in low or _is_blocked_url(url):
            continue
        out.append(
            {"url": url, "title": str(r.get("title") or ""), "snippet": str(r.get("snippet") or "")}
        )
    return out


def _rank(candidates: list[dict[str, str]], reference: str) -> list[dict[str, str]]:
    """Result order, nudged by title/snippet overlap with the angle and topic."""
    from apis.topic_tokens import content_tokens

    ref = set(content_tokens(reference))

    def overlap(c: dict[str, str]) -> int:
        return len(ref & set(content_tokens(f"{c['title']} {c['snippet']}")))

    indexed = list(enumerate(candidates))
    indexed.sort(key=lambda item: (-overlap(item[1]), item[0]))
    return [c for _, c in indexed]


def _read(url: str) -> list[str]:
    key = build_key("web_research_url", url)
    cached = get_cached(key)
    if isinstance(cached, list):
        return [str(x) for x in cached]
    from core.link_facts import _article_extract

    lines, _meta = _article_extract(url)
    set_cache(key, list(lines), ttl_seconds=_CACHE_TTL)
    return list(lines)


def _news_fallback(
    base: dict[str, Any], report: dict[str, Any], *, angle: str, topic: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """#964: no web search results (no key, or the vault skip) - read Google News headlines
    that name the topic's subject instead of nothing. Keyless; `AUTO_RESEARCH_NEWS_FALLBACK=
    false` turns it off."""
    from core.providers import flag_enabled

    if not flag_enabled("AUTO_RESEARCH_NEWS_FALLBACK", default=True):
        return base, report
    try:
        from core.event_coverage import event_name
        from core.event_research import google_news_headlines

        name = event_name(topic) or event_name(angle)
        lines = google_news_headlines(name)[: _env_int("AUTO_RESEARCH_MAX_LINES", 20, 1, 80)]
    except Exception as exc:
        logger.debug("news fallback skipped: %s", exc)
        return base, report
    if not lines:
        return base, report
    before = str(report.get("reason") or "")
    reason = "news fallback" if before in ("", "no web results") else f"news fallback ({before})"
    report.update(reason=reason, lines=len(lines), kept_lines=list(lines))
    base[SIGNAL_NAME] = make_signal(
        connected=True,
        active=True,
        score=0,
        confidence=0.5,
        status=STATUS_OK,
        status_detail=f"Auto-research: {len(lines)} Google News headline(s) naming {name!r}",
        data={"lines": lines, "urls": []},
    )
    return base, report


def attach_web_research(
    signals: dict[str, Any] | None,
    *,
    angle: str,
    topic: str,
    exclude_urls: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """(a copy of `signals` plus `web_research`, a report). Never raises."""
    base = dict(signals or {})
    report: dict[str, Any] = {"pages": 0, "lines": 0, "off_topic": 0, "urls": [], "reason": ""}
    try:
        reference = "\n".join(p for p in (angle, topic) if p)
        candidates = _rank(_candidate_urls(base, set(exclude_urls or [])), reference)
        if not candidates:
            report["reason"] = "no web results"
            return _news_fallback(base, report, angle=angle, topic=topic)
        chosen = candidates[: _env_int("AUTO_RESEARCH_URLS", 3, 1, 6)]
        deadline = _deadline_s()
        started = time.monotonic()
        pages: dict[str, list[str]] = {}
        executor = ThreadPoolExecutor(max_workers=len(chosen))
        futures = {executor.submit(_read, c["url"]): c["url"] for c in chosen}
        try:
            for future in as_completed(futures, timeout=deadline):
                url = futures[future]
                try:
                    pages[url] = future.result()
                except Exception as exc:
                    logger.debug("auto-research read failed for %s: %s", url, exc)
        except FuturesTimeout:
            report["reason"] = "deadline"
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        from core.facts.selection import flag_off_topic
        from core.vault.relevance import build_relevance_corpus

        corpus = build_relevance_corpus(base, include_web=True)
        cap = _env_int("AUTO_RESEARCH_MAX_LINES", 20, 1, 80)
        kept: list[str] = []
        used_urls: list[str] = []
        off = 0
        for c in chosen:  # ranked order, not completion order
            lines = pages.get(c["url"]) or []
            if not lines:
                continue
            flagged = set(flag_off_topic(lines, reference=reference, corpus=corpus))
            off += len(flagged)
            took = False
            for line in lines:
                if line in flagged or line in kept or len(kept) >= cap:
                    continue
                kept.append(line)
                took = True
            if took:
                used_urls.append(c["url"])
        report.update(
            pages=len([u for u in pages if pages[u]]),
            lines=len(kept),
            off_topic=off,
            urls=used_urls,
            kept_lines=list(kept),
            seconds=round(time.monotonic() - started, 1),
        )
        if not report["reason"]:
            report["reason"] = "ok" if kept else "nothing on-topic"
        if not kept:
            # #972: run 113 read 0 pages before the deadline and kept nothing.
            return _news_fallback(base, report, angle=angle, topic=topic)
        if kept:
            base[SIGNAL_NAME] = make_signal(
                connected=True,
                active=True,
                score=0,
                confidence=0.6,
                status=STATUS_OK,
                status_detail=f"Auto-research: {len(kept)} line(s) from {len(used_urls)} page(s)",
                data={"lines": kept, "urls": used_urls},
            )
        return base, report
    except Exception as exc:  # fail-open: research is a bonus, never a blocker
        logger.debug("auto-research skipped: %s", exc)
        report["reason"] = f"error: {exc}"
        return base, report


def save_kept_lines(
    channel_id: str, topic: str, report: dict[str, Any] | None, *, today: Any = None
) -> str | None:
    """Write a report's kept lines to the vault's `_link_facts/` (#862). Never raises.

    Link tier, never operator: nobody reviewed these lines. The note gets its own
    `-auto-research` file name so it cannot replace a pasted-link note of the same day.
    """
    kept = [str(line) for line in (report or {}).get("kept_lines") or [] if str(line).strip()]
    if not kept:
        return None
    try:
        from core.operator_facts import capture_facts_to_vault

        return capture_facts_to_vault(
            channel_id,
            topic,
            kept,
            today=today,
            tier="link",
            origin="auto-research",
            sources=[str(u) for u in (report or {}).get("urls") or []],
        )
    except Exception as exc:
        logger.debug("auto-research save skipped: %s", exc)
        return None


def maybe_save_research(channel_id: str, topic: str, report: dict[str, Any] | None) -> None:
    """Save the kept lines when `AUTO_RESEARCH_SAVE` is on; record where in the report."""
    from core.providers import flag_enabled

    if not report or not flag_enabled("AUTO_RESEARCH_SAVE", default=False):
        return
    path = save_kept_lines(channel_id, topic, report)
    if path:
        report["saved_to"] = path


def report_line(report: dict[str, Any] | None) -> str:
    """One operator-facing line for the run summary."""
    if not report:
        return ""
    reason = str(report.get("reason") or "")
    if reason in ("no web results", ""):
        return "Auto-research: no web results to read"
    if reason.startswith("news fallback"):
        why = reason[len("news fallback") :].strip(" ()") or "no web results"
        return (
            f"Auto-research: {why} - read {report.get('lines', 0)} Google News headline(s) instead"
        )
    return (
        f"Auto-research: {report.get('pages', 0)} page(s) read, {report.get('lines', 0)} line(s) kept, "
        f"{report.get('off_topic', 0)} off-topic dropped"
        + (" (deadline hit)" if reason == "deadline" else "")
    )


def report_lines(report: dict[str, Any] | None, *, show: int = 5) -> list[str]:
    """The summary line plus the kept lines themselves (#861); old reports: header only."""
    header = report_line(report)
    if not header:
        return []
    kept = [str(line) for line in (report or {}).get("kept_lines") or [] if str(line).strip()]
    out = [header]
    out.extend(f"  - {line[:160]}" for line in kept[:show])
    if len(kept) > show:
        out.append(f"  (+{len(kept) - show} more)")
    saved = str((report or {}).get("saved_to") or "")
    if saved:
        out.append(f"  saved to vault: {saved}")
    return out
