"""Apify monthly true-up (candidate 68).

Compare the $0.02/run cost_meter model to a *synthetic* invoice fixture.
No network, no live invoice, no secrets. Never writes apify_sources.json
or quota_state.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger("core.apify_trueup")

DEFAULT_FIXTURE = (
    Path(__file__).resolve().parent.parent / "tests" / "fixtures" / ("apify_invoice_synthetic.json")
)


def parse_invoice(raw: dict[str, Any] | str | Path) -> dict[str, Any]:
    """Normalize an invoice-shaped dict or JSON file into {total_usd, runs, items}."""
    data: Any = raw
    if isinstance(raw, str | Path):
        path = Path(raw)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.debug("apify invoice parse failed: %s", exc)
            return {"total_usd": 0.0, "runs": 0, "items": [], "error": str(exc)}
    if not isinstance(data, dict):
        return {"total_usd": 0.0, "runs": 0, "items": [], "error": "not an object"}
    items_out: list[dict[str, Any]] = []
    runs = 0
    for row in data.get("line_items") or []:
        if not isinstance(row, dict):
            continue
        try:
            n = int(row.get("runs") or 0)
        except (TypeError, ValueError):
            n = 0
        try:
            usd = float(row.get("usd") or 0.0)
        except (TypeError, ValueError):
            usd = 0.0
        runs += max(0, n)
        items_out.append(
            {
                "actor": str(row.get("actor") or ""),
                "runs": max(0, n),
                "usd": round(usd, 4),
            }
        )
    try:
        total = float(data.get("total_usd") or 0.0)
    except (TypeError, ValueError):
        total = round(sum(i["usd"] for i in items_out), 4)
    return {
        "period": str(data.get("period") or ""),
        "currency": str(data.get("currency") or "USD"),
        "total_usd": round(total, 4),
        "runs": runs,
        "items": items_out,
    }


def modeled_usd(runs: int, *, per_run: float | None = None) -> float:
    if per_run is None:
        try:
            from core.cost_meter import _rate

            per_run = _rate("COST_APIFY_PER_RUN", 0.02)
        except Exception:
            per_run = 0.02
    return round(max(0, int(runs)) * float(per_run), 4)


def trueup(invoice: dict[str, Any]) -> dict[str, Any]:
    """Invoice vs cost_meter model. Positive delta = we under-counted the bill."""
    parsed = parse_invoice(invoice) if not invoice.get("items") else invoice
    if "items" not in parsed:
        parsed = parse_invoice(invoice)
    billed = float(parsed.get("total_usd") or 0.0)
    model = modeled_usd(int(parsed.get("runs") or 0))
    delta = round(billed - model, 4)
    return {
        "period": parsed.get("period") or "",
        "invoice_usd": billed,
        "modeled_usd": model,
        "delta_usd": delta,
        "runs": int(parsed.get("runs") or 0),
        "items": parsed.get("items") or [],
        "under_counted": delta > 0.005,
    }


def render(report: dict[str, Any]) -> str:
    lines = [
        "Apify monthly true-up (synthetic invoice vs $0.02/run model)",
        "=" * 56,
        f"  period : {report.get('period') or 'n/a'}",
        f"  invoice: ${float(report.get('invoice_usd') or 0):.2f}",
        f"  modeled: ${float(report.get('modeled_usd') or 0):.2f} "
        f"({int(report.get('runs') or 0)} runs)",
        f"  delta  : ${float(report.get('delta_usd') or 0):+.2f}"
        + ("  (meter under-counted)" if report.get("under_counted") else ""),
    ]
    for item in report.get("items") or []:
        lines.append(
            f"    {item.get('actor') or '?':<36} {int(item.get('runs') or 0):>4} runs"
            f"  ${float(item.get('usd') or 0):.2f}"
        )
    return "\n".join(lines)
