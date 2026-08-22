"""
Validate channels.json profiles before production runs.

Usage:
    py -m config.validate_channels
    py -m config.validate_channels --channel tapin
"""

from __future__ import annotations

import argparse
import json
import os

from config.channels import _CHANNELS_FILE, get_channel_profiles, list_channel_ids

SIGNAL_KEYS = {
    "youtube",
    "trends",
    "news",
    "wikipedia",
    "blog_rss",
    "sports",
    "live_scores",
    "odds",
    "rawg",
    "steam",
    "autocomplete",
    "ufc_context",
    "tapology",
    "stats_context",
    "api_sports",
    "twitch",
    "igdb",
    "trendingnow",
    "fred",
    "sec_edgar",
    "finnhub",
    "coingecko",
    "anime",
    "tmdb",
    "tvmaze",
    "lastfm",
    "musicbrainz",
}


def _load_raw() -> dict:
    if not os.path.isfile(_CHANNELS_FILE):
        return {}
    with open(_CHANNELS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _known_voice_ids() -> set[str]:
    """Every ElevenLabs id in config/voices.json. Empty set = catalog unavailable, which
    disables the "unknown id" warnings rather than firing false positives."""
    try:
        from core.tts import load_voice_registry

        return {vid for pool in load_voice_registry().values() for vid in pool}
    except Exception:
        return set()


def _check_shared_voices(channels: dict) -> list[str]:
    """Warn when channels are pinned to the SAME single voice — they'd sound identical."""
    warnings: list[str] = []
    pinned: dict[str, list[str]] = {}
    for cid, cfg in channels.items():
        if not isinstance(cfg, dict):
            continue
        tts = cfg.get("tts") or {}
        vid = tts.get("voice_id") or cfg.get("tts_voice_id")
        if vid:
            pinned.setdefault(str(vid), []).append(cid)
    for vid, cids in sorted(pinned.items()):
        if len(cids) > 1:
            warnings.append(
                f"channels {', '.join(sorted(cids))} are all pinned to voice {vid} — they will "
                "sound identical; give each a tts.voice_pool instead"
            )
    return warnings


def _check_post_schedule(block: dict, channel_id: str) -> list[str]:
    errors: list[str] = []
    if not block:
        return errors
    slots = block.get("default_slots") or []
    if isinstance(slots, list):
        for i, slot in enumerate(slots):
            if not isinstance(slot, dict):
                errors.append(f"{channel_id}: default_slots[{i}] must be an object")
                continue
            wd = slot.get("weekday")
            if wd is None or not (0 <= int(wd) <= 6):
                errors.append(f"{channel_id}: default_slots[{i}].weekday must be 0-6")
    domain_slots = block.get("domain_slots") or {}
    if isinstance(domain_slots, dict):
        for domain, dslots in domain_slots.items():
            if not isinstance(dslots, list):
                errors.append(f"{channel_id}: domain_slots.{domain} must be a list")
    return errors


def validate_channel(channel_id: str, raw_cfg: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(raw_cfg, dict):
        errors.append(f"{channel_id}: channel config must be an object")
        return errors, warnings

    domain = str(raw_cfg.get("domain", "neutral")).strip().lower()
    if not domain:
        warnings.append(f"{channel_id}: missing domain (defaults to neutral in code)")

    tts = raw_cfg.get("tts") or {}
    voice_id = tts.get("voice_id") or raw_cfg.get("tts_voice_id")
    voice_pool = tts.get("voice_pool") or raw_cfg.get("tts_voice_pool")
    if not voice_id and not voice_pool:
        warnings.append(
            f"{channel_id}: no tts.voice_id or tts.voice_pool — global voice pool will be used"
        )

    known = _known_voice_ids()
    if isinstance(voice_pool, dict):
        for vid, weight in voice_pool.items():
            try:
                if float(weight) <= 0:
                    errors.append(f"{channel_id}: tts.voice_pool[{vid}] must be > 0 (got {weight})")
            except (TypeError, ValueError):
                errors.append(
                    f"{channel_id}: tts.voice_pool[{vid}] must be numeric, not {weight!r}"
                )
            if known and vid not in known:
                warnings.append(
                    f"{channel_id}: tts.voice_pool id {vid} is not in config/voices.json "
                    "(run: py -m scripts.ops voices)"
                )
    if voice_id and known and voice_id not in known:
        warnings.append(
            f"{channel_id}: tts.voice_id {voice_id} is not in config/voices.json "
            "(run: py -m scripts.ops voices)"
        )

    mode = str(raw_cfg.get("background_mode", "hybrid")).lower()
    if mode not in ("hybrid", "stock", "local"):
        errors.append(
            f"{channel_id}: background_mode must be hybrid, stock, or local (got {mode!r})"
        )
    try:
        ratio = float(raw_cfg.get("hybrid_local_ratio", 0.45))
        if not (0.1 <= ratio <= 0.9):
            warnings.append(
                f"{channel_id}: hybrid_local_ratio {ratio} unusual (expected 0.15–0.85)"
            )
    except (TypeError, ValueError):
        errors.append(f"{channel_id}: hybrid_local_ratio must be a number")

    order = raw_cfg.get("asset_provider_order")
    if order is not None:
        if isinstance(order, str):
            order = [p.strip() for p in order.split(",") if p.strip()]
        if not isinstance(order, list):
            errors.append(f"{channel_id}: asset_provider_order must be a list or comma string")
        else:
            allowed = {"local", "pexels", "pixabay"}
            bad = [p for p in order if str(p).lower() not in allowed]
            if bad:
                errors.append(f"{channel_id}: unknown asset_provider_order entries: {bad}")

    overrides = raw_cfg.get("weight_overrides") or {}
    if overrides:
        unknown = set(overrides) - SIGNAL_KEYS
        if unknown:
            errors.append(
                f"{channel_id}: unknown weight_overrides keys: {sorted(unknown)} "
                "(move background_mode, asset_provider_order, etc. to channel root)"
            )
        numeric = {}
        for key, value in overrides.items():
            try:
                numeric[key] = float(value)
            except (TypeError, ValueError):
                errors.append(
                    f"{channel_id}: weight_overrides.{key} must be numeric, not {value!r}"
                )
        if numeric:
            total = sum(numeric.values())
            if total > 0 and abs(total - 1.0) > 0.15:
                warnings.append(
                    f"{channel_id}: weight_overrides sum to {total:.2f} (expected ~1.0)"
                )

    token_file = raw_cfg.get("youtube_oauth_token_file")
    if token_file and not os.path.isfile(token_file):
        warnings.append(f"{channel_id}: OAuth token file not found: {token_file}")

    # ui_theme must name a registered skin: an unknown one silently falls back to
    # the default mid-run instead of failing here (candidate 33).
    theme = raw_cfg.get("ui_theme")
    if theme is not None:
        try:
            from core.themes import THEMES

            if str(theme).strip().lower() not in THEMES:
                errors.append(
                    f"{channel_id}: unknown ui_theme {theme!r} "
                    f"(known: {', '.join(sorted(THEMES))})"
                )
        except Exception as exc:  # registry unavailable - do not invent an error
            warnings.append(f"{channel_id}: could not check ui_theme: {exc}")

    # persona feeds the human-context block the 2026 authenticity policy leans on;
    # without it a channel's scripts read as a neutral recap.
    persona = raw_cfg.get("persona")
    if persona is None:
        warnings.append(
            f"{channel_id}: no persona - scripts lose the human-context block "
            "(core/channel_persona.py)"
        )
    elif not isinstance(persona, dict):
        errors.append(f"{channel_id}: persona must be an object, not {type(persona).__name__}")
    elif not any(str(v).strip() for v in persona.values()):
        warnings.append(f"{channel_id}: persona is present but every field is empty")

    errors.extend(_check_post_schedule(raw_cfg.get("post_schedule") or {}, channel_id))
    return errors, warnings


def validate_all(channel_filter: str | None = None) -> int:
    raw = _load_raw()
    channels = raw.get("channels", raw) if isinstance(raw, dict) else {}
    if not channels:
        print("No channels defined in channels.json")
        return 1

    profiles = get_channel_profiles()
    ids = [channel_filter] if channel_filter else list_channel_ids()
    all_errors: list[str] = []
    all_warnings: list[str] = []

    for cid in ids:
        if cid not in profiles:
            all_errors.append(f"Unknown channel id: {cid}")
            continue
        cfg = channels.get(cid, {}) if isinstance(channels, dict) else {}
        errs, warns = validate_channel(cid, cfg)
        all_errors.extend(errs)
        all_warnings.extend(warns)

    if not channel_filter and isinstance(channels, dict):
        all_warnings.extend(_check_shared_voices(channels))

    for w in all_warnings:
        print(f"WARN: {w}")
    for e in all_errors:
        print(f"ERROR: {e}")

    if all_errors:
        print(f"\n{len(all_errors)} error(s), {len(all_warnings)} warning(s)")
        return 1

    print(f"OK — {len(ids)} channel(s) validated ({len(all_warnings)} warning(s))")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate channels.json")
    parser.add_argument("--channel", help="Validate a single channel id")
    args = parser.parse_args(argv)
    return validate_all(args.channel)


if __name__ == "__main__":
    raise SystemExit(main())
