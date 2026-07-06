"""
Thumbnail generation — BFL Flux API when configured, else Pillow title card.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional

import requests
from PIL import Image, ImageDraw, ImageFont

from config.settings import get_settings
from core.logging import get_logger

logger = get_logger("assets.flux_thumbnail")

BFL_BASE_URL = os.getenv("BFL_API_BASE", "https://api.bfl.ai")
FLUX_MODEL = os.getenv("FLUX_MODEL", "flux-2-pro-preview")
FLUX_POLL_TIMEOUT = int(os.getenv("FLUX_POLL_TIMEOUT", "120"))


@dataclass
class ThumbnailResult:
    path: Optional[str]
    status: str
    detail: Optional[str] = None


def _flux_api_key() -> str:
    return os.getenv("BFL_API_KEY") or os.getenv("FLUX_API_KEY") or ""


def is_flux_configured() -> bool:
    return bool(_flux_api_key())


def _safe_slug(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return (slug or "thumb")[:max_len]


def _thumbnail_basename(title: str, topic: str, *, suffix: str = "") -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = _safe_slug(title or topic)
    tag = f"_{suffix}" if suffix else ""
    return f"{base}_{ts}{tag}.jpg"


def list_channel_thumbnails(output_dir: str) -> List[str]:
    if not os.path.isdir(output_dir):
        return []
    paths = [
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    return sorted(paths, key=lambda p: os.path.getmtime(p))


def _build_flux_prompt(topic: str, title: str) -> str:
    headline = (title or topic).strip()[:120]
    lower = headline.lower()
    if any(k in lower for k in ("nba", "basketball", "finals", "knicks", "spurs")):
        vibe = "basketball arena, court action, dramatic sports lighting"
    elif any(k in lower for k in ("ufc", "mma", "fight", "holloway", "mcgregor")):
        vibe = "MMA octagon, fight night energy, intense sports portrait"
    elif any(k in lower for k in ("gta", "gaming", "game", "marvel", "cod")):
        vibe = "video game scene, neon gaming aesthetic, action screenshot style"
    else:
        vibe = "bold editorial photo, high contrast, clear subject"
    return (
        f"YouTube thumbnail background, {vibe}, sharp focus, vibrant colors, "
        "single clear subject, no text, no logos, no watermark, family safe"
    )


def _poll_flux_result(
    polling_url: str,
    api_key: str,
    *,
    on_wait: Optional[Callable[[float, str], None]] = None,
) -> str:
    headers = {"accept": "application/json", "x-key": api_key}
    delay = 0.5
    deadline = time.time() + FLUX_POLL_TIMEOUT
    started = time.time()

    while time.time() < deadline:
        resp = requests.get(polling_url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "")

        if on_wait and status not in ("Ready", "Error", "Failed", "Request Moderated"):
            on_wait(time.time() - started, status)

        if status == "Ready":
            sample = (data.get("result") or {}).get("sample")
            if not sample:
                raise RuntimeError("Flux ready but no sample URL")
            return sample
        if status in ("Error", "Failed", "Request Moderated"):
            raise RuntimeError(f"Flux generation failed: {data}")

        time.sleep(delay)
        delay = min(delay * 1.5, 5.0)

    raise TimeoutError("Flux thumbnail generation timed out")


def _download_image(url: str, dest_path: str) -> None:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(resp.content)


def _flux_thumbnail(
    topic: str, title: str, output_dir: str, *, filename: str, style_directive: str = ""
) -> ThumbnailResult:
    api_key = _flux_api_key()
    if not api_key:
        return ThumbnailResult(
            path=None, status="not_configured", detail="Set FLUX_API_KEY or BFL_API_KEY"
        )

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, filename)
    prompt = _build_flux_prompt(topic, title)
    if style_directive:
        prompt = f"{prompt}, {style_directive}"

    headers = {
        "accept": "application/json",
        "x-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": prompt,
        "width": 1280,
        "height": 720,
    }

    try:
        submit = requests.post(
            f"{BFL_BASE_URL}/v1/{FLUX_MODEL}",
            headers=headers,
            json=payload,
            timeout=30,
        )
        submit.raise_for_status()
        body = submit.json()
        polling_url = body.get("polling_url")
        if not polling_url:
            raise RuntimeError(f"Flux response missing polling_url: {body}")

        last_bucket = [-1]

        def _flux_wait(elapsed: float, status: str) -> None:
            bucket = int(elapsed // 5)
            if bucket > last_bucket[0]:
                last_bucket[0] = bucket
                print(
                    f"           Flux generating… {elapsed:.0f}s ({status})",
                    flush=True,
                )

        image_url = _poll_flux_result(polling_url, api_key, on_wait=_flux_wait)
        _download_image(image_url, out_path)
        logger.info("Flux thumbnail saved: %s", out_path)
        return ThumbnailResult(
            path=out_path,
            status="generated",
            detail=f"Flux {FLUX_MODEL}",
        )
    except Exception as e:
        logger.warning("Flux failed (%s), falling back to Pillow", e)
        return ThumbnailResult(
            path=None,
            status="flux_failed",
            detail=str(e)[:200],
        )


def _topic_accent(topic: str, title: str) -> tuple:
    text = f"{title} {topic}".lower()
    if any(k in text for k in ("nba", "basketball", "finals")):
        return (220, 40, 40), (30, 60, 120)
    if any(k in text for k in ("ufc", "mma", "fight")):
        return (200, 30, 30), (20, 20, 28)
    if any(k in text for k in ("gta", "gaming", "game", "marvel")):
        return (0, 200, 120), (18, 22, 42)
    return (255, 180, 0), (22, 24, 36)


def _pillow_thumbnail(
    topic: str,
    title: str,
    output_dir: str,
    *,
    filename: str,
    channel_id: Optional[str] = None,
) -> ThumbnailResult:
    os.makedirs(output_dir, exist_ok=True)
    width, height = 1280, 720
    accent, bg_bottom = _topic_accent(topic, title)
    img = Image.new("RGB", (width, height), color=bg_bottom)
    draw = ImageDraw.Draw(img)
    for y in range(height):
        blend = y / max(height - 1, 1)
        r = int(bg_bottom[0] * (1 - blend) + accent[0] * blend * 0.35)
        g = int(bg_bottom[1] * (1 - blend) + accent[1] * blend * 0.35)
        b = int(bg_bottom[2] * (1 - blend) + accent[2] * blend * 0.35)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    draw.rectangle([(0, 0), (width, 12)], fill=accent)
    draw.rectangle([(0, height - 12), (width, height)], fill=accent)

    display = (title or topic).strip()[:80]
    try:
        font_lg = ImageFont.truetype("arialbd.ttf", 58)
        font_sm = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        try:
            font_lg = ImageFont.truetype("arial.ttf", 52)
            font_sm = ImageFont.load_default()
        except OSError:
            font_lg = ImageFont.load_default()
            font_sm = font_lg

    wrapped = []
    words = display.split()
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if len(candidate) > 22:
            if line:
                wrapped.append(line)
            line = word
        else:
            line = candidate
    if line:
        wrapped.append(line)
    if not wrapped:
        wrapped = [display[:22] or "Video"]

    y = height // 2 - len(wrapped) * 34
    for text_line in wrapped[:4]:
        bbox = draw.textbbox((0, 0), text_line, font=font_lg)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (width - tw) // 2
        draw.rectangle(
            [(x - 14, y - 10), (x + tw + 14, y + th + 10)],
            fill=(0, 0, 0),
        )
        draw.text((x, y), text_line, fill=(255, 255, 255), font=font_lg)
        y += 64

    from config.channels import resolve_channel_id

    if resolve_channel_id(channel_id) == "tapin":
        draw.text((24, height - 48), "TAPIN", fill=(255, 255, 255), font=font_sm)

    out_path = os.path.join(output_dir, filename)
    img.save(out_path, "JPEG", quality=92)
    size_kb = max(1, os.path.getsize(out_path) // 1024)
    return ThumbnailResult(
        path=out_path,
        status="generated",
        detail=f"Pillow title card ({size_kb} KB)",
    )


def generate_thumbnail(
    topic: str,
    title: str,
    output_dir: str = "output/thumbnails",
    *,
    content_run_id: Optional[int] = None,
    channel_id: Optional[str] = None,
) -> ThumbnailResult:
    """
    One thumbnail per render (Flux if configured, always Pillow as usable fallback).

    Files are timestamped so older thumbnails are not overwritten.
    """
    run_tag = f"run{content_run_id}" if content_run_id else "thumb"
    pillow_name = _thumbnail_basename(title, topic, suffix=f"pillow_{run_tag}")
    flux_name = _thumbnail_basename(title, topic, suffix=f"flux_{run_tag}")

    pillow = _pillow_thumbnail(
        topic, title, output_dir, filename=pillow_name, channel_id=channel_id
    )
    primary = pillow

    # Thumbnail A/B (Phase S): an active thumbnail-kind experiment appends its
    # arm's style directive to the Flux prompt. The assignment is recorded only
    # when Flux actually generated the image — Pillow fallbacks would pollute
    # the arm's attribution with thumbnails the lever never shaped.
    experiment: tuple[str, str, str] | None = None
    try:
        from config.channels import resolve_channel_id
        from core.experiments import next_arm

        experiment = next_arm(resolve_channel_id(channel_id), kind="thumbnail")
    except Exception:
        experiment = None

    if is_flux_configured() and os.getenv("THUMBNAIL_FLUX_FIRST", "true").lower() not in (
        "0",
        "false",
        "no",
    ):
        flux = _flux_thumbnail(
            topic,
            title,
            output_dir,
            filename=flux_name,
            style_directive=experiment[2] if experiment else "",
        )
        if flux.path:
            primary = flux
            if experiment and content_run_id:
                try:
                    from config.channels import resolve_channel_id
                    from core.experiments import record_assignment

                    record_assignment(
                        resolve_channel_id(channel_id), content_run_id, experiment[0], experiment[1]
                    )
                except Exception:
                    pass
        elif flux.detail:
            logger.info("Using Pillow thumbnail; Flux: %s", flux.detail)
            primary = ThumbnailResult(
                path=pillow.path,
                status="generated",
                detail=f"Pillow (Flux skipped: {flux.detail[:80]})",
            )

    return primary
