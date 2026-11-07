"""What the money buys (wave 158).

- #1800 (B09.4) ElevenLabs' plan sized to the month's characters. Nothing counted them: the
  character ledger is fed only when `ELEVENLABS_MONTHLY_CHAR_BUDGET` is set (opt-in, decided
  2026-08-20; it is not set - Sep, Oct and Nov read 0), and the API key has no `user_read`
  permission (401 on `/v1/user/subscription`). Each run records its voice cost (`features.cost.tts`,
  characters x `COST_TTS_PER_1K_CHARS`), so the month's characters are that cost back over the rate.
  The month's pace against `config/plans.json` names the smallest plan that covers it with 10%
  headroom, and when the current one (`COST_TTS_PLAN_CHARS` / `COST_TTS_PLAN_USD`, default Creator)
  runs out.
- #1807 (B09.11) each monthly subscription in the spend ledger with what it bought this month -
  the runs' voice, LLM, Apify and search use - and the one to cut first: nothing measured against
  it, else the most dollars a run.
"""

from __future__ import annotations

import calendar
import json
import os
from datetime import date, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger("core.money.plans")

_PLANS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
    "plans.json",
)
HEADROOM = 1.1
_USES = ("tts", "llm", "apify", "web_search")
_USE_WORDS = {"tts": "voice", "llm": "LLM", "apify": "Apify", "web_search": "search"}
_MATCH = (
    ("tts", ("eleven", "voice", "tts")),
    ("llm", ("openrouter", "deepseek", "openai", "anthropic", "claude", "gpt", "llm")),
    ("apify", ("apify",)),
    ("web_search", ("serp", "search", "tavily", "brave", "exa")),
)


def elevenlabs_plans() -> list[dict[str, Any]]:
    """The plans by characters, smallest first."""
    try:
        with open(_PLANS_FILE, encoding="utf-8") as handle:
            rows = (json.load(handle) or {}).get("elevenlabs") or []
    except (OSError, ValueError, AttributeError) as exc:
        logger.debug("plans.json unread: %s", exc)
        rows = []
    good = [r for r in rows if isinstance(r, dict) and int(r.get("chars") or 0) > 0]
    return sorted(good, key=lambda r: int(r["chars"]))


def _tts_rate() -> float:
    try:
        from core.cost_meter import TTS_RATE_DEFAULT, TTS_RATE_ENV, _rate

        return float(_rate(TTS_RATE_ENV, TTS_RATE_DEFAULT))
    except Exception:
        return 0.22


def _created(run: Any) -> date | None:
    raw = getattr(run, "created_at", None)
    if isinstance(raw, datetime):
        return raw.date()
    try:
        return date.fromisoformat(str(raw or "")[:10])
    except ValueError:
        return None


def month_use(today: date, runs: list[Any] | None = None) -> dict[str, Any]:
    """{tts, llm, apify, web_search (dollars), runs, voiced, chars} for `today`'s calendar month,
    from every channel's runs."""
    if runs is None:
        from config.channels import list_channel_ids
        from storage.repositories.content_runs import get_content_run_repository

        repo = get_content_run_repository()
        runs = [r for c in list_channel_ids() for r in repo.list_for_channel(c) or []]
    out: dict[str, Any] = dict.fromkeys(_USES, 0.0)
    out.update(runs=0, voiced=0)
    for run in runs:
        made = _created(run)
        if made is None or (made.year, made.month) != (today.year, today.month) or made > today:
            continue
        try:
            cost = (json.loads(getattr(run, "features_json", "") or "{}") or {}).get("cost") or {}
        except (TypeError, ValueError):
            continue
        if not isinstance(cost, dict):
            continue
        out["runs"] += 1
        for use in _USES:
            try:
                out[use] += float(cost.get(use) or 0)
            except (TypeError, ValueError):
                continue
        if float(cost.get("tts") or 0) > 0:
            out["voiced"] += 1
    rate = _tts_rate()
    out["chars"] = round(out["tts"] / rate * 1000) if rate > 0 else 0
    return out


def _current_plan(plans: list[dict[str, Any]]) -> dict[str, Any]:
    from core.unit_economics import _plan_chars, _plan_usd

    chars, usd = _plan_chars(), _plan_usd()
    named = next((p for p in plans if int(p["chars"]) == chars), None)
    return {"name": named["name"] if named else "your plan", "chars": chars, "usd": usd}


def plan_fit(
    chars: int, today: date, plans: list[dict[str, Any]], current: dict[str, Any]
) -> dict[str, Any]:
    """{pace, fits, runs_out} - the month's pace at today's rate, the smallest plan that covers it
    with `HEADROOM`, and the day the current plan's characters run out (None when they do not)."""
    days = calendar.monthrange(today.year, today.month)[1]
    pace = round(chars / max(1, today.day) * days)
    fits = next(
        (p for p in plans if int(p["chars"]) >= pace * HEADROOM), plans[-1] if plans else None
    )
    runs_out = None
    per_day = chars / max(1, today.day)
    if per_day > 0 and pace > int(current["chars"]):
        day = int(int(current["chars"]) / per_day) + 1
        runs_out = date(today.year, today.month, min(days, max(1, day)))
    return {"pace": pace, "fits": fits, "runs_out": runs_out}


def plan_line(*, today: date | None = None, use: dict[str, Any] | None = None) -> str:
    """#1800: "ElevenLabs: ~31,000 characters by Nov 6 ... the Creator plan covers it", or ""."""
    day = today or date.today()
    plans = elevenlabs_plans()
    if not plans:
        return ""
    found = use if use is not None else month_use(day)
    chars = int(found.get("chars") or 0)
    current = _current_plan(plans)
    fit = plan_fit(chars, day, plans, current)
    head = (f"ElevenLabs (#1800): ~{chars:,} characters by {day:%b} {day.day} ({found.get('voiced', 0)} "
            f"voiced runs) - on pace for ~{fit['pace']:,} this month")  # fmt: skip
    best = fit["fits"]
    if fit["runs_out"] is not None:
        tail = (f"; the {current['name']} plan ({int(current['chars']):,}, ${float(current['usd']):g}) "
                f"runs out about {fit['runs_out']:%b} {fit['runs_out'].day}")  # fmt: skip
        if best and int(best["chars"]) > int(current["chars"]):
            tail += f" - {best['name']} ({int(best['chars']):,}, ${float(best['usd']):g}) covers it"
        return head + tail
    if best and float(best["usd"]) < float(current["usd"]):
        save = float(current["usd"]) - float(best["usd"])
        return (head + f"; {best['name']} ({int(best['chars']):,}, ${float(best['usd']):g}) covers it - "
                f"${save:g} a month less than {current['name']} (${float(current['usd']):g})")  # fmt: skip
    return head + f"; the {current['name']} plan ({int(current['chars']):,}) covers it"


def money_plan_lines(*, today: date | None = None) -> list[str]:
    """#1800 / #1807: the voice plan against the month's pace, then each subscription with what it
    bought - for `ops spend` and the weekly report. Never raises: [] when unread."""
    day = today or date.today()
    try:
        use = month_use(day)
        return [line for line in (plan_line(today=day, use=use),
                                  *subscription_lines(today=day, use=use)) if line]  # fmt: skip
    except Exception as exc:
        logger.debug("money plan lines skipped: %s", exc)
        return []


def _use_of(what: str) -> str:
    low = (what or "").lower()
    return next((use for use, words in _MATCH if any(w in low for w in words)), "")


def _monthly(entries: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    out = []
    for row in entries:
        if row.get("kind") != "subscription" or not row.get("monthly"):
            continue
        start, ended = str(row.get("date") or ""), str(row.get("ended") or "")
        if start[:10] > today.isoformat() or (ended and ended[:7] < f"{today:%Y-%m}"):
            continue
        out.append(row)
    return out


def subscription_lines(
    *,
    today: date | None = None,
    entries: list[dict[str, Any]] | None = None,
    use: dict[str, Any] | None = None,
) -> list[str]:
    """#1807: each running monthly subscription with what it bought this month, then the one to
    cut first. With none entered, what the runs used this month and how to enter one."""
    day = today or date.today()
    if entries is None:
        from core.money.ledger import entries as ledger_entries

        entries = list(ledger_entries())
    found = use if use is not None else month_use(day)
    subs = _monthly(entries, day)
    spent = " · ".join(f"{_USE_WORDS[u]} ${float(found.get(u) or 0):,.2f}" for u in _USES
                       if float(found.get(u) or 0) > 0) or "nothing paid"  # fmt: skip
    if not subs:
        return [f"Subscriptions (#1807): none entered - this month's {found.get('runs', 0)} runs used "
                f"{spent}. Enter each plan once: py -m scripts.ops spend add --kind subscription "
                "--monthly --amount N --what NAME"]  # fmt: skip
    lines = [f"Subscriptions (#1807), {day:%B}:"]
    worst: tuple[float, str] | None = None
    idle: list[str] = []
    for row in subs:
        name, usd = str(row.get("what") or "?"), float(row.get("amount") or 0)
        use_key = _use_of(name)
        runs = int(found.get("voiced" if use_key == "tts" else "runs") or 0)
        bought = float(found.get(use_key) or 0) if use_key else 0.0
        if not use_key or bought <= 0:
            lines.append(f"  {name} ${usd:,.2f}/mo - nothing measured against it this month")
            idle.append(name)
            continue
        extra = f", ~{int(found['chars']):,} characters" if use_key == "tts" else ""
        per_run = usd / runs if runs else usd
        lines.append(f"  {name} ${usd:,.2f}/mo - {runs} runs used ${bought:,.2f} of "
                     f"{_USE_WORDS[use_key]}{extra} (${per_run:,.2f} a run)")  # fmt: skip
        if worst is None or per_run > worst[0]:
            worst = (per_run, name)
    if idle:
        lines.append(f"  Cut first: {idle[0]} - nothing this month used it")
    elif worst is not None:
        lines.append(f"  Cut first: {worst[1]} - ${worst[0]:,.2f} a run, the most of these")
    return lines
