"""Channel go-live checklist (candidate 60).

Fail until OAuth, SEO, RSS feeds, and a brand kit exist. MoneyWise is the
highest-RPM channel and still a one-time ops footnote. Does not read token
*contents* except through the existing ``youtube.check_setup`` helpers.
Never writes ``config/secrets/``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from config.paths import ROOT_DIR
from config.seo import get_seo_profile, rss_feeds_for_channel
from core.logging import get_logger

logger = get_logger("core.channel_go_live")


@dataclass
class GoLiveCheck:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class GoLiveReport:
    channel_id: str
    checks: list[GoLiveCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)


def _channel_extras(channel_id: str) -> dict:
    """Raw channels.json keys not on ChannelProfile (handle, trailer). Fail-open."""
    try:
        from config.channels import _load_channels_file

        raw = _load_channels_file()
        channels = raw.get("channels", raw) if isinstance(raw, dict) else {}
        cfg = channels.get(channel_id) if isinstance(channels, dict) else None
        return cfg if isinstance(cfg, dict) else {}
    except Exception as exc:
        logger.debug("channel extras skipped: %s", exc)
        return {}


def _brand_kit_paths(channel_id: str) -> list[str]:
    base = os.path.join(ROOT_DIR, "assets", "branding", channel_id)
    found: list[str] = []
    for name in ("logo.svg", "logo.png", "banner.svg", "banner.png"):
        path = os.path.join(base, name)
        if os.path.isfile(path):
            found.append(name)
    return found


def inspect_channel(channel_id: str) -> GoLiveReport:
    from config.channels import get_channel_profile, resolve_channel_id

    cid = resolve_channel_id(channel_id)
    report = GoLiveReport(channel_id=cid)
    try:
        profile = get_channel_profile(cid)
    except Exception as exc:
        report.checks.append(GoLiveCheck("profile", False, f"unreadable: {exc}"))
        return report

    report.checks.append(
        GoLiveCheck(
            "profile",
            True,
            f"{profile.name} domain={profile.domain or 'unset'}",
        )
    )

    persona = profile.persona or {}
    persona_ok = bool(persona.get("tone") and persona.get("audience"))
    report.checks.append(
        GoLiveCheck(
            "persona",
            persona_ok,
            "tone + audience set" if persona_ok else "missing tone/audience in channels.json",
        )
    )

    seo = get_seo_profile(cid)
    seo_ok = bool(seo.get("niche") and (seo.get("default_tags") or seo.get("title_rules")))
    report.checks.append(
        GoLiveCheck(
            "seo",
            seo_ok,
            f"config/seo/{cid}.json" if seo_ok else f"missing config/seo/{cid}.json (niche + tags)",
        )
    )

    feeds = rss_feeds_for_channel(cid)
    report.checks.append(
        GoLiveCheck(
            "feeds",
            len(feeds) >= 1,
            f"{len(feeds)} RSS feed(s)" if feeds else "no rss_feeds in SEO profile",
        )
    )

    # #151. Was `os.path.isfile` over two filenames, which is why the backlog
    # said this "checks files exist; it does not apply a kit". The compiler
    # resolves palette + channel config + assets together and says which source
    # each field came from, so a partial kit reads as partial.
    from core.brand_kit import compile_kit, kit_status_line

    kit = compile_kit(cid)
    report.checks.append(GoLiveCheck("brand_kit", kit.complete, kit_status_line(kit)))

    report.checks.append(
        GoLiveCheck(
            "banner",
            bool(kit.banner_path),
            kit.banner_path or f"missing assets/branding/{cid}/banner",
        )
    )

    extras = _channel_extras(cid)
    handle = str(extras.get("youtube_handle") or seo.get("handle") or "").strip()
    report.checks.append(
        GoLiveCheck(
            "handle",
            bool(handle),
            handle if handle else "set youtube_handle in channels.json (e.g. @tapin)",
        )
    )
    trailer_file = str(extras.get("channel_trailer_file") or "").strip()
    trailer_id = str(extras.get("youtube_trailer_id") or "").strip()
    trailer_ok = bool(
        trailer_id or (trailer_file and os.path.isfile(os.path.join(ROOT_DIR, trailer_file)))
    )
    report.checks.append(
        GoLiveCheck(
            "trailer",
            trailer_ok,
            trailer_id or trailer_file or "set youtube_trailer_id or channel_trailer_file",
        )
    )

    publishers = tuple(profile.publishers_enabled or ())
    yt_pub = "youtube" in publishers or not publishers
    report.checks.append(
        GoLiveCheck(
            "publisher",
            yt_pub,
            "youtube enabled" if yt_pub else f"publishers_enabled={publishers}",
        )
    )

    try:
        from youtube.check_setup import check_channel_setup

        oauth = check_channel_setup(cid)
        report.checks.append(
            GoLiveCheck(
                "oauth",
                oauth.ok,
                "upload + analytics ready"
                if oauth.ok
                else "; ".join(oauth.issues[:3]) or "not ready",
            )
        )
    except Exception as exc:
        logger.debug("channel-go-live oauth check skipped: %s", exc)
        report.checks.append(GoLiveCheck("oauth", False, f"check failed: {exc}"))

    return report


def render_report(report: GoLiveReport) -> str:
    status = "READY" if report.ok else "NOT READY"
    lines = [f"Channel go-live — {report.channel_id} [{status}]", "=" * 44]
    for check in report.checks:
        mark = "ok" if check.ok else "FAIL"
        detail = f" — {check.detail}" if check.detail else ""
        lines.append(f"  [{mark}] {check.name}{detail}")
    if not report.ok:
        lines.append("")
        lines.append(
            "Fix the FAIL lines, then re-run: "
            f"py -m scripts.ops channel-go-live --channel {report.channel_id}"
        )
    return "\n".join(lines)
