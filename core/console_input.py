"""Buffered-console input: see it, read it, or discard it.

A paste into a terminal does not arrive one prompt at a time — the whole block
lands in the console input buffer and every following `input()` eats one line of
it. Live-run 74 lost a whole run to this: an article pasted at the `Fact N`
prompt ended intake at its first blank line, and the leftover lines answered the
prompts that came after. `Proceed?` received Engadget's byline label `by`, read
it as "not y", and threw the script away. Live-run 71 was the same shape.

Three primitives, all best-effort and all safe when stdin is not a console:

  `input_pending()`     - is more input already waiting? (a blank line mid-paste
                          is a paragraph break, not the operator pressing Enter)
  `read_pending_lines()` - drain the buffer and *return* it, so a paste can be
                          offered back as facts instead of hijacking a gate
  `drain_stdin()`       - discard it, reporting how many lines went

None of them raise. Off a real console (CI, pipes, redirected stdin) they report
"nothing pending", which is the behaviour that keeps a non-interactive run
identical to today's.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from core.logging import get_logger

logger = get_logger("core.console_input")


def _stdin_is_tty() -> bool:
    """True only for a real interactive console. Never raises."""
    try:
        return bool(sys.stdin) and sys.stdin.isatty()
    except Exception:  # detached / closed / replaced stdin
        return False


def _pending_backend() -> bool:
    """Platform check for 'bytes are already buffered'. Raises on an odd platform."""
    try:
        import msvcrt  # Windows console
    except ImportError:
        pass
    else:
        return bool(msvcrt.kbhit())

    import select

    ready, _, _ = select.select([sys.stdin], [], [], 0)
    return bool(ready)


def _read_backend() -> str:
    """Drain the buffer to a string. Raises on an odd platform."""
    try:
        import msvcrt  # Windows console
    except ImportError:
        pass
    else:
        chunks: list[str] = []
        # getwch() does not echo, so a discarded paste leaves no wreckage on screen.
        while msvcrt.kbhit():
            chunks.append(msvcrt.getwch())
        return "".join(chunks)

    import os
    import select

    chunks_b: list[bytes] = []
    while True:
        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if not ready:
            break
        data = os.read(sys.stdin.fileno(), 4096)
        if not data:
            break
        chunks_b.append(data)
    return b"".join(chunks_b).decode("utf-8", errors="replace")


def _to_lines(raw: str) -> list[str]:
    """Console text -> lines, keeping interior blanks (paragraph breaks) intact."""
    flat = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in flat.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def input_pending() -> bool:
    """True when more input is already buffered. False whenever it cannot tell."""
    if not _stdin_is_tty():
        return False
    try:
        return bool(_pending_backend())
    except Exception as exc:
        logger.debug("input_pending unavailable: %s", exc)
        return False


def _read_one_key() -> str:
    """One console key. Enter is ``\\r`` or ``\\n``. Never raises to the caller."""
    try:
        import msvcrt

        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            msvcrt.getwch()
            return ""
        return ch
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("menu key unavailable: %s", exc)
        return ""
    try:
        termios: Any = __import__("termios")
        tty: Any = __import__("tty")
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return ch or ""
    except Exception as exc:
        logger.debug("menu key unavailable: %s", exc)
        return ""


_ENTER_WINDOW = 0.75


def swallow_enter(*, ready, read, unread, window: float = _ENTER_WINDOW) -> None:
    """Take the Enter typed straight after a menu key, so it does not answer the next prompt.

    Waits at most ``window`` seconds. Any other key is put back for the next prompt.
    """
    import time

    deadline = time.monotonic() + window
    while time.monotonic() < deadline:
        if ready():
            ch = read()
            if ch not in ("\r", "\n"):
                unread(ch)
            return
        time.sleep(0.02)


def _swallow_console_enter() -> None:
    try:
        import msvcrt

        swallow_enter(ready=msvcrt.kbhit, read=msvcrt.getwch, unread=msvcrt.ungetwch)
    except ImportError:
        return
    except Exception as exc:
        logger.debug("trailing Enter not read: %s", exc)


def menu_line(
    prompt: str,
    input_fn=None,
    *,
    tty: bool | None = None,
    read_char=None,
    print_fn=None,
    after_key=None,
) -> str:
    """A numbered menu. On a TTY, one key is enough and Enter is the empty default.

    A scripted ``input_fn`` (tests, the desktop bridge) still returns the whole
    line. ``read_char`` is how a test supplies the key without a console. The Enter
    typed out of habit after the key is taken with it (``after_key``).
    """
    from core.ask import ask_text

    fn = input_fn or ask_text
    interactive = read_char is not None or (
        fn is ask_text and (tty if tty is not None else _stdin_is_tty())
    )
    if not interactive:
        return fn(prompt)
    from core.ask import gate_bell

    try:
        tty = bool(sys.stdout) and sys.stdout.isatty()
    except Exception:
        tty = False
    bell = gate_bell(
        prompt,
        tty=tty,
        no_color=bool(os.getenv("NO_COLOR", "").strip()),
    )
    if bell:
        sys.stdout.write(bell)
        sys.stdout.flush()
    if print_fn is not None:
        print_fn(prompt, end="")
    else:
        sys.stdout.write(prompt)
    # #1297: a prompt with no newline stays in the buffer, so every one-key menu read its key
    # with nothing on the screen - "the menu will just not have a visual input anymore".
    try:
        sys.stdout.flush()
    except Exception as exc:
        logger.debug("prompt not flushed: %s", exc)
    ch = (read_char or _read_one_key)()
    if ch == "\x03":
        raise KeyboardInterrupt
    shown = "" if ch in ("\r", "\n") else ch
    if shown:
        # Review of 29c280c: the Enter after "6" stayed buffered and answered the next prompt.
        if after_key is not None:
            after_key()
        elif read_char is None:
            _swallow_console_enter()
    if print_fn is not None:
        print_fn(shown)
    else:
        sys.stdout.write(shown + "\n")
        sys.stdout.flush()
    return shown


def read_pending_lines() -> list[str]:
    """Drain buffered input and return it as lines. `[]` when nothing is waiting."""
    if not _stdin_is_tty():
        return []
    try:
        return _to_lines(_read_backend())
    except Exception as exc:
        logger.debug("read_pending_lines unavailable: %s", exc)
        return []


def drain_stdin() -> int:
    """Discard buffered input; return how many lines were thrown away."""
    return len(read_pending_lines())
