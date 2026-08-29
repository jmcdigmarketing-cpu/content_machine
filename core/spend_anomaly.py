"""#379 spend-anomaly toast when a run costs ≥ 3× the trailing median."""

from __future__ import annotations

from statistics import median

from core.logging import get_logger

logger = get_logger("core.spend_anomaly")


def maybe_toast_spend_anomaly(run_cost: float, trailing: list[float]) -> bool:
    """Toast when run_cost ≥ 3× trailing median. Cheap runs return False."""
    try:
        cost = float(run_cost)
    except (TypeError, ValueError):
        return False
    nums = []
    for raw in trailing:
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        if val > 0:
            nums.append(val)
    if cost <= 0 or len(nums) < 2:
        return False
    med = median(nums)
    if med <= 0 or cost < 3.0 * med:
        return False
    from core.win_notify import toast

    return bool(
        toast(
            "Spend anomaly",
            f"This run ${cost:.2f} is ≥ 3× trailing median ${med:.2f}",
            key=f"spend:{cost:.2f}:{med:.2f}",
        )
    )
