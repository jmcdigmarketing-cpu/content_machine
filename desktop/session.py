"""Stage 1 session: worker thread drives the existing video flow through ask()."""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
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
