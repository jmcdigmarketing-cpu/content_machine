"""
Thumbnail generation — BFL Flux API when configured, else Pillow title card.

Optional provider chain (env `THUMBNAIL_PROVIDER=ideogram|recraft|flux|pillow`):
the selected provider fails open to Flux, then Pillow. Ideogram and Recraft
render the headline text directly on the image (Flux prompts stay text-free).
Unset (default) keeps the original Flux-if-configured behavior unchanged.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import requests
from PIL import Image, ImageDraw, ImageFont

from core import experiment_levers
from core.logging import get_logger

logger = get_logger("assets.flux_thumbnail")

# Report-card letters ranked high→low. Missing grade fail-opens (don't change
# the current paid path when the card hasn't been persisted yet).
_GRADE_RANK = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}


def _min_grade_for_paid() -> str | None:
    raw = os.getenv("THUMBNAIL_MIN_GRADE", "B").strip().upper()
    if raw in ("", "OFF", "FALSE", "NO", "0"):
        return None
    return raw if raw in _GRADE_RANK else "B"


def paid_thumbnail_blocked(grade_letter: str | None) -> bool:
    """True when the report card is below the paid-image floor (Pillow-first)."""
    min_g = _min_grade_for_paid()
    if min_g is None or not grade_letter:
        return False
    letter = grade_letter.strip().upper()
    if letter not in _GRADE_RANK:
        return False
    return _GRADE_RANK[letter] < _GRADE_RANK[min_g]


BFL_BASE_URL = os.getenv("BFL_API_BASE", "https://api.bfl.ai")
FLUX_MODEL = os.getenv("FLUX_MODEL", "flux-2-pro-preview")
FLUX_POLL_TIMEOUT = int(os.getenv("FLUX_POLL_TIMEOUT", "120"))
IDEOGRAM_BASE_URL = os.getenv("IDEOGRAM_API_BASE", "https://api.ideogram.ai")
RECRAFT_BASE_URL = os.getenv("RECRAFT_API_BASE", "https://external.api.recraft.ai")


@dataclass
class ThumbnailResult:
    path: str | None
    status: str
    detail: str | None = None
    provider: str = ""  # flux | ideogram | recraft | pillow | ""


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


def list_channel_thumbnails(output_dir: str) -> list[str]:
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
    on_wait: Callable[[float, str], None] | None = None,
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
            provider="flux",
        )
    except Exception as e:
        logger.warning("Flux failed (%s), falling back to Pillow", e)
        return ThumbnailResult(
            path=None,
            status="flux_failed",
            detail=str(e)[:200],
        )


def _build_text_prompt(topic: str, title: str) -> str:
    """Prompt for text-capable models (Ideogram/Recraft): render the headline
    on the image — unlike Flux, whose prompt explicitly forbids text."""
    headline = (title or topic).strip()[:80].replace('"', "'")
    base = _build_flux_prompt(topic, title).replace("no text, ", "")
    return f'{base}, large bold readable headline text: "{headline}"'


def _ideogram_thumbnail(
    topic: str, title: str, output_dir: str, *, filename: str, style_directive: str = ""
) -> ThumbnailResult:
    api_key = os.getenv("IDEOGRAM_API_KEY") or ""
    if not api_key:
        return ThumbnailResult(path=None, status="not_configured", detail="Set IDEOGRAM_API_KEY")

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, filename)
    prompt = _build_text_prompt(topic, title)
    if style_directive:
        prompt = f"{prompt}, {style_directive}"

    try:
        resp = requests.post(
            f"{IDEOGRAM_BASE_URL}/generate",
            headers={"Api-Key": api_key, "Content-Type": "application/json"},
            json={
                "image_request": {
                    "prompt": prompt,
                    "aspect_ratio": "ASPECT_16_9",
                    "model": os.getenv("IDEOGRAM_MODEL", "V_2"),
                    "magic_prompt_option": "AUTO",
                }
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data") or []
        url = items[0].get("url") if items and isinstance(items[0], dict) else None
        if not url:
            raise RuntimeError(f"Ideogram response missing image url: {data}")
        _download_image(url, out_path)
        logger.info("Ideogram thumbnail saved: %s", out_path)
        return ThumbnailResult(
            path=out_path, status="generated", detail="Ideogram", provider="ideogram"
        )
    except Exception as e:
        logger.warning("Ideogram failed (%s), falling back", e)
        return ThumbnailResult(path=None, status="ideogram_failed", detail=str(e)[:200])


def _recraft_thumbnail(
    topic: str, title: str, output_dir: str, *, filename: str, style_directive: str = ""
) -> ThumbnailResult:
    api_key = os.getenv("RECRAFT_API_KEY") or ""
    if not api_key:
        return ThumbnailResult(path=None, status="not_configured", detail="Set RECRAFT_API_KEY")

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, filename)
    prompt = _build_text_prompt(topic, title)
    if style_directive:
        prompt = f"{prompt}, {style_directive}"

    try:
        resp = requests.post(
            f"{RECRAFT_BASE_URL}/v1/images/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "prompt": prompt,
                "model": os.getenv("RECRAFT_MODEL", "recraftv3"),
                "style": os.getenv("RECRAFT_STYLE", "realistic_image"),
                # Closest 16:9 in Recraft's fixed size list.
                "size": "1820x1024",
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data") or []
        url = items[0].get("url") if items and isinstance(items[0], dict) else None
        if not url:
            raise RuntimeError(f"Recraft response missing image url: {data}")
        _download_image(url, out_path)
        logger.info("Recraft thumbnail saved: %s", out_path)
        return ThumbnailResult(
            path=out_path, status="generated", detail="Recraft", provider="recraft"
        )
    except Exception as e:
        logger.warning("Recraft failed (%s), falling back", e)
        return ThumbnailResult(path=None, status="recraft_failed", detail=str(e)[:200])


def _provider_chain(selected: str) -> list[str]:
    """Fail-open order for an explicit THUMBNAIL_PROVIDER value."""
    if selected == "pillow":
        return ["pillow"]
    if selected in ("ideogram", "recraft", "flux"):
        chain = [selected]
    else:
        logger.warning("Unknown THUMBNAIL_PROVIDER=%r, using flux->pillow", selected)
        chain = []
    for fallback in ("flux", "pillow"):
        if fallback not in chain:
            chain.append(fallback)
    return chain


def _chain_thumbnail(
    selected: str,
    topic: str,
    title: str,
    output_dir: str,
    *,
    content_run_id: int | None = None,
    channel_id: str | None = None,
) -> ThumbnailResult:
    """Explicit-provider path: try `selected`, fail open to Flux, then Pillow.

    Unlike the default path, only the provider that succeeds writes a file.
    An active thumbnail A/B arm styles the generative providers and is
    recorded only when one of them (not Pillow) produced the image.
    """
    run_tag = f"run{content_run_id}" if content_run_id else "thumb"

    experiment: tuple[str, str, str] | None = None
    try:
        from config.channels import resolve_channel_id
        from core.experiments import next_arm

        experiment = next_arm(resolve_channel_id(channel_id), kind="thumbnail")
    except Exception:
        experiment = None
    style = experiment[2] if experiment else ""

    skipped: list[str] = []
    for name in _provider_chain(selected):
        filename = _thumbnail_basename(title, topic, suffix=f"{name}_{run_tag}")
        if name == "ideogram":
            result = _ideogram_thumbnail(
                topic, title, output_dir, filename=filename, style_directive=style
            )
        elif name == "recraft":
            result = _recraft_thumbnail(
                topic, title, output_dir, filename=filename, style_directive=style
            )
        elif name == "flux":
            result = _flux_thumbnail(
                topic, title, output_dir, filename=filename, style_directive=style
            )
        else:
            result = _pillow_thumbnail(
                topic, title, output_dir, filename=filename, channel_id=channel_id
            )
        if result.path:
            if (
                name != "pillow"
                and experiment
                and experiment[0] != "thumbnail_format"
                and content_run_id
            ):
                try:
                    from config.channels import resolve_channel_id
                    from core.experiments import record_assignment

                    record_assignment(
                        resolve_channel_id(channel_id), content_run_id, experiment[0], experiment[1]
                    )
                except Exception as exc:
                    logger.debug("thumbnail experiment assignment skipped: %s", exc)
            if skipped:
                detail = f"{result.detail} (skipped: {'; '.join(skipped)})"[:200]
                result = ThumbnailResult(
                    path=result.path,
                    status=result.status,
                    detail=detail,
                    provider=result.provider,
                )
            return result
        skipped.append(f"{name}: {result.detail or result.status}")

    return ThumbnailResult(path=None, status="failed", detail="; ".join(skipped)[:200])


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
    channel_id: str | None = None,
    variant: str = "text_on",
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

    if variant == "face_forward":
        # Deterministic local fallback that remains visibly distinct from text_on:
        # a subject-led composition with the copy held to the left.
        draw.ellipse((760, 90, 1260, 590), fill=accent, outline=(255, 255, 255), width=8)
        draw.ellipse((900, 165, 1120, 385), fill=bg_bottom)
        draw.rounded_rectangle((845, 360, 1175, 680), radius=90, fill=bg_bottom)
    y = height // 2 - len(wrapped) * 34
    for text_line in wrapped[:4]:
        bbox = draw.textbbox((0, 0), text_line, font=font_lg)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = max(40, (640 - tw) // 2) if variant == "face_forward" else (width - tw) // 2
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
        provider="pillow",
    )


def generate_dual_thumbnails(
    topic: str,
    title: str,
    output_dir: str,
    *,
    content_run_id: int | None,
    channel_id: str | None,
    grade_letter: str | None = None,
) -> list[dict]:
    """Generate text_on + face_forward independently, each fail-open to Pillow."""
    from core.cost_meter import thumbnail_cost

    os.makedirs(output_dir, exist_ok=True)
    run_tag = f"run{content_run_id}" if content_run_id else "thumb"
    candidates: list[dict] = []
    for arm in ("text_on", "face_forward"):
        if paid_thumbnail_blocked(grade_letter):
            preferred = "pillow"
        elif arm == "text_on" and os.getenv("IDEOGRAM_API_KEY"):
            preferred = "ideogram"
        elif arm == "text_on" and os.getenv("RECRAFT_API_KEY"):
            preferred = "recraft"
        elif arm == "face_forward" and is_flux_configured():
            preferred = "flux"
        elif arm == "face_forward" and os.getenv("RECRAFT_API_KEY"):
            preferred = "recraft"
        else:
            preferred = "pillow"
        filename = _thumbnail_basename(title, topic, suffix=f"{arm}_{preferred}_{run_tag}")
        directive = experiment_levers.directive("thumbnail_format", arm)
        if preferred == "ideogram":
            result = _ideogram_thumbnail(
                topic, title, output_dir, filename=filename, style_directive=directive
            )
        elif preferred == "recraft":
            result = _recraft_thumbnail(
                topic, title, output_dir, filename=filename, style_directive=directive
            )
        elif preferred == "flux":
            result = _flux_thumbnail(
                topic, title, output_dir, filename=filename, style_directive=directive
            )
        else:
            result = _pillow_thumbnail(
                topic,
                title,
                output_dir,
                filename=filename,
                channel_id=channel_id,
                variant=arm,
            )
        failed_paid = preferred != "pillow" and not result.path
        if not result.path:
            fallback_name = _thumbnail_basename(
                title, topic, suffix=f"{arm}_pillow_{run_tag}"
            )
            result = _pillow_thumbnail(
                topic,
                title,
                output_dir,
                filename=fallback_name,
                channel_id=channel_id,
                variant=arm,
            )
        candidates.append(
            {
                "path": result.path,
                "arm": arm,
                "provider": result.provider,
                "features": {
                    "layout": arm,
                    "headline": arm == "text_on",
                    "subject_led": arm == "face_forward",
                },
                "provider_evidence": {
                    "pre_provider": preferred,
                    "post_provider": result.provider,
                    "failed_paid_attempt": failed_paid,
                },
                "cost": {
                    "pre_fallback_usd": thumbnail_cost(preferred),
                    "post_fallback_usd": thumbnail_cost(result.provider),
                    "known_incurred_usd": thumbnail_cost(result.provider),
                    "failed_attempt_billing": "unknown" if failed_paid else "none",
                },
            }
        )
    return candidates


def generate_thumbnail(
    topic: str,
    title: str,
    output_dir: str = "output/thumbnails",
    *,
    content_run_id: int | None = None,
    channel_id: str | None = None,
    grade_letter: str | None = None,
) -> ThumbnailResult:
    """
    One thumbnail per render (Flux if configured, always Pillow as usable fallback).

    Files are timestamped so older thumbnails are not overwritten.

    Set THUMBNAIL_PROVIDER=ideogram|recraft|flux|pillow to pick an explicit
    provider instead (fails open to Flux, then Pillow). Unset keeps the
    default behavior below unchanged.

    Report card below THUMBNAIL_MIN_GRADE (default B) skips paid APIs — don't
    pay Flux for a draft that already failed authenticity/grade.
    """
    if paid_thumbnail_blocked(grade_letter):
        logger.info(
            "Pillow-first: report card %s below %s — skipping paid thumbnail APIs",
            (grade_letter or "").strip().upper(),
            _min_grade_for_paid(),
        )
        run_tag = f"run{content_run_id}" if content_run_id else "thumb"
        pillow_name = _thumbnail_basename(title, topic, suffix=f"pillow_{run_tag}")
        return _pillow_thumbnail(
            topic, title, output_dir, filename=pillow_name, channel_id=channel_id
        )

    selected = (os.getenv("THUMBNAIL_PROVIDER") or "").strip().lower()
    if selected:
        return _chain_thumbnail(
            selected,
            topic,
            title,
            output_dir,
            content_run_id=content_run_id,
            channel_id=channel_id,
        )

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
            if experiment and experiment[0] != "thumbnail_format" and content_run_id:
                try:
                    from config.channels import resolve_channel_id
                    from core.experiments import record_assignment

                    record_assignment(
                        resolve_channel_id(channel_id), content_run_id, experiment[0], experiment[1]
                    )
                except Exception as exc:
                    logger.debug("thumbnail experiment assignment skipped: %s", exc)
        elif flux.detail:
            logger.info("Using Pillow thumbnail; Flux: %s", flux.detail)
            primary = ThumbnailResult(
                path=pillow.path,
                status="generated",
                detail=f"Pillow (Flux skipped: {flux.detail[:80]})",
                provider="pillow",
            )

    return primary
