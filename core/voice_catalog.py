"""Voice discovery — "which voices can I add?" for both the paid and free lanes.

Read-only helper behind `py -m scripts.ops voices`. Answers the two questions you need
before editing `config/voices.json`:

  1. what voices exist on the ElevenLabs account (id + name + labels to paste in);
  2. what local/free voices are on this machine (Piper `.onnx` files) or built in.

Listing ElevenLabs voices is a metadata call, not synthesis — it costs no characters.
Everything fails open: no key, no SDK, or no voices dir just prints a hint instead of
raising, so the command is safe to run on any machine.

Output is ASCII-only: `scripts/ops.py` does not force UTF-8 stdout (cp1252 on Windows).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from core.logging import get_logger

logger = get_logger("core.voice_catalog")

# Where local Piper voice models live. Each voice is a `.onnx` PLUS a matching
# `.onnx.json` config — both files are required for synthesis.
DEFAULT_PIPER_DIR = os.path.join("video", "voices")


@dataclass
class RemoteVoice:
    voice_id: str
    name: str = ""
    labels: dict = field(default_factory=dict)
    category: str = ""

    def label_summary(self) -> str:
        keys = ("gender", "accent", "age", "use_case", "description")
        parts = [str(self.labels.get(k)) for k in keys if self.labels.get(k)]
        return ", ".join(parts)


def piper_voices_dir() -> str:
    return (os.getenv("PIPER_VOICES_DIR", "") or "").strip() or DEFAULT_PIPER_DIR


def list_elevenlabs_voices() -> tuple[list[RemoteVoice], str]:
    """(voices, note) from the ElevenLabs account. Never raises.

    `note` is a human-readable reason when the list is empty (no key, SDK missing, API
    error) so the caller can print guidance instead of an empty table.
    """
    if not (os.getenv("ELEVEN_API_KEY", "") or "").strip():
        return [], "ELEVEN_API_KEY not set - skipping the ElevenLabs account listing."
    try:
        from elevenlabs.client import ElevenLabs

        client = ElevenLabs(api_key=os.getenv("ELEVEN_API_KEY"))
        response = client.voices.get_all()
    except Exception as exc:  # SDK missing, auth failure, network - all non-fatal here
        return [], f"Could not list ElevenLabs voices ({exc})."

    raw = getattr(response, "voices", None) or []
    voices: list[RemoteVoice] = []
    for item in raw:
        # Field names vary across SDK versions - read defensively.
        voice_id = str(getattr(item, "voice_id", "") or getattr(item, "id", "") or "").strip()
        if not voice_id:
            continue
        labels = getattr(item, "labels", None)
        voices.append(
            RemoteVoice(
                voice_id=voice_id,
                name=str(getattr(item, "name", "") or ""),
                labels=labels if isinstance(labels, dict) else {},
                category=str(getattr(item, "category", "") or ""),
            )
        )
    if not voices:
        return [], "The ElevenLabs account returned no voices."
    return voices, ""


def list_local_piper_voices(directory: str | None = None) -> list[str]:
    """`.onnx` voice models found on disk (sorted). Empty when the dir is absent."""
    root = directory or piper_voices_dir()
    try:
        names = sorted(n for n in os.listdir(root) if n.lower().endswith(".onnx"))
    except OSError:
        return []
    return [os.path.join(root, n) for n in names]


def _channel_rows() -> list[str]:
    """What each channel resolves to right now (a *sample* when a pool is configured)."""
    from config.channels import get_channel_profile, list_channel_ids
    from core.tts import _resolve_tts_provider, resolve_local_voice, resolve_tts_config

    rows: list[str] = []
    provider = _resolve_tts_provider()
    for cid in list_channel_ids():
        try:
            profile = get_channel_profile(cid)
            voice_id, _model = resolve_tts_config(cid)
            if profile.tts_voice_id:
                how = "pinned"
            elif profile.tts_voice_pool:
                how = f"pool of {len(profile.tts_voice_pool)} (sample)"
            else:
                how = "global catalog (sample)"
            rows.append(f"  {cid:<12} elevenlabs {voice_id}  [{how}]")
            if provider in ("piper", "kokoro", "xtts", "qwen"):
                local = resolve_local_voice(provider, cid) or "(none configured)"
                rows.append(f"  {'':<12} {provider:<10} {local}")
        except Exception as exc:  # a broken channel must not kill the listing
            rows.append(f"  {cid:<12} (could not resolve: {exc})")
    return rows


def render() -> str:
    """The full `ops voices` report."""
    from core.tts import load_local_voice_pool, load_voice_registry

    lines: list[str] = ["Voice catalog", ""]

    registry = load_voice_registry()
    total = sum(len(pool) for pool in registry.values())
    lines.append(f"In config/voices.json - elevenlabs ({total} voice(s)):")
    for category, pool in registry.items():
        ids = ", ".join(f"{vid} (w{w})" for vid, w in pool.items())
        lines.append(f"  {category}: {ids}")

    for provider in ("piper", "kokoro", "xtts", "qwen"):
        pool = load_local_voice_pool(provider)
        if pool:
            joined = ", ".join(f"{vid} (w{w})" for vid, w in pool.items())
            lines.append(f"  local.{provider}: {joined}")

    lines.append("")
    lines.append("On the ElevenLabs account (paste ids into config/voices.json):")
    remote, note = list_elevenlabs_voices()
    if note:
        lines.append(f"  {note}")
    known = {vid for pool in registry.values() for vid in pool}
    for voice in remote:
        mark = "*" if voice.voice_id in known else " "
        summary = voice.label_summary()
        suffix = f"  [{summary}]" if summary else ""
        lines.append(f"  {mark} {voice.voice_id}  {voice.name}{suffix}")
    if remote:
        lines.append("  (* = already in config/voices.json)")

    lines.append("")
    directory = piper_voices_dir()
    local_files = list_local_piper_voices(directory)
    lines.append(f"Local Piper voices in {directory}:")
    if local_files:
        for path in local_files:
            lines.append(f"  {path}")
        lines.append("  Add to config/voices.json local.piper[], or PIPER_VOICES=<csv>.")
    else:
        lines.append("  (none found)")
        lines.append("  Download from the rhasspy/piper-voices repo on HuggingFace - each")
        lines.append(
            "  voice needs BOTH <voice>.onnx and <voice>.onnx.json. See docs/free_mode.md."
        )
    lines.append("  Kokoro ships its own voices (KOKORO_VOICE, default af_heart).")

    lines.append("")
    lines.append("Resolves right now:")
    lines.extend(_channel_rows())
    return "\n".join(lines)
