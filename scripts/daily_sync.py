"""
Daily direction sync — competitors + SEO hints (Phase I).

Run once per day (Task Scheduler / manual):

    py -m scripts.daily_sync --channel tapin
"""

from __future__ import annotations

import argparse

from analytics.competitor_context import ensure_competitor_snapshot, snapshot_age_hours
from analytics.seo_refresh import refresh_seo_hints
from config.channels import resolve_channel_id


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Daily competitor + SEO refresh")
    parser.add_argument("--channel", default="tapin")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force competitor sync even if cache is fresh",
    )
    args = parser.parse_args(argv)

    channel_id = resolve_channel_id(args.channel)
    print(f"Daily sync — {channel_id}\n")

    snap = ensure_competitor_snapshot(channel_id, force=args.force)
    if snap.get("error"):
        print(f"  Competitors: skipped ({snap['error']})")
    elif snap.get("skipped"):
        print(f"  Competitors: skipped ({snap.get('reason')})")
    else:
        n = sum(len(c.get("recent_videos") or []) for c in (snap.get("competitors") or []))
        age = snapshot_age_hours(channel_id)
        age_s = f"{age:.1f}h old" if age is not None else "just synced"
        print(f"  Competitors: OK ({n} videos, {age_s})")

    seo = refresh_seo_hints(channel_id)
    print(f"  SEO hints: {len(seo.get('trending_tags') or [])} tags refreshed")

    # Write machine-learned channel beliefs back into the Obsidian vault (no-op
    # when OBSIDIAN_VAULT_PATH is unset or there is no analytics yet).
    try:
        from core.vault_writeback import write_channel_beliefs

        belief_path = write_channel_beliefs(channel_id)
        if belief_path:
            print(f"  Vault beliefs: refreshed {belief_path}")
        else:
            print("  Vault beliefs: skipped (no vault or no analytics yet)")
    except Exception as exc:  # never let writeback break the daily sync
        print(f"  Vault beliefs: skipped ({exc})")

    # Refresh run dossiers so post-sync actuals (views/engaged/revenue) land in
    # the vault (Pillar 4; no-op without a vault).
    try:
        from core.vault_dossiers import refresh_dossiers

        n_doss = refresh_dossiers(channel_id)
        print(f"  Vault dossiers: {n_doss} refreshed" if n_doss else "  Vault dossiers: none")
    except Exception as exc:
        print(f"  Vault dossiers: skipped ({exc})")

    print("\nDone. Discovery will use this data on next py main.py run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
