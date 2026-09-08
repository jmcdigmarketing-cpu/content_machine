"""Stage 1 session: worker thread drives the existing video flow through ask()."""

from __future__ import annotations

import json
import os
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

from core.angle_intent import angle_intent_note, detect_angle_intent
from core.ask import reset_backend, set_backend
from core.ask_bridge import AskBridge, BridgeBackend, set_current_bridge
from core.emit import reset_emit, set_emit
from core.operator_facts import parse_pasted_block


def angle_mode_line(topic: str) -> str:
    """Operator-facing intent for the angle strip — real detector, not a second lexicon."""
    return angle_intent_note(detect_angle_intent(topic))


def facts_from_paste(text: str) -> list[str]:
    return parse_pasted_block(text or "")


def facts_meter_line(text: str) -> str:
    from core.operator_facts import operator_key_fact_char_budget

    n = len(text or "")
    budget = operator_key_fact_char_budget()
    return f"{n} / {budget} chars"


def facts_from_drop(paths: list[str]) -> str:
    chunks: list[str] = []
    for raw in paths:
        item = str(raw or "").strip()
        if not item:
            continue
        if item.lower().startswith(("http://", "https://")):
            chunks.append(item)
            continue
        path = Path(item)
        if path.suffix.lower() == ".txt" and path.is_file():
            chunks.append(path.read_text(encoding="utf-8"))
            continue
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks).strip()


def window_state_path() -> Path:
    override = (os.getenv("CONTENT_WINDOW_STATE") or "").strip()
    if override:
        return Path(override)
    from config.paths import DATA_DIR

    return Path(DATA_DIR) / "window_state.json"


def load_window_state(channel_id: str) -> dict[str, object]:
    path = window_state_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    row = data.get((channel_id or "").strip().lower()) or {}
    return dict(row) if isinstance(row, dict) else {}


def save_window_state(channel_id: str, state: dict[str, object]) -> None:
    path = window_state_path()
    data: dict[str, object] = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, json.JSONDecodeError):
            data = {}
    data[(channel_id or "").strip().lower()] = dict(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _gui_emit(lines: list[str], lock: threading.Lock) -> Callable[..., None]:
    def sink(*args: object, **_kwargs: object) -> None:
        piece = " ".join(str(a) for a in args)
        with lock:
            lines.append(piece)

    return sink


class _StdoutTee:
    """main.py still uses print(); the pane would be empty without this."""

    def __init__(self, original: TextIO, lines: list[str], lock: threading.Lock) -> None:
        self._original = original
        self._lines = lines
        self._lock = lock
        self._buf = ""

    def write(self, data: str) -> int:
        written = self._original.write(data)
        self._buf += data.replace("\r", "")
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            with self._lock:
                self._lines.append(line)
        return int(written or 0)

    def flush(self) -> None:
        flush = getattr(self._original, "flush", None)
        if flush:
            flush()

    def isatty(self) -> bool:
        return False


@contextmanager
def capture_stdout(lines: list[str], lock: threading.Lock) -> Iterator[None]:
    original = sys.stdout
    sys.stdout = _StdoutTee(original, lines, lock)  # type: ignore[assignment]
    try:
        yield
    finally:
        sys.stdout = original


def start_run_worker(
    *,
    channel_id: str,
    topic: str,
    facts_text: str,
    bridge: AskBridge,
    log_lines: list[str],
    log_lock: threading.Lock,
    on_done: Callable[[BaseException | None], None] | None = None,
) -> threading.Thread:
    """Run main._run_new_video_flow on a worker. Pipeline stays on this thread."""

    facts = facts_from_paste(facts_text)
    bridge.set_fact_lines(facts)

    def body() -> None:
        err: BaseException | None = None
        set_current_bridge(bridge)
        set_backend(BridgeBackend(bridge))
        set_emit(_gui_emit(log_lines, log_lock))
        try:
            with capture_stdout(log_lines, log_lock):
                import main as app

                app._run_new_video_flow(
                    channel_id,
                    seed_topic=topic.strip(),
                    creative_brief="",
                )
        except BaseException as exc:
            err = exc
        finally:
            reset_backend()
            reset_emit()
            set_current_bridge(None)
            if on_done is not None:
                on_done(err)

    thread = threading.Thread(target=body, name="content-os-run", daemon=True)
    thread.start()
    return thread
