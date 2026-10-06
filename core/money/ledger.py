"""Total money spent on the project, at startup, in `ops status` and the app (#980).

Operator, 2026-10-06: "can i also get a total money spent across everything with the project in
entirety when i boot up". Each run stores an estimate of what it used (`features["cost"]`),
`ops cost-tower` shows quotas and `ops economics` cost per video, but nothing added up money
actually paid: subscriptions, credit top-ups, ads. None of that is in an API, so each payment is
entered once (`py -m scripts.ops spend add`) into `data/spend_ledger.json`:

- a one-off counts once (an ad campaign, a credit top-up);
- a `monthly` entry counts each month it has started in, from its date until it is ended.

What the runs used (`run_usage`) is shown beside the total and never added to it - it was paid
for by those same credits and subscriptions.
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.money.ledger")

LEDGER_FILE = os.path.join(DATA_DIR, "spend_ledger.json")
KINDS = ("subscription", "credits", "ads", "other")
_KIND_LABELS = {"subscription": "subscriptions", "credits": "credits", "ads": "ads",
                "other": "other"}  # fmt: skip


def _load() -> list[dict[str, Any]]:
    try:
        with open(LEDGER_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    rows = data.get("entries") if isinstance(data, dict) else None
    return [r for r in rows or [] if isinstance(r, dict)]


def _save(rows: list[dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(LEDGER_FILE) or ".", exist_ok=True)
    tmp = f"{LEDGER_FILE}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"entries": rows}, f, indent=2)
    os.replace(tmp, LEDGER_FILE)


def entries() -> list[dict[str, Any]]:
    return _load()


def add_entry(
    amount: float, what: str, kind: str, *, monthly: bool = False, on: date | None = None
) -> dict[str, Any]:
    """Record a payment; ValueError for a negative amount, an unknown kind or no description."""
    if amount is None or float(amount) < 0:
        raise ValueError("amount must be 0 or more")
    if kind not in KINDS:
        raise ValueError(f"kind must be one of: {', '.join(KINDS)}")
    if not str(what or "").strip():
        raise ValueError("say what it was for (--what)")
    rows = _load()
    entry = {
        "id": max((int(r.get("id") or 0) for r in rows), default=0) + 1,
        "date": (on or date.today()).isoformat(),
        "amount": round(float(amount), 2),
        "what": str(what).strip(),
        "kind": kind,
        "monthly": bool(monthly),
    }
    rows.append(entry)
    _save(rows)
    return entry


def end_entry(entry_id: int, *, on: date | None = None) -> bool:
    """Stop a monthly entry counting after `on`'s month; False when there is no such entry."""
    rows = _load()
    for row in rows:
        if int(row.get("id") or 0) == int(entry_id):
            row["ended"] = (on or date.today()).isoformat()
            _save(rows)
            return True
    return False


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def entry_total(entry: dict[str, Any], today: date) -> float:
    """What an entry has cost by `today`."""
    start = _day(entry.get("date"))
    amount = float(entry.get("amount") or 0)
    if start is None or start > today:
        return 0.0
    if not entry.get("monthly"):
        return amount
    end = min(_day(entry.get("ended")) or today, today)
    months = (end.year - start.year) * 12 + end.month - start.month + 1
    return amount * max(0, months)


def total_spent(*, today: date | None = None) -> dict[str, Any]:
    """{total, by_kind, count}."""
    today = today or date.today()
    by_kind: dict[str, float] = {}
    rows = _load()
    for row in rows:
        cost = entry_total(row, today)
        if cost:
            kind = str(row.get("kind") or "other")
            by_kind[kind] = round(by_kind.get(kind, 0.0) + cost, 2)
    return {"total": round(sum(by_kind.values()), 2), "by_kind": by_kind, "count": len(rows)}


def run_usage() -> tuple[float, int]:
    """(USD, runs): what every run on every channel recorded using (`features["cost"]`)."""
    from config.channels import list_channel_ids
    from storage.repositories.content_runs import get_content_run_repository

    repo = get_content_run_repository()
    usd, runs = 0.0, 0
    for channel in list_channel_ids():
        for run in repo.list_for_channel(channel) or []:
            try:
                cost = (json.loads(getattr(run, "features_json", None) or "{}") or {}).get("cost")
                value = float((cost or {}).get("total") or 0)
            except (TypeError, ValueError, AttributeError):
                continue
            if value > 0:
                usd += value
                runs += 1
    return round(usd, 4), runs


def spend_line(*, today: date | None = None) -> str:
    """ "Spent so far: $54.00 - subscriptions $44.00, ads $10.00 · 58 runs used ~$3.40 of it" """
    try:
        usd, runs = run_usage()
    except Exception as exc:
        logger.debug("run usage unavailable: %s", exc)
        usd, runs = 0.0, 0
    used = f"{runs} runs used ~${usd:,.2f} of it" if runs else ""
    spent = total_spent(today=today)
    if not spent["count"]:
        tail = f" ({runs} runs used ~${usd:,.2f} in API credits)" if runs else ""
        return f"Spent so far: not entered yet - py -m scripts.ops spend add{tail}"
    parts = [f"{_KIND_LABELS.get(k, k)} ${v:,.2f}" for k, v in sorted(
        spent["by_kind"].items(), key=lambda kv: -kv[1])]  # fmt: skip
    line = f"Spent so far: ${spent['total']:,.2f}"
    if parts:
        line += " - " + ", ".join(parts)
    return f"{line} · {used}" if used else line


def ledger_lines(*, today: date | None = None) -> list[str]:
    """`ops spend`: the total, then each entry."""
    today = today or date.today()
    lines = [spend_line(today=today)]
    for row in _load():
        so_far = entry_total(row, today)
        every = " monthly" if row.get("monthly") else ""
        ended = f", ended {row['ended']}" if row.get("ended") else ""
        lines.append(
            f"  #{row.get('id')}  {row.get('date')}  ${float(row.get('amount') or 0):,.2f}{every}"
            f"  {row.get('kind')}  {row.get('what')}{ended}  (so far ${so_far:,.2f})"
        )
    return lines
