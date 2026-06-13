"""
Install bundled Luffy mascot art into core/data/luffy_ascii.txt.

Preserves exact line content (including U+2800 Braille spacing). Does not strip rows.
ASCII spaces are converted to U+2800 so whitespace trimmers cannot collapse offsets.

Usage:
    py -m scripts.update_luffy_art --write-bundled
    py -m scripts.update_luffy_art path/to/new_art.txt
    type new_art.txt | py -m scripts.update_luffy_art
"""

from __future__ import annotations

import sys
from pathlib import Path

from config.paths import LUFFY_ASCII_FILE

OUT = Path(LUFFY_ASCII_FILE)
_BRAILLE_BLANK = "\u2800"


def _normalize_line(line: str) -> str:
    if " " not in line:
        return line
    return line.replace(" ", _BRAILLE_BLANK)


def _read_source(argv: list[str]) -> str:
    if "--write-bundled" in argv:
        if not OUT.is_file():
            raise SystemExit(f"Bundled art missing at {OUT}; paste art into that file first.")
        return OUT.read_text(encoding="utf-8")

    if len(argv) > 1 and not argv[1].startswith("-"):
        src = Path(argv[1])
        if not src.is_file():
            raise SystemExit(f"Source file not found: {src}")
        raw = src.read_bytes()
    else:
        raw = sys.stdin.buffer.read()

    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode("utf-8")


def _write_lines(lines: list[str]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv
    text = _read_source(argv)
    lines = [_normalize_line(line.rstrip("\n\r")) for line in text.splitlines()]
    if not lines:
        raise SystemExit("No art lines to write.")

    _write_lines(lines)
    widths = [len(line) for line in lines]
    print(
        f"wrote {len(lines)} lines to {OUT} " f"(width {min(widths)}-{max(widths)}, UTF-8 no BOM)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
