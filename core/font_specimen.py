"""#248: three caption faces. A pick writes a note, never channels.json."""

from __future__ import annotations

from pathlib import Path

from config.channels import get_channel_profile


def specimen_faces(channel_id: str | None = "tapin") -> list[str]:
    skin = get_channel_profile(channel_id).caption_skin or {}
    faces: list[str] = []
    for key in ("title_font", "body_font", "font"):
        name = str(skin.get(key) or "").strip()
        if name and name not in faces:
            faces.append(name)
    for extra in ("Segoe UI", "Georgia", "Arial"):
        if extra not in faces:
            faces.append(extra)
        if len(faces) >= 3:
            break
    return faces[:3]


def write_font_pick(face: str, dest: str) -> str:
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"caption font pick: {face}\n", encoding="utf-8")
    return str(path)
