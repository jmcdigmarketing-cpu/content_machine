"""#295. 2x2 Pillow collage of the newest thumbs. No image API."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw

from core.design_tokens import header_border_hex, load_tokens
from core.html_report import themed_page


@dataclass(frozen=True)
class ContactSheet:
    path: str
    paths: list[str] = field(default_factory=list)
    ok: bool = True
    detail: str = ""
    html_path: str = ""


def _newest_thumbs(folder: str, *, limit: int = 4) -> list[Path]:
    root = Path(folder)
    if not root.is_dir():
        return []
    suffixes = {".png", ".jpg", ".jpeg", ".webp"}
    files = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in suffixes]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def render_contact_sheet(
    dest_path: str,
    *,
    thumbs_dir: str,
    channel_id: str | None = "tapin",
    cell: int = 320,
) -> ContactSheet:
    thumbs = _newest_thumbs(thumbs_dir)
    if not thumbs:
        return ContactSheet(
            path=dest_path,
            paths=[],
            ok=False,
            detail="no thumbnail files in the output folder",
        )
    from core.caption_contrast import parse_hex

    border = parse_hex(header_border_hex(channel_id))
    gap = 8
    cols, rows = 2, 2
    canvas_w = cols * cell + (cols + 1) * gap
    canvas_h = rows * cell + (rows + 1) * gap
    image = Image.new("RGB", (canvas_w, canvas_h), border)
    draw = ImageDraw.Draw(image)
    used: list[str] = []
    for idx in range(cols * rows):
        r, c = divmod(idx, cols)
        x = gap + c * (cell + gap)
        y = gap + r * (cell + gap)
        draw.rectangle((x, y, x + cell, y + cell), fill=(10, 10, 12))
        if idx >= len(thumbs):
            continue
        src = thumbs[idx]
        used.append(str(src))
        with Image.open(src) as raw:
            tile = raw.convert("RGB")
            tile.thumbnail((cell, cell))
            ox = x + (cell - tile.size[0]) // 2
            oy = y + (cell - tile.size[1]) // 2
            image.paste(tile, (ox, oy))
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest)
    html_path = dest.with_suffix(".html")
    html_path.write_text(
        contact_sheet_html(dest.name, channel_id=channel_id),
        encoding="utf-8",
    )
    return ContactSheet(
        path=str(dest),
        paths=used,
        ok=True,
        detail=f"{len(used)} thumbs",
        html_path=str(html_path),
    )


def contact_sheet_html(image_href: str, *, channel_id: str | None = "tapin") -> str:
    tokens = load_tokens()
    body_px = int(tokens["type"]["body"])
    body = (
        f"<style>img.sheet {{ width: 100%; max-width: 720px; }} "
        f"@media print {{ header {{ display: none !important; }} "
        f"body {{ font-size: {body_px}px; }} }}</style>"
        f"<p>Last four thumbnails</p>"
        f"<img class='sheet' src='{image_href}' alt='contact sheet'>"
    )
    return themed_page("Contact sheet", body, channel_id=channel_id or "tapin")
