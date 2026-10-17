"""Channel / brand profiles for multi-channel Content OS."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from config.paths import CHANNELS_FILE, ROOT_DIR, migrate_file_if_needed
from config.settings import get_settings

DEFAULT_CHANNEL_ID = "default"
_CHANNELS_FILE = CHANNELS_FILE
_LEGACY_CHANNELS = os.path.join(ROOT_DIR, "channels.json")


def _overnight_renders(cfg: dict) -> int:
    block = cfg.get("overnight")
    try:
        return max(0, int((block or {}).get("renders") or 0)) if isinstance(block, dict) else 0
    except (TypeError, ValueError):
        return 0


@dataclass
class ChannelProfile:
    id: str
    name: str = ""
    domain: str = "neutral"
    # Further on-brand domains beyond `domain` (channels.json "extra_domains").
    # TapIn: football, operator decision 2026-09-26 (run 98).
    extra_domains: tuple[str, ...] = ()
    weight_overrides: dict[str, float] = field(default_factory=dict)
    youtube_oauth_token_file: str | None = None
    asset_provider_order: tuple | None = None
    output_subdir: str | None = None
    privacy_status_default: str = "private"
    # #1078 (operator, 2026-10-11): how many drafts `ops overnight` may render and queue
    # unlisted. channels.json "overnight": {"renders": N}; 0 keeps overnight render-free.
    overnight_renders: int = 0
    # #1134: a channel that is set up and not being worked (channels.json "parked": true).
    parked: bool = False
    tts_voice_id: str | None = None
    tts_model_id: str | None = None
    tts_voice_pool: dict[str, int] | None = None
    # #883: draw each run's voice from `tts_voice_pool` instead of always `tts_voice_id`.
    tts_rotate: bool = False
    # #890: speaking pace, 0.7-1.2 (ElevenLabs' range); None means the 0.95 default.
    tts_speed: float | None = None
    # #1037: sent on the ElevenLabs voice_settings object. None keeps the saved voice.
    tts_stability: float | None = None
    tts_style: float | None = None
    tts_similarity_boost: float | None = None
    # Optional per-channel LOCAL TTS voice(s) for the TTS_PROVIDER chain (Pillar 6 voice
    # variety, core/tts.resolve_local_voice). Value semantics depend on the active local
    # provider: Piper -> a .onnx path, Kokoro -> a voice name, XTTS -> a speaker wav. A
    # pool rotates per run (delivery variation); a single value is fixed. Falls back to
    # the global PIPER_VOICE/KOKORO_VOICE/XTTS_SPEAKER_WAV env when unset.
    local_tts_voice: str | None = None
    local_tts_voices: tuple[str, ...] | None = None
    background_mode: str = "hybrid"
    hybrid_local_ratio: float = 0.45
    intro_video_file: str | None = None
    intro_offset_seconds: float | None = None
    publishers_enabled: tuple | None = None
    repurpose_publish: bool = True
    # Optional human-context persona (channels.json "persona"): free-form keys like
    # tone / audience / perspective / recurring_segment / signoff that give the
    # channel a consistent voice + continuity (Phase O human-context layer).
    persona: dict[str, str] = field(default_factory=dict)
    # Optional terminal skin (core/themes.py) — CONTENT_UI_THEME env overrides.
    ui_theme: str = ""
    # Burned-caption video skin. Kept as config data so channels do not fork render code.
    caption_skin: dict[str, Any] = field(default_factory=dict)
    # Generated publish-only outro and render treatment. Dicts deliberately preserve
    # forward compatibility while config.validate_channels enforces shipped values.
    end_card: dict[str, Any] = field(default_factory=dict)
    color_grade: dict[str, Any] = field(default_factory=dict)
    # #497: a .cube LUT path relative to the repo root. Empty keeps the eq identity fallback.
    color_lut: str = ""
    hook_motion: dict[str, Any] = field(default_factory=dict)
    # #411: a bed from the operator's own tracks - {enabled, folder, volume}.
    music: dict[str, Any] = field(default_factory=dict)
    # #438: snippet language and the region named on a dry run. Never a geo-block.
    audience_language: str = ""
    audience_region: str = ""
    # #233: WinRT toast audio URI; callers still stay silent when toasts are disabled.
    notification_sound: str = "ms-winsoundevent:Notification.Default"


def channel_reading_target(channel_id: str) -> float | None:
    """channels.json ``reading_level``, or None when the channel sets no target.

    TapIn sets none: the grade is recorded and the script check does not fail.
    """
    raw = _load_channels_file()
    channels = raw.get("channels", raw) if isinstance(raw, dict) else {}
    cfg = channels.get(channel_id, {}) if isinstance(channels, dict) else {}
    if not isinstance(cfg, dict):
        return None
    return _optional_float(cfg.get("reading_level"))


def _optional_float(value) -> float | None:
    try:
        return float(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None


def _load_channels_file() -> dict[str, Any]:
    migrate_file_if_needed(_CHANNELS_FILE, _LEGACY_CHANNELS)
    if not os.path.isfile(_CHANNELS_FILE):
        if os.path.isfile(_LEGACY_CHANNELS):
            with open(_LEGACY_CHANNELS, encoding="utf-8") as f:
                return json.load(f)
        return {}
    with open(_CHANNELS_FILE, encoding="utf-8") as f:
        return json.load(f)


@lru_cache
def get_channel_profiles() -> dict[str, ChannelProfile]:
    raw = _load_channels_file()
    channels = raw.get("channels", raw) if isinstance(raw, dict) else {}
    profiles: dict[str, ChannelProfile] = {}

    if not channels:
        profiles[DEFAULT_CHANNEL_ID] = ChannelProfile(
            id=DEFAULT_CHANNEL_ID,
            name="Default",
        )
        return profiles

    for cid, cfg in channels.items():
        if not isinstance(cfg, dict):
            continue
        order = cfg.get("asset_provider_order")
        if isinstance(order, str):
            order = tuple(p.strip().lower() for p in order.split(",") if p.strip())
        elif isinstance(order, list):
            order = tuple(str(p).strip().lower() for p in order if p)

        tts = cfg.get("tts") or {}
        voice_pool = tts.get("voice_pool") or cfg.get("tts_voice_pool")
        if isinstance(voice_pool, dict):
            voice_pool = {str(k): int(v) for k, v in voice_pool.items()}

        local_voice = tts.get("local_voice") or cfg.get("local_tts_voice")
        local_voice = str(local_voice).strip() if local_voice else None
        local_voices = tts.get("local_voices") or cfg.get("local_tts_voices")
        if isinstance(local_voices, str):
            local_voices = tuple(v.strip() for v in local_voices.split(",") if v.strip())
        elif isinstance(local_voices, list):
            local_voices = tuple(str(v).strip() for v in local_voices if str(v).strip())
        else:
            local_voices = None

        pub = cfg.get("publishers_enabled")
        if isinstance(pub, str):
            pub = tuple(p.strip().lower() for p in pub.split(",") if p.strip())
        elif isinstance(pub, list):
            pub = tuple(str(p).strip().lower() for p in pub if p)

        profiles[cid] = ChannelProfile(
            id=cid,
            name=cfg.get("name", cid),
            domain=cfg.get("domain", "neutral"),
            extra_domains=tuple(str(d) for d in cfg.get("extra_domains") or ()),
            weight_overrides=dict(cfg.get("weight_overrides") or {}),
            youtube_oauth_token_file=cfg.get("youtube_oauth_token_file"),
            asset_provider_order=order,
            output_subdir=cfg.get("output_subdir") or cid,
            privacy_status_default=str(cfg.get("privacy_status_default", "private")),
            overnight_renders=_overnight_renders(cfg),
            parked=bool(cfg.get("parked", False)),
            tts_voice_id=tts.get("voice_id") or cfg.get("tts_voice_id"),
            tts_model_id=tts.get("model_id") or cfg.get("tts_model_id"),
            tts_voice_pool=voice_pool,
            tts_rotate=bool(tts.get("rotate", cfg.get("tts_rotate", False))),
            tts_speed=_optional_float(tts.get("speed")),
            tts_stability=_optional_float(tts.get("stability")),
            tts_style=_optional_float(tts.get("style")),
            tts_similarity_boost=_optional_float(tts.get("similarity_boost")),
            local_tts_voice=local_voice,
            local_tts_voices=local_voices,
            background_mode=str(cfg.get("background_mode", "hybrid")).lower(),
            hybrid_local_ratio=float(cfg.get("hybrid_local_ratio", 0.45)),
            intro_video_file=cfg.get("intro_video_file"),
            intro_offset_seconds=(
                float(cfg["intro_offset_seconds"])
                if cfg.get("intro_offset_seconds") is not None
                else None
            ),
            publishers_enabled=pub,
            repurpose_publish=bool(cfg.get("repurpose_publish", True)),
            persona={
                str(k): str(v)
                for k, v in (cfg.get("persona") or {}).items()
                if isinstance(v, str | int | float) and str(v).strip()
            },
            ui_theme=str(cfg.get("ui_theme", "")).strip().lower(),
            caption_skin=dict(cfg.get("caption_skin") or {}),
            end_card=dict(cfg.get("end_card") or {}),
            color_grade=dict(cfg.get("color_grade") or {}),
            color_lut=str(cfg.get("color_lut") or "").strip(),
            hook_motion=dict(cfg.get("hook_motion") or {}),
            music=dict(cfg.get("music") or {}),
            audience_language=str(cfg.get("audience_language") or "").strip(),
            audience_region=str(cfg.get("audience_region") or "").strip(),
            notification_sound=str(
                cfg.get("notification_sound") or "ms-winsoundevent:Notification.Default"
            ).strip(),
        )

    profiles.setdefault(
        DEFAULT_CHANNEL_ID,
        ChannelProfile(id=DEFAULT_CHANNEL_ID, name="Default"),
    )
    return profiles


def resolve_channel_id(channel_id: str | None = None) -> str:
    cid = (channel_id or get_settings().content_channel_id or DEFAULT_CHANNEL_ID).strip()
    profiles = get_channel_profiles()
    if cid not in profiles:
        return DEFAULT_CHANNEL_ID
    return cid


def get_channel_profile(channel_id: str | None = None) -> ChannelProfile:
    cid = resolve_channel_id(channel_id)
    return get_channel_profiles()[cid]


def list_channel_ids() -> list[str]:
    return list(get_channel_profiles().keys())


def active_channel_ids() -> list[str]:
    """Every channel that is being worked (#1134): the list minus the parked ones."""
    return [cid for cid, profile in get_channel_profiles().items() if not profile.parked]


def parked_channel_ids() -> list[str]:
    return [cid for cid, profile in get_channel_profiles().items() if profile.parked]


def parked_feed_scopes() -> set[str]:
    """Feed scopes that belong only to parked channels: a parked channel's own SEO feeds, and
    a domain no working channel covers. MoneyWise is parked and had made no video; its dead
    Yahoo Finance feed was failing `ops doctor` for the channel that is being worked."""
    profiles = get_channel_profiles()
    working: set[str] = set()
    for profile in profiles.values():
        if not profile.parked:
            working.add(profile.domain)
            working.update(profile.extra_domains)
    scopes: set[str] = set()
    for cid, profile in profiles.items():
        if not profile.parked:
            continue
        scopes.add(f"seo:{cid}")
        for domain in (profile.domain, *profile.extra_domains):
            if domain not in working:
                scopes.add(f"domain:{domain}")
    return scopes
