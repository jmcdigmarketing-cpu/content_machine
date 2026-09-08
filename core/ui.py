"""CLI presentation helpers."""

import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, ClassVar

from apis.signal_contract import format_health_line
from config.channels import (
    get_channel_profile,
    get_channel_profiles,
    list_channel_ids,
    resolve_channel_id,
)
from config.settings import get_settings
from core.ask import ask_text
from core.emit import emit
from core.logging import get_logger

logger = get_logger("core.ui")


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def fact_display_width() -> int:
    """#488. Fact preview width follows the terminal, not a hardcoded 90."""
    from core.ui_theme import terminal_width

    return max(56, terminal_width(maximum=160) - 4)


# ---------------------------------------------------------------------------
# Live spinner for long-running operations
# ---------------------------------------------------------------------------


class DiscoverySpinner:
    """Animated in-place spinner shown during the multi-minute discovery phase.

    The pipeline drives the displayed phase via :meth:`report` (pass it as the
    ``progress`` callback to ``run_discovery``). When no phase is reported, the
    spinner falls back to time-based stage guesses so older callers still animate.
    """

    _FRAMES: ClassVar[list[str]] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    _STAGES: ClassVar[list[tuple[int, str]]] = [
        (0, "Fetching signals"),
        (15, "Scoring variants"),
        (45, "Finishing up"),
    ]

    # Phase-prefix → run-trace timing key, for the "typ ~Ns" hint.
    _PHASE_TIMING_KEYS: ClassVar[dict[str, str]] = {
        "Fetching signals": "signals_and_variants",
        "Scoring variants": "variant_scoring",
    }

    def __init__(self, label: str = "Discovery"):
        self._label = label
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._t0: float = 0.0
        self._enabled = sys.stdout.isatty()
        self._lock = threading.Lock()
        self._phase: str | None = None
        self._done: int | None = None
        self._total: int | None = None
        self._detail: str | None = None
        self._line_len = 0
        # Themed frames + loading copy (CONTENT_UI_THEME) — resolved once per
        # spinner so the 10Hz animation loop never re-reads env/theme state.
        try:
            from core.themes import active_theme, themed_phase

            self._frames: list[str] = list(active_theme().spinner_frames) or self._FRAMES
            self._themed_phase = themed_phase
        except Exception:
            self._frames = self._FRAMES
            self._themed_phase = lambda phase: phase
        self._typical = self._load_typical_timings()

    @staticmethod
    def _load_typical_timings() -> dict[str, float]:
        """Median phase timings from recent traces ("typ ~Ns" hints). Fail-open."""
        try:
            from core.run_trace import list_traces

            buckets: dict[str, list[float]] = {}
            for trace in list_traces(limit=20):
                timings = trace.get("timings") or {}
                if not isinstance(timings, dict):
                    continue
                for key in ("signals_and_variants", "variant_scoring"):
                    val = timings.get(key)
                    if isinstance(val, int | float) and float(val) >= 5:
                        buckets.setdefault(key, []).append(float(val))
            return {key: _median(vals) for key, vals in buckets.items() if vals}
        except Exception as exc:
            logger.debug("list_traces skipped: %s", exc)
        return {}

    def report(
        self,
        phase: str,
        done: int | None = None,
        total: int | None = None,
        detail: str | None = None,
    ) -> None:
        """Thread-safe progress hook. Sets phase, optional N/M count, and a detail line
        (e.g. the variant title currently being scored)."""
        with self._lock:
            self._phase = phase
            self._done = done
            self._total = total
            self._detail = detail
        try:
            from core.ask_bridge import current_bridge

            bridge = current_bridge()
            if bridge is not None:
                bridge.set_progress(phase, done, total, detail)
        except Exception as exc:
            logger.debug("gui progress skipped: %s", exc)

    def _typical_hint(self, phase: str) -> str:
        for prefix, key in self._PHASE_TIMING_KEYS.items():
            if phase.startswith(prefix):
                secs = self._typical.get(key) or 0.0
                if secs >= 5:
                    return f" (typ ~{secs:.0f}s)"
        return ""

    def _current_stage(self, elapsed: float) -> str:
        with self._lock:
            phase, done, total, detail = self._phase, self._done, self._total, self._detail
        if phase is None:
            # Fall back to time-based guesses for callers that don't report progress.
            stage = self._STAGES[0][1]
            for threshold, name in self._STAGES:
                if elapsed >= threshold:
                    stage = name
            return self._themed_phase(stage)
        stage = self._themed_phase(phase)
        if total:
            stage = f"{stage} {done or 0}/{total}"
        stage += self._typical_hint(phase)
        if detail:
            stage += f" · {detail[:44]}"
        return stage

    def _spin(self) -> None:
        i = 0
        while not self._stop.is_set():
            elapsed = time.perf_counter() - self._t0
            frame = self._frames[i % len(self._frames)]
            stage = self._current_stage(elapsed)
            text = f"  {frame}  {self._label} · {stage}... {elapsed:.0f}s"[:110]
            # Pad to the longest line drawn so a shrinking status never leaves residue.
            self._line_len = max(self._line_len, len(text))
            sys.stdout.write(f"\r{text.ljust(self._line_len)}")
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1
        sys.stdout.write(f"\r{' ' * max(self._line_len, 70)}\r")
        sys.stdout.flush()

    def __enter__(self):
        self._t0 = time.perf_counter()
        if self._enabled:
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)


# ---------------------------------------------------------------------------
# Domain-specific ASCII art panels
# ---------------------------------------------------------------------------

_DOMAIN_ART: dict[str, str] = {
    "gaming": """\
  ╔═══════════════╗
  ║  ◁  ●  ▷  ●  ║
  ║   [L]   [R]  ║
  ║  ╔═══════╗   ║
  ║  ║ START ║   ║
  ║  ╚═══════╝   ║
  ╚═══════════════╝""",
    "ufc": """\
      ___   ___
     /   | |   \\
    | UFC | UFC |
    |  🥊 | 🥊  |
     \\___| |___/
      OCTAGON
      ───────""",
    "nba": """\
       .-\"\"\"-.
      /  |||  \\
     | --|--|- |
      \\   |   /
       '-...-'
      NBA TODAY""",
    "nfl": """\
      .-\"\"\"-.
     ( o   o )
      |  ▲  |
      | NFL |
     (       )
      '-----' """,
    "finance": """\
    ┌─────────┐
    │ ▲ +2.4% │
    │ ╱╲      │
    │╱  ╲  ╱  │
    │    ╲╱   │
    └─────────┘
      MARKETS """,
}


def _load_art(filename: str) -> str:
    """Load decorative art from core/data/<filename> (UTF-8). '' if missing."""
    from pathlib import Path

    try:
        return (Path(__file__).parent / "data" / filename).read_text(encoding="utf-8").rstrip("\n")
    except OSError:
        return ""


# Franchise-specific art shown when a topic mentions it (overrides domain art).
# Keyed by a tuple of trigger keywords -> (art, accent color).
_SUPER_MARIO_GALAXY = _load_art("mario_ascii.txt")

_FRANCHISE_ART: list[tuple[tuple[str, ...], str, str]] = [
    (
        ("super mario galaxy", "mario galaxy", "mario", "galaxy", "nintendo", "luma"),
        _SUPER_MARIO_GALAXY,
        "\033[33m",  # yellow — star bits
    ),
]


def _franchise_art_for(topic: str) -> tuple[str, str] | None:
    t = (topic or "").lower()
    for keywords, art, color in _FRANCHISE_ART:
        if any(k in t for k in keywords):
            return art, color
    return None


def print_domain_art(domain: str, *, topic: str = "", print_fn=emit) -> None:
    """Print a small decorative ASCII panel for the topic's franchise or domain."""
    from core.ascii_art import ascii_enabled
    from core.ui_theme import paint, ui_color_enabled

    if not ascii_enabled():
        return

    art: str | None
    franchise = _franchise_art_for(topic)
    if franchise:
        art, color = franchise
    else:
        # Prefer the topic's own domain (a UFC topic on a gaming channel should show
        # the octagon, not the controller); fall back to the channel domain.
        art_domain = domain
        if topic:
            from apis.topic_scorer import infer_domain

            inferred = infer_domain(topic)
            if inferred and inferred in _DOMAIN_ART:
                art_domain = inferred
        art = _DOMAIN_ART.get(art_domain)
        color = "\033[36m"  # cyan
    if not art:
        return
    for line in art.splitlines():
        print_fn(paint(line, color) if ui_color_enabled() else line)
    print_fn()


# ---------------------------------------------------------------------------
# Bonus art gallery — purely decorative, shown liberally (topic-agnostic).
# Mario is always in the rotation; the rest add variety. All colored.
# ---------------------------------------------------------------------------

_TROPHY_ART = """\
        ___________
       '._==_==_=_.'
       .-\\:      /-.
      | (|:.     |) |
       '-|:.     |-'
         \\::.    /
          '::. .'
            ) (
          _.' '._
         `\"\"\"\"\"\"\"`
         CHAMPION"""

_ROCKET_ART = """\
           /\\
          /  \\
         |    |
         | CM |
         |    |
        /|/\\/\\|\\
       /_|_||_|_\\
          /||\\
         // || \\\\
            ''
        LIFTOFF"""

_STARBURST_ART = """\
        .    *    .
      *   \\  |  /   *
       '--==[ ★ ]==--'
      *   /  |  \\   *
        '    *    '
        ON A ROLL"""

_HERO_ART = _load_art("bonus_hero_ascii.txt")

# Theme celebration pieces (fired on publish success via print_celebration).
_ZELDA_ITEM_ART = """\
      da-da-da-DAAA!
         ________
        |  ◆◆◆◆  |
        |  ◆||◆  |
        |  ◆||◆  |
        |__◆◆◆◆__|
       YOU GOT THE
      RENDERED VIDEO"""

_POKEMON_LEVELUP_ART = """\
       ▁▂▃▅▆▇ ⚡
      CHANNEL grew
      to LVL UP! ⬆
     ◓ It's super
       effective!"""

_DBZ_OVER9000_ART = """\
       \\ ⚡ ⚡ /
      ─ ((●)) ─
       / |☰| \\
     IT'S OVER 9000!
      (the render
       is complete)"""

_JJBA_TBC_ART = """\
                    ____
      ⬅ TO BE CONTINUED
     ────────────────╯
      ゴ ゴ ゴ ゴ ゴ"""

# (art, color) — keyed; "mario"/"hero" load from core/data art files. Empty pieces
# (missing data file) are filtered out so the gallery never prints a blank panel.
_BONUS_ART: dict[str, tuple[str, str]] = {
    key: (art, color)
    for key, art, color in (
        ("mario", _SUPER_MARIO_GALAXY, "\033[31m"),  # red — Mario
        ("hero", _HERO_ART, "\033[35m"),  # magenta
        ("trophy", _TROPHY_ART, "\033[33m"),  # gold
        ("rocket", _ROCKET_ART, "\033[36m"),  # cyan
        ("starburst", _STARBURST_ART, "\033[35m"),  # magenta
        ("zelda_item", _ZELDA_ITEM_ART, "\033[32m"),  # kokiri green
        ("pokemon_levelup", _POKEMON_LEVELUP_ART, "\033[33m"),  # pikachu yellow
        ("dbz_over9000", _DBZ_OVER9000_ART, "\033[33m"),  # saiyan orange-ish
        ("jjba_tbc", _JJBA_TBC_ART, "\033[35m"),  # stand purple
    )
    if art
}


def print_bonus_art(*, key: str | None = None, print_fn=emit) -> None:
    """Print a decorative colored art panel. Random piece unless `key` is given.

    Mario is guaranteed to be available; pass key='mario' to force it.
    """
    import random

    from core.ascii_art import ascii_enabled
    from core.ui_theme import paint, ui_color_enabled

    if not ascii_enabled():
        return
    if key and key in _BONUS_ART:
        art, color = _BONUS_ART[key]
    else:
        art, color = random.choice(list(_BONUS_ART.values()))
    for line in art.splitlines():
        print_fn(paint(line, color) if ui_color_enabled() else line)
    print_fn()


def print_celebration(*, print_fn=emit) -> None:
    """Publish-success flourish: the active theme's celebration piece, else random."""
    try:
        from core.themes import active_theme

        key = active_theme().celebration_key or None
    except Exception:
        key = None
    print_bonus_art(key=key, print_fn=print_fn)


# Publish counts that earn a milestone line (kept sparse so it stays special).
_MILESTONES = (1, 5, 10, 25, 50, 100, 250, 500, 1000)


def maybe_print_milestone(channel_id: str, *, print_fn=emit) -> None:
    """One-line badge when the channel's upload count hits a milestone. Fail-open."""
    try:
        from storage.repositories.publish_log import get_publish_log_repository

        count = len(get_publish_log_repository().list_uploaded_for_channel(channel_id))
    except Exception:
        return
    if count not in _MILESTONES:
        return
    from core.ui_theme import accent

    label = "first video queued!" if count == 1 else f"video #{count} for this channel!"
    print_fn(accent(f"  ★ Milestone — {label}"))


HEALTH_LEGEND = "ON=ok | ON (not active)=no match | " "QUOTA/RATE LIMITED/AUTH=issue — see detail"

SIGNAL_ORDER = (
    "youtube",
    "wikipedia",
    "live_scores",
    "stats_context",
    "api_sports",
    "blog_rss",
    "trends",
    "news",
    "web_search",
    "youtube_competitors",
    "twitter",
    "reddit",
    "tiktok_trends",
    "sports",
    "odds",
    "autocomplete",
    "twitch",
    "igdb",
    "trendingnow",
    "steam",
    "rawg",
    "anime",
    "tmdb",
    "tvmaze",
    "lastfm",
    "musicbrainz",
    "fred",
    "finnhub",
    "sec_edgar",
    "coingecko",
    "tapology",
    "ufc_context",
)


def section(title: str, print_fn=emit):
    from core.ascii_art import section_glyph
    from core.ui_theme import banner_line, terminal_width
    from core.ui_theme import title as theme_title

    width = terminal_width()
    print_fn()
    glyph = section_glyph(title)
    print_fn(banner_line("=", width))
    print_fn(theme_title(f"{glyph}{title}".rstrip()))
    print_fn(banner_line("=", width))


def subsection(title: str, print_fn=emit):
    from core.ui_theme import subsection_label

    print_fn()
    print_fn(subsection_label(title))


def format_timing(seconds: float) -> str:
    return f"{seconds:.1f}s"


def display_database_status(print_fn=emit):
    from config.settings import get_settings

    get_settings()
    if not (os.getenv("DATABASE_URL") or os.getenv("DATABASE_KEY")):
        print_fn("  Database: JSON-only (Postgres not configured)")
        return
    try:
        from storage.db import check_database_connection, is_database_configured
    except ModuleNotFoundError:
        print_fn("  Database: missing sqlalchemy — py -m pip install sqlalchemy psycopg2-binary")
        return
    if is_database_configured():
        ok, detail = check_database_connection()
        print_fn(f"  Database: {'OK' if ok else 'ERROR'} — {detail}")
        if ok:
            try:
                from sqlalchemy import inspect

                from storage.db import get_engine

                if "assets" not in inspect(get_engine()).get_table_names():
                    print_fn("  Hint: assets table missing — run: py -m storage.migrate_schema")
            except Exception as exc:
                logger.debug("assets-table hint skipped: %s", exc)


def display_competitor_pulse(channel_id: str, topic: str = "", *, print_fn=emit) -> None:
    from analytics.competitor_context import (
        list_recent_competitor_titles,
        snapshot_age_hours,
    )

    channel_id = resolve_channel_id(channel_id)
    age = snapshot_age_hours(channel_id)
    titles = list_recent_competitor_titles(channel_id, topic=topic, limit=5)
    if not titles and age is None:
        return
    subsection("Competitor pulse", print_fn)
    if age is not None:
        print_fn(f"  Snapshot: {age:.0f}h old")
    for row in titles:
        print_fn(f"  - {row.get('channel', '?')}: {row.get('title', '')[:55]}")


def display_signal_health(signals: dict[str, Any], *, print_fn=emit):
    from core.ui_theme import health_status, warn

    subsection("Signal health", print_fn)

    active, issues, inactive = [], [], []
    all_names = list(SIGNAL_ORDER) + [n for n in signals if n not in SIGNAL_ORDER]
    for name in all_names:
        if name not in signals:
            continue
        sig = signals[name]
        if not sig.get("connected"):
            status = sig.get("status", "")
            if any(k in status.lower() for k in ("quota", "rate", "auth", "key", "no api")):
                issues.append(name)
            else:
                inactive.append(name)
        elif sig.get("active"):
            active.append(name)
        else:
            inactive.append(name)

    if active:
        from core.ui_theme import ok

        print_fn(f"  {ok('Active')} ({len(active)}): " + ", ".join(s.capitalize() for s in active))
    if issues:
        print_fn(
            f"  {warn('Issues')} ({len(issues)}): " + ", ".join(s.capitalize() for s in issues)
        )
    try:
        from datetime import datetime

        from apis.register_signals import signal_cooldowns

        cooldowns = signal_cooldowns()
        if cooldowns:
            parts = [
                f"{name} → {datetime.fromtimestamp(until).strftime('%H:%M')}"
                for name, until in sorted(cooldowns.items())
            ]
            print_fn(f"  {warn('Cooling down')} (rate-limited): " + ", ".join(parts))
    except Exception as exc:
        logger.debug("Signal cooldown line skipped: %s", exc)
    print_fn(f"  Inactive/no match: {len(inactive)} signals  (type 'v' to expand)")
    print_fn()

    from core.ask import ask_text

    expand = ask_text("  [Enter to continue / v to view all signals]: ").strip().lower()
    if expand == "v":
        print_fn()
        print_fn(f"  {warn(HEALTH_LEGEND)}")
        print_fn()
        for name in all_names:
            if name in signals:
                line = format_health_line(name, signals[name])
                print_fn(health_status(name.capitalize(), line.split(": ", 1)[-1]))


def display_variants(
    evaluated: list[tuple[str, float, Any]],
    *,
    channel_id: str | None = None,
    raw_scores: dict[str, float] | None = None,
    angle_scores: dict[str, float] | None = None,
    own_idea: str | None = None,
    print_fn=emit,
) -> int:
    """Print variant list; return index of highest score.

    When ``channel_id`` is given, each variant whose title matches a pattern that
    has historically over-engaged on this channel is annotated "▲ proven pattern"
    — the A/B title-pattern loop surfacing learned winners at selection time.
    """
    # Candidate 323: the displayed score is clamped to 100, so on a hot topic every
    # variant prints the same number. Rank on the pre-clamp score when we have it, and
    # say so — a tie presented as a ranking is worse than an admitted tie.
    from core.pipeline import best_variant_index

    raw = raw_scores or {}
    angle = angle_scores or {}
    best_i = best_variant_index(evaluated, raw, angle)
    try:
        from core.ask_bridge import current_bridge

        bridge = current_bridge()
        if bridge is not None:
            bridge.set_choices([str(row[0]) for row in evaluated])
    except Exception as exc:
        logger.debug("gui angle list skipped: %s", exc)
    shown = [round(float(s), 2) for _, s, *_ in evaluated]
    display_tied = len(evaluated) > 1 and len(set(shown)) == 1
    raw_values = [raw.get(v) for v, *_ in evaluated]
    raw_known = all(r is not None for r in raw_values)
    angle_values = [angle.get(v) for v, *_ in evaluated]
    angle_breaks_it = (
        all(a is not None for a in angle_values)
        and len({round(float(a), 4) for a in angle_values}) > 1  # type: ignore[arg-type]
    )

    subsection("Scored angles (Enter = best)", print_fn)
    print_fn("  (YouTube title is generated after key facts + script — not here.)")
    own = (own_idea or "").strip()
    if own:
        print_fn(f"    0. {own}  (your idea — type 0 to keep it)")
    if display_tied:
        if raw_known and len({round(float(r), 2) for r in raw_values}) > 1:  # type: ignore[arg-type]
            print_fn(
                f"  All {len(evaluated)} angles hit the {shown[0]:.0f} ceiling — "
                "ordered by headroom above it, not by the printed number."
            )
        elif angle_breaks_it:
            # The signals are pinned across variants, so an identical composite is
            # the norm, not a hot-topic edge case. Say which number actually ranked.
            print_fn(
                f"  All {len(evaluated)} angles scored {shown[0]:.1f} — the trend "
                "signals are identical across angles. Ordered by editorial score "
                "(distinctness, seed fidelity, specificity), shown in brackets."
            )
        else:
            print_fn(
                f"  All {len(evaluated)} angles scored {shown[0]:.1f} — this is a tie, "
                "not a ranking. Pick on editorial judgement."
            )
    from core.ui_theme import paint, score_badge

    winning: frozenset[str] = frozenset()
    feature_tags = None
    if channel_id:
        try:
            from core.title_experiments import winning_tags
            from core.title_features import feature_tags as _feature_tags

            winning = winning_tags(channel_id)
            feature_tags = _feature_tags
        except Exception:
            winning = frozenset()

    for i, (variant, score, _) in enumerate(evaluated, start=1):
        marker = paint("  *", "\033[1m\033[33m") if i - 1 == best_i else "   "
        hint = ""
        if winning and feature_tags:
            hits = [t for t in feature_tags(variant) if t in winning]
            if hits:
                hint = paint(f"  ▲ {hits[0]}", "\033[32m")
        editorial = ""
        if angle_breaks_it and variant in angle:
            editorial = paint(f"  [ed {angle[variant]:.2f}]", "\033[90m")
        print_fn(f"{marker} {i}. {score_badge(score)} {variant}{editorial}{hint}")
    return best_i


def display_fact_preview(
    signal_facts: str,
    research_brief=None,
    *,
    print_fn=emit,
) -> bool:
    """
    Show a compact summary of the facts that went into the script.
    Splits verified facts from YouTube context-only titles for clarity.
    Returns True if facts are thin (warning condition).
    """
    from core.fact_enrichment import _fact_line_count
    from core.ui_theme import ok, warn

    # Separate YouTube context from verified game/news data
    _YT_HEADERS = (
        "YouTube — real video titles",
        "YouTube video descriptions",
        "YouTube market titles",
    )
    verified_lines: list[str] = []
    context_lines: list[str] = []
    in_yt = False
    for line in signal_facts.splitlines():
        s = line.strip()
        if any(s.startswith(h) for h in _YT_HEADERS):
            in_yt = True
            context_lines.append(s)
            continue
        if in_yt and (
            s.startswith("•")
            or s.startswith("→")
            or line.startswith("  •")
            or line.startswith("  →")
        ):
            context_lines.append(s)
            continue
        in_yt = False
        if s and not s.startswith("⚠"):
            verified_lines.append(s)

    "\n".join(verified_lines)
    is_thin = (
        not signal_facts.strip()
        or signal_facts.startswith("No structured facts")
        or signal_facts.startswith("⚠ THIN FACTS")
        or _fact_line_count(signal_facts) < 3
    )

    subsection("Fact quality", print_fn)
    if is_thin:
        print_fn(
            f"  {warn('⚠ Thin facts')} — limited verified data; script will frame as emerging coverage."
        )
    else:
        print_fn(f"  {ok('✓ Facts available')}")

    # Show verified facts first (what the LLM actually used as source-of-truth)
    if verified_lines:
        for line in verified_lines[:8]:
            short = _elide(line, fact_display_width())
            print_fn(f"  {short}")
    else:
        print_fn("  (no verified game/news data — script based on topic angle only)")

    # Show count of context-only competitor titles
    yt_titles = [line for line in context_lines if line.startswith("•")]
    if yt_titles:
        print_fn(f"  + {len(yt_titles)} competitor title(s) in context block (not used as facts)")

    # Show supporting evidence from brief
    if research_brief and hasattr(research_brief, "supporting_evidence"):
        ev = [e for e in (research_brief.supporting_evidence or []) if e][:3]
        if ev:
            print_fn("  Brief evidence:")
            for e in ev:
                print_fn(f"    · {_elide(e, fact_display_width())}")

    return is_thin


def _elide(text: str, width: int) -> str:
    """Shorten for display, saying so. Never severs a word, never silent.

    Run 74 printed link facts as `{ex[:90]}` with no ellipsis, so the operator had
    no way to tell a shortened *line on screen* from a shortened *fact in the
    prompt* — and at the time both were happening. Facts are no longer cut
    (`split_at_sentences`); this makes the display honest about the difference.
    """
    body = (text or "").strip()
    if len(body) <= width:
        return body
    head = body[: max(1, width - 1)]
    if " " in head and not body[width - 1 : width].isspace():
        head = head.rsplit(" ", 1)[0]
    return f"{head.rstrip()}… (+{len(body) - len(head.rstrip())} chars)"


def display_signal_breakdown(signals: dict[str, Any], *, print_fn=emit):
    subsection("Signal breakdown (selected variant)", print_fn)
    print_fn("  (Used in composite = connected + active + score > 0)")
    for name in SIGNAL_ORDER:
        if name not in signals:
            continue
        sig = signals[name]
        score = sig.get("score", 0)
        if sig.get("stale"):
            detail = sig.get("status_detail") or "STALE cache"
            print_fn(f"  {name.capitalize()}: — ({detail})")
        elif sig.get("connected") and sig.get("active") and score > 0:
            print_fn(f"  {name.capitalize()}: {score}")
        else:
            detail = sig.get("status_detail") or sig.get("status", "inactive")
            print_fn(f"  {name.capitalize()}: — ({detail})")
    for name, sig in signals.items():
        if name in SIGNAL_ORDER or name.startswith("_"):
            continue
        score = sig.get("score", 0)
        if sig.get("connected") and sig.get("active") and score > 0:
            print_fn(f"  {name.capitalize()}: {score}")


def _provenance_records(
    collected: list[str],
    *,
    manual_facts: list[str],
    link_provenance: list[tuple[str, str, Any]],
    vault_records: list[tuple[str, Any]],
) -> list[Any]:
    """Attach tier / source / date to the deduped fact pool, for ranking.

    Intake flattens three very different things into one list of strings: lines the
    operator typed (the highest ground truth there is), lines a scraped page gave
    up, and lines borrowed from the vault. Ranking them without that distinction
    would let a scorer demote what the operator typed by hand, so the distinction
    is rebuilt here — keyed on `dedupe_key`, the same identity `dedupe_facts` used
    to collapse them.
    """
    from datetime import date

    from core.fact_store import TIER_LINK, TIER_OPERATOR, TIER_VAULT, FactRecord
    from core.operator_facts import dedupe_key

    today = date.today()
    tiers: dict[str, str] = {}
    dates: dict[str, Any] = {}
    urls: dict[str, str] = {}
    for claim in manual_facts:
        tiers.setdefault(dedupe_key(claim), TIER_OPERATOR)
        dates.setdefault(dedupe_key(claim), today)
    for claim, url, published in link_provenance:
        key = dedupe_key(claim)
        tiers.setdefault(key, TIER_LINK)
        urls.setdefault(key, url)
        if published is not None:
            dates.setdefault(key, published)
    for stamped, record in vault_records:
        key = dedupe_key(stamped)
        tiers.setdefault(key, getattr(record, "tier", TIER_VAULT) or TIER_VAULT)
        verified = getattr(record, "verified_at", None)
        if verified is not None:
            dates.setdefault(key, verified)
        source = getattr(record, "source_url", "") or ""
        if source:
            urls.setdefault(key, source)

    out: list[Any] = []
    for claim in collected:
        key = dedupe_key(claim)
        out.append(
            FactRecord(
                claim=claim,
                tier=tiers.get(key, TIER_LINK),
                source_url=urls.get(key, ""),
                verified_at=dates.get(key),
            )
        )
    return out


@dataclass
class KeyFactSelection:
    """Facts plus the evidence needed to audit and publish their provenance.

    `facts` is what rides in the prompt — already ranked and budget-fitted (run 74).
    `records` is everything collected, with provenance, and `held_back` says which
    of them lost and why. The vault gets `records`, never just `facts`.
    """

    facts: list[str]
    source_urls: list[str]
    relevance_corpus: str
    vault_audit: list[dict[str, Any]]
    records: list[Any] = field(default_factory=list)
    held_back: list[Any] = field(default_factory=list)


def prompt_key_facts_result(
    topic: str,
    channel_id: str = "default",
    *,
    signals: dict[str, Any] | None = None,
    print_fn=emit,
    input_fn=ask_text,
) -> KeyFactSelection:
    """Collect operator facts and return their vault-relevance audit.

    Manual/link facts are collected before the authoritative vault scan so the scorer
    can use them with signal text. Candidate vault facts are never put in their own
    corpus.
    """
    from core.obsidian_facts import is_playbook_line

    subsection("Key facts (ground truth — highest priority)", print_fn)
    print_fn("  Cover the things that go stale — add as many as apply:")
    print_fn("    · Who holds what NOW (champion, ranking, roster, CEO)")
    print_fn("    · Latest result/event + its date")
    print_fn("    · Hard numbers (score, record, odds, price)")
    print_fn("    · Recency anchor (e.g. 'as of June 2026, ...')")

    key_facts: list[str] = []
    vault_accepted: list[str] = []
    manual_facts: list[str] = []
    link_facts: list[str] = []

    print_fn("")
    print_fn("  Add facts — paste a URL, one line, or type `paste` + Enter for a multi-line block.")
    print_fn("  (Trade trackers paste well as a block. Empty line when done.)")
    from core.console_input import input_pending, read_pending_lines
    from core.content_engine import key_facts_for_prompt
    from core.fact_selection import select_facts_for_prompt
    from core.link_facts import (
        extract_facts_from_url,
        is_title_only,
        link_fetch_issue,
        looks_like_url,
    )
    from core.link_facts import last_extract_report as link_extract_report
    from core.operator_facts import (
        capture_facts_to_vault,
        dedupe_facts,
        max_operator_key_facts,
        operator_key_fact_char_budget,
        parse_pasted_block,
        read_multiline_paste,
    )

    pasted_sources: list[dict[str, str]] = []
    # (claim, source url, page publication date) for every line a link produced —
    # the recency signal the selector weights most heavily.
    link_provenance: list[tuple[str, str, Any]] = []
    while True:
        fact = input_fn(
            f"  Fact {len(manual_facts) + len(link_facts) + len(vault_accepted) + 1} "
            f"(or `paste`, empty when done): "
        ).strip()
        if not fact:
            # Run 74: a blank line in the middle of a paste is a paragraph break, not
            # the operator pressing Enter. Ending here dropped ~40 paragraphs of the
            # article and left them buffered to answer the prompts that followed.
            # `read_multiline_paste` has always known this; this prompt did not.
            if input_pending():
                continue
            break
        if fact.lower() == "paste":
            print_fn("  >> Paste your block below ('.' / END / two blank lines when finished):")
            parsed = parse_pasted_block(read_multiline_paste(input_fn))
            if parsed:
                print_fn(f"    Parsed {len(parsed)} fact line(s) from block.")
                manual_facts.extend(parsed)
            else:
                print_fn("    No facts parsed — try shorter lines or one trade per paragraph.")
            continue
        if looks_like_url(fact):
            print_fn("    Fetching link…")
            extracted = extract_facts_from_url(fact)
            if extracted:
                for ex in extracted:
                    print_fn(f"    + {_elide(ex, fact_display_width())}")
                report = link_extract_report()
                found = int(report.get("found") or 0)
                kept = int(report.get("kept") or 0)
                if found > kept:
                    print_fn(
                        f"    ({kept} of {found} line(s) kept — "
                        "raise the page cap if you need the rest)"
                    )
                if is_title_only(extracted):
                    print_fn(
                        "    ⚠ Only got the headline — no article body scraped (JS-heavy page?). "
                        "Paste the article text as facts, or set LINK_READER_PROXY=1 to try a proxy."
                    )
                link_facts.extend(extracted)
                published = report.get("published")
                link_provenance.extend((line, fact, published) for line in extracted)
                pasted_sources.append({"url": fact, "title": extracted[0]})
            else:
                issue = link_fetch_issue(fact)
                msg = issue or "Could not extract facts from that link."
                print_fn(f"    {msg}")
                print_fn("    Tip: type `paste` and paste the article text as a block instead.")
            continue
        if "\n" in fact:
            manual_facts.extend(parse_pasted_block(fact))
        else:
            manual_facts.append(fact)

    # Anything still buffered was pasted, not chosen — offer it back rather than let
    # it drift downstream and auto-answer `Proceed?` (which is how run 74 ended).
    leftover = read_pending_lines()
    if leftover:
        recovered = parse_pasted_block("\n".join(leftover))
        if recovered:
            print_fn(
                f"  {len(leftover)} more pasted line(s) arrived after the blank line "
                f"— {len(recovered)} of them look like facts."
            )
            answer = input_fn("  Add them as facts? [Y/n]: ").strip().lower()
            if answer in ("", "y", "yes"):
                manual_facts.extend(recovered)
                print_fn(f"    + added {len(recovered)} fact(s) from the paste.")
            else:
                print_fn("    Dropped — they will not answer any later prompt.")
        else:
            print_fn(f"  Discarded {len(leftover)} buffered line(s) of pasted text.")

    # Authoritative vault scan. The scorer sees signal evidence plus facts the
    # operator/link fetch supplied, never the candidate fact itself.
    from core.operator_facts import is_writing_tip
    from core.vault_relevance import build_relevance_corpus, compact_reasons

    relevance_corpus = build_relevance_corpus(
        signals or {},
        operator_facts=[*manual_facts, *link_facts],
    )
    vault_error: Exception | None = None
    try:
        from core.obsidian_facts import load_fact_records

        records = load_fact_records(
            topic,
            channel_id,
            require_distinctive=True,
            corpus=relevance_corpus,
        )
    except Exception as exc:
        vault_error = exc
        logger.debug("Vault fact scan unavailable for %r: %s", topic, exc)
        records = []
    records = [
        record
        for record in records
        if not is_writing_tip(record.claim) and not is_playbook_line(record.claim)
    ]
    suggestions = [record.claim for record in records]

    def _is_inspect_reject(record: Any) -> bool:
        return (getattr(record, "relevance_band", "") or "") == "reject"

    uncertain_records = [
        record
        for record in records
        if getattr(record, "uncertain", False) and not _is_inspect_reject(record)
    ]
    confident_records = [
        record
        for record in records
        if not getattr(record, "uncertain", False) and not _is_inspect_reject(record)
    ]
    inspect_rejects = [record for record in records if _is_inspect_reject(record)]
    auto_attach = os.getenv("VAULT_FACTS_AUTO", "true").lower() not in (
        "0",
        "false",
        "no",
    )
    selected_records: list[Any] = []
    overrides: dict[str, str] = {}

    def _record_line(index: int, record: Any) -> str:
        band = getattr(record, "relevance_band", "") or (
            "uncertain" if getattr(record, "uncertain", False) else "confident"
        )
        score = getattr(record, "relevance_score", None)
        suffix = f" [{band}]"
        if isinstance(score, int | float):
            from core.vault_relevance import VaultRelevanceDecision

            decision = VaultRelevanceDecision(
                score=float(score),
                band=band,
                scorer_version=getattr(record, "relevance_scorer_version", ""),
                policy="operator",
                breakdown=dict(getattr(record, "relevance_breakdown", {}) or {}),
            )
            reasons = compact_reasons(decision)
            suffix = f" [{band} {float(score):.2f}"
            if reasons:
                suffix += "; " + ", ".join(reasons)
            suffix += "]"
        return f"    {index}. {_elide(record.claim, 120)}{suffix}"

    if vault_error is not None:
        print_fn("")
        print_fn("  Vault scan unavailable — continuing without suggestions.")
    elif not suggestions:
        print_fn("")
        print_fn("  Vault scan: no topic-relevant facts — skipped.")
    elif auto_attach:
        print_fn("")
        print_fn(
            format_vault_scan_line(
                confident=len(confident_records),
                uncertain=len(uncertain_records),
            )
        )
        for index, record in enumerate(records, 1):
            print_fn(_record_line(index, record))
        if inspect_rejects:
            print_fn(
                f"  {len(inspect_rejects)} near-threshold exclusion(s) listed "
                "above are not attached."
            )
        selected_records.extend(confident_records)
        overrides.update({record.claim: "auto" for record in confident_records})
        overrides.update({record.claim: "rejected" for record in inspect_rejects})
        if uncertain_records:
            choice = (
                input_fn("  Use uncertain facts? [Enter=all / n=none / e.g. '2'=printed number]: ")
                .strip()
                .lower()
            )
            if choice in ("", "y", "yes", "all"):
                chosen = list(uncertain_records)
            elif choice in ("n", "no", "none"):
                chosen = []
            else:
                picked = {
                    int(tok)
                    for tok in choice.replace(",", " ").split()
                    if tok.isdigit() and 1 <= int(tok) <= len(records)
                }
                chosen = [
                    record
                    for index, record in enumerate(records, 1)
                    if index in picked and record in uncertain_records
                ]
            selected_records.extend(chosen)
            chosen_claims = {record.claim for record in chosen}
            overrides.update(
                {
                    record.claim: ("accepted" if record.claim in chosen_claims else "rejected")
                    for record in uncertain_records
                }
            )
    else:
        print_fn("")
        print_fn(f"  From your Obsidian vault ({len(suggestions)} topic-relevant match(es)):")
        for index, record in enumerate(records, 1):
            print_fn(_record_line(index, record))
        choice = input_fn("  Use these? [Enter=all / n=none / e.g. '1 3'=pick]: ").strip().lower()
        if choice in ("", "y", "yes", "all"):
            selected_records = [record for record in records if not _is_inspect_reject(record)]
        elif choice not in ("n", "no", "none"):
            picked = {
                int(tok)
                for tok in choice.replace(",", " ").split()
                if tok.isdigit() and 1 <= int(tok) <= len(records)
            }
            selected_records = [
                record
                for index, record in enumerate(records, 1)
                if index in picked and not _is_inspect_reject(record)
            ]
        selected_claims = {record.claim for record in selected_records}
        overrides.update(
            {
                record.claim: ("accepted" if record.claim in selected_claims else "rejected")
                for record in records
            }
        )
    from core.fact_store import stamp_as_of

    vault_accepted.extend(stamp_as_of(record) for record in selected_records)

    if pasted_sources:
        try:
            from core.source_capture import capture_sources

            saved = capture_sources(channel_id, topic, pasted_sources)
            if saved:
                print_fn(f"    Saved {len(pasted_sources)} source URL(s) to your vault.")
        except Exception as exc:
            logger.debug("capture_sources skipped: %s", exc)

    collected = dedupe_facts(manual_facts + link_facts + vault_accepted)

    # Run 74: choose which facts ride in the prompt, rather than taking the first N
    # in insertion order. This happens here because this is the only place that
    # knows the provenance — who typed what, which page a line came from and when
    # that page was published. Downstream sees the chosen set, so the script
    # prompt, the regeneration loop and the grounding display never disagree.
    fact_records = _provenance_records(
        collected,
        manual_facts=manual_facts,
        link_provenance=link_provenance,
        vault_records=list(zip(vault_accepted, selected_records, strict=False)),
    )
    key_facts, held_back = select_facts_for_prompt(
        fact_records,
        topic=topic,
        corpus=relevance_corpus,
        budget=operator_key_fact_char_budget(),
        line_cap=max_operator_key_facts(),
    )

    # Persist only facts that are NEW to the vault. Re-saving `vault_accepted` would
    # copy borrowed facts into a note titled with THIS topic, permanently stamping
    # them as this topic's facts — a laundering loop: one weak token match pulls a
    # foreign fact in, the write-back re-titles it, and it then matches strongly
    # forever. That is how Marvel Rivals facts ended up in an MMA-rankings note.
    new_facts = dedupe_facts(manual_facts + link_facts)

    if new_facts:
        try:
            from core.fact_intake import lint_fact_intake

            vault_claims = [str(getattr(r, "claim", "") or "") for r in records]
            for warn in lint_fact_intake(new_facts, vault_claims=vault_claims):
                print_fn(f"  intake: {warn}")
        except Exception as exc:
            logger.debug("fact intake lint skipped: %s", exc)
        saved_path = capture_facts_to_vault(channel_id, topic, new_facts)
        if saved_path:
            print_fn(f"  Saved all {len(new_facts)} fact(s) to vault (full set, no cap).")

    if key_facts:
        from core.operator_facts import last_fact_budget_report

        sent = key_facts_for_prompt(key_facts)
        budget = operator_key_fact_char_budget()
        report = last_fact_budget_report()
        # Both limits, always — the operator read "18 packed" as a hard 18-fact cap
        # because only the char side of the budget was ever shown.
        print_fn(
            f"  {len(collected)} fact(s) collected; {len(sent)} packed for the LLM "
            f"({len(sent)}/{max_operator_key_facts()} lines · "
            f"{sum(len(s) for s in sent)}/{budget} chars)."
        )
        if held_back:
            scaffolding = sum(1 for drop in held_back if "scaffolding" in drop.reason)
            parts = []
            if scaffolding:
                parts.append(f"{scaffolding} article scaffolding")
            if len(held_back) - scaffolding:
                parts.append(f"{len(held_back) - scaffolding} lower-ranked than the budget held")
            print_fn(f"  {len(held_back)} held back — {' · '.join(parts)}. All saved to the vault.")
            for drop in held_back[:3]:
                print_fn(f"    · {_elide(drop.claim, 72)}")
            if len(held_back) > 3:
                print_fn(f"    · …and {len(held_back) - 3} more")
        if report.get("dropped"):
            print_fn(
                f"  Note: {report['dropped']} fact(s) stored in vault but omitted "
                f"from the prompt — {report.get('reason') or 'budget reached'}."
            )
    selected_claims = {record.claim for record in selected_records}
    vault_audit: list[dict[str, Any]] = []
    for record in records:
        legacy_attaches = getattr(record, "legacy_attaches", None)
        if legacy_attaches is True:
            pre_score = (
                "legacy_uncertain"
                if not getattr(record, "legacy_attaches", False)
                or getattr(record, "uncertain", False)
                else "legacy_attach"
            )
        elif legacy_attaches is False:
            pre_score = "legacy_reject"
        else:
            pre_score = (
                "legacy_uncertain" if getattr(record, "uncertain", False) else "legacy_attach"
            )
        band = getattr(record, "relevance_band", "") or (
            "uncertain" if getattr(record, "uncertain", False) else "confident"
        )
        vault_audit.append(
            {
                "claim": record.claim,
                "note_path": getattr(record, "note_path", ""),
                "source_url": getattr(record, "source_url", ""),
                "pre_score_verdict": pre_score,
                "band": band,
                "score": getattr(record, "relevance_score", None),
                "breakdown": dict(getattr(record, "relevance_breakdown", {}) or {}),
                "scorer_version": getattr(record, "relevance_scorer_version", ""),
                "pre_tiebreak_band": getattr(record, "relevance_pre_tiebreak_band", ""),
                "tiebreak_status": getattr(record, "relevance_tiebreak_status", ""),
                "selected": record.claim in selected_claims,
                "operator_override": overrides.get(record.claim, "rejected"),
            }
        )

    source_urls: list[str] = []
    seen_urls: set[str] = set()
    for url in [
        *(str(item.get("url") or "") for item in pasted_sources),
        *(str(getattr(record, "source_url", "") or "") for record in selected_records),
    ]:
        clean = url.strip()
        if not clean or clean.lower() in seen_urls:
            continue
        seen_urls.add(clean.lower())
        source_urls.append(clean)

    return KeyFactSelection(
        facts=key_facts,
        source_urls=source_urls,
        relevance_corpus=relevance_corpus,
        vault_audit=vault_audit,
        records=fact_records,
        held_back=held_back,
    )


def prompt_key_facts(
    topic: str,
    channel_id: str = "default",
    *,
    signals: dict[str, Any] | None = None,
    print_fn=emit,
    input_fn=ask_text,
) -> list[str]:
    """Backward-compatible list-only wrapper around the audited operator flow."""
    return prompt_key_facts_result(
        topic,
        channel_id,
        signals=signals,
        print_fn=print_fn,
        input_fn=input_fn,
    ).facts


def display_grounding_report(
    ungrounded: list[str],
    *,
    key_facts: list[str] | None = None,
    print_fn=emit,
) -> bool:
    """Show post-generation grounding warnings. Returns True when review is needed."""
    from core.content_engine import key_facts_for_prompt

    subsection("Fact grounding", print_fn)
    if not ungrounded:
        print_fn("  ✓ No unsupported specifics detected in the script.")
        sent = key_facts_for_prompt(key_facts) if key_facts else []
        if sent:
            print_fn(f"  Operator key facts sent to LLM ({len(sent)}):")
            for i, fact in enumerate(sent, 1):
                print_fn(f"    {i}. {_elide(fact, fact_display_width())}")
        return False

    print_fn(
        f"  ⚠ {len(ungrounded)} specific(s) in the script are NOT backed by verified facts "
        f"(possible hallucination):"
    )
    for ent in ungrounded[:12]:
        print_fn(f"    · {ent}")
    if len(ungrounded) > 12:
        print_fn(f"    · …and {len(ungrounded) - 12} more")
    print_fn(
        "  These passed the authenticity gate (structure/take) but failed token grounding. "
        "Add them as key facts or edit the script before publishing."
    )
    sent = key_facts_for_prompt(key_facts) if key_facts else []
    if sent:
        print_fn(f"  Key facts that reached the LLM ({len(sent)}):")
        for i, fact in enumerate(sent, 1):
            print_fn(f"    {i}. {_elide(fact, fact_display_width())}")
    return True


def format_vault_scan_line(*, confident: int, uncertain: int) -> str:
    """The vault-scan headline, splitting proven matches from unproven ones (329 P0).

    A note relevant on token evidence but sharing no franchise anchor with the topic
    used to be dropped silently — which also dropped notes about the people and
    companies in the story. It is kept and counted here instead, so a wrong call is
    visible and correctable rather than invisible.
    """
    total = confident + uncertain
    if not uncertain:
        return f"  Vault scan: auto-attached {total} topic-relevant fact(s):"
    return (
        f"  Vault scan: {confident} confident fact(s) auto-attached; "
        f"{uncertain} uncertain (subject unproven; review below):"
    )


def display_fact_engine_report(features: dict, *, print_fn=emit) -> bool:
    """Pillar 3 surface — pre-script conflicts, grounding-tier lint, claim verifier.

    Reads the features the pipeline persisted for this run. Returns True when
    anything needs operator review (all advisory; only GROUNDING_GATE=block
    turns the verifier verdict into a hard stop).
    """
    from core.claim_verifier import display_claim_verification
    from core.fact_conflicts import display_fact_conflicts

    features = features or {}
    needs_review = display_fact_conflicts(
        features.get("fact_conflicts") or [],
        dropped=int(features.get("fact_conflicts_dropped") or 0),
        print_fn=print_fn,
    )
    if features.get("disputed"):
        print_fn("\n  DISPUTED — operator facts won; these source claims lost:")
        for claim in (features.get("disputed_claims") or [])[:6]:
            print_fn(f"    - {claim}")
        needs_review = True

    tier_warnings = features.get("tier_warnings") or []
    if tier_warnings:
        print_fn(f"\n  ⚠ Grounding tiers ({len(tier_warnings)}):")
        for warning in tier_warnings[:8]:
            print_fn(f"    · {warning}")
        needs_review = True

    # Candidate 321 — the title used to be the one string no check read.
    title_warnings = features.get("title_warnings") or []
    if title_warnings:
        print_fn(f"\n  ⚠ Title check ({len(title_warnings)}):")
        for warning in title_warnings[:4]:
            print_fn(f"    · {warning}")
        print_fn("    The title is the first thing viewers read — fix it before publishing.")
        needs_review = True

    # Run 74: these fired and only ever reached the log, so a phrase banned by the
    # script prompt *and* by the linter still graded A. Style, not fact — shown
    # before `Proceed?`, but it does not raise the fact-review flag.
    persona_hits = features.get("persona_lint") or []
    if persona_hits:
        print_fn(f"\n  ⚠ Style ({len(persona_hits)}): banned filler in the script")
        for hit in persona_hits[:4]:
            print_fn(f"    · {hit}")
        print_fn("    Regenerate (+/- at Proceed) or edit before publishing.")

    cta = features.get("cta_summary") or {}
    if isinstance(cta, dict) and cta.get("stripped"):
        pre = int(cta.get("pre_paragraphs") or 0)
        post = int(cta.get("post_paragraphs") or 0)
        print_fn(
            f"\n  Pre-CTA recap stripped ({pre} -> {post} paragraphs). "
            "The published script is the shorter one."
        )

    rhythm = features.get("sentence_rhythm") or []
    if rhythm:
        print_fn(f"\n  ⚠ Sentence rhythm: {rhythm[0]}")
        print_fn("    Uniform sentence length is an LLM tell — regenerate before publishing.")

    if display_claim_verification(features.get("claim_verification"), print_fn=print_fn):
        needs_review = True
    return needs_review


def prompt_channel_selection(*, print_fn=emit, input_fn=ask_text) -> str:
    """Interactive channel picker; returns resolved channel_id."""
    profiles = get_channel_profiles()
    ids = list_channel_ids()
    default_id = resolve_channel_id(get_settings().content_channel_id)

    subsection("Channel", print_fn)
    default_index = ids.index(default_id) if default_id in ids else 0
    for i, cid in enumerate(ids, start=1):
        profile = profiles[cid]
        marker = " *" if i - 1 == default_index else "  "
        domain = f" — {profile.domain}" if profile.domain != "neutral" else ""
        print_fn(f"{marker}{i}. {profile.name} ({cid}){domain}")

    hint = str(default_index + 1)
    choice = input_fn(f"  Select 1-{len(ids)} [Enter = {hint}]: ").strip()
    if not choice:
        return default_id
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(ids):
            return ids[idx]
    return default_id


@dataclass
class UploadPlan:
    """User-selected upload behavior after render."""

    mode: str  # skip | queue
    scheduled_at: datetime | None = None
    privacy_status: str = "private"
    # YouTube publishAt — upload soon, YouTube publishes at this time (no PC at slot)
    youtube_publish_at: datetime | None = None


def display_upload_queue(channel_id: str | None = None, *, print_fn=emit) -> None:
    """Show upcoming YouTube publish slots already reserved for this channel."""
    from analytics.post_timing import format_scheduled_local
    from analytics.upload_queue import list_queue_entries

    channel_id = resolve_channel_id(channel_id)
    entries = list_queue_entries(channel_id)
    subsection("Publish queue", print_fn)
    if not entries:
        print_fn("  (empty — no upcoming scheduled publishes)")
    else:
        if any(not e.on_youtube for e in entries):
            print_fn(
                "  awaiting_upload = target time reserved; MP4 not on YouTube yet "
                "(upload blocked if quota exhausted)"
            )
        print_fn("  #   When (local)              Title / job")
        for i, entry in enumerate(entries, 1):
            when = format_scheduled_local(entry.publish_at, channel_id)
            print_fn(f"  {i}.  {when:<26}  {entry.title[:40]}  [{entry.status}]")
    print_fn(
        "  Deleted a scheduled video on YouTube? "
        "py main.py → Queue manager, or: py -m scripts.queue_manage --channel "
        f"{channel_id}"
    )


def prompt_startup_mode(*, print_fn=emit, input_fn=ask_text) -> str:
    """new_video | queue_manager | intelligence_report | sync_analytics | idea_intake"""
    from core.intelligence_report import intelligence_mode_enabled

    if intelligence_mode_enabled():
        return "intelligence_report"

    subsection("Start", print_fn)
    print_fn("  1) Create new video (discovery pipeline)")
    print_fn("  2) Queue manager — recover / re-queue rendered videos")
    print_fn("  3) Intelligence report only (no script/render)")
    print_fn("  4) Sync YouTube analytics (update performance metrics)")
    print_fn("  5) Make a video from my own idea (paste idea or a YouTube link)")
    choice = input_fn("  Select 1-5 [1]: ").strip() or "1"
    if choice == "2":
        return "queue_manager"
    if choice == "3":
        return "intelligence_report"
    if choice == "4":
        return "sync_analytics"
    if choice == "5":
        return "idea_intake"
    return "new_video"


def prompt_cost_mode(*, print_fn=emit, input_fn=ask_text) -> str:
    """standard | free — pick the run's cost mode. Honors RUN_COST_MODE headless.

    Free ($0) pins TTS/LLM/signals to their zero-cost backends and, in strict mode,
    never calls a paid provider (see core.run_mode). The readiness line shows which
    $0 backends are actually installed so the choice is informed.
    """
    from core.run_mode import (
        COST_MODE_FREE,
        COST_MODE_STANDARD,
        format_readiness_line,
        free_backend_readiness,
        resolve_cost_mode,
    )

    # Non-interactive override: RUN_COST_MODE=free skips the prompt.
    if resolve_cost_mode() == COST_MODE_FREE:
        why = (
            "PAID_CALLS=off"
            if os.getenv("PAID_CALLS", "").strip().lower()
            in (
                "0",
                "off",
                "false",
                "no",
            )
            else "RUN_COST_MODE=free"
        )
        print_fn(f"  Cost mode: Free ($0) [{why}]")
        return COST_MODE_FREE

    subsection("Cost mode", print_fn)
    print_fn("  1) Standard  - best quality (may use paid providers)")
    print_fn("  2) Free ($0) - local voice + free models only, no paid calls")
    try:
        print_fn("  " + format_readiness_line(free_backend_readiness()))
    except Exception as exc:
        logger.debug("Free-mode readiness line skipped: %s", exc)
    choice = input_fn("  Select 1-2 [1]: ").strip() or "1"
    return COST_MODE_FREE if choice == "2" else COST_MODE_STANDARD


def _looks_pasted(raw: str) -> bool:
    """True when an answer is plainly prose, not a fat-fingered menu key (candidate 325).

    Deliberately narrow: a stray character is still a stop (the operator meant to
    decline and missed), while a sentence, a URL or a multi-line block gets one
    re-prompt instead of silently discarding the run.
    """
    text = (raw or "").strip()
    if len(text) > 24 or "\n" in text:
        return True
    return len(text.split()) > 1


# Run 74: three asks, not two. `by` — Engadget's byline label, left in the console
# buffer by a paste at the Fact prompt — is two characters and one word, so the
# run-71 prose detector never saw it, and the run was discarded without a word.
_PROCEED_MAX_ASKS = 3


def prompt_proceed_or_length(
    current_choice: str,
    *,
    print_fn=emit,
    input_fn=ask_text,
) -> tuple[str, str]:
    """Post-generation gate: render, regenerate at a different length, or stop.

    Returns one of:
      ("render", current_choice)  -- y: proceed to render
      ("relength", new_choice)    -- +/-/1-4: regenerate at a new length target
      ("stop", current_choice)    -- n / empty / three unrecognised answers

    "+"/"-" nudge the current preset one step (core.script_length.nudge_length); a 1-4
    entry jumps to that preset. Regeneration is a fresh generate at the new target, so
    grounding + authenticity are re-checked — it is not an in-place trim.

    **Only an explicit decline stops.** `n` / `N` / `no` / Enter still resolve on the
    first answer, exactly as they always have. Everything else re-prompts. Candidate
    325 gave that second chance to *obvious prose* only, which run 74 proved too
    narrow: the leftover line that landed here was the single word `by`, and losing a
    run to a two-character token is never what the operator meant. A misplaced
    keystroke costs one Enter; the old rule cost the whole script.

    Buffered input is drained first (core.console_input) so a paste physically cannot
    answer this gate — the re-prompt is the second line of defence, not the first.
    """
    from core.console_input import read_pending_lines
    from core.script_length import nudge_length

    stale = read_pending_lines()
    if stale:
        print_fn(
            f"  Ignored {len(stale)} buffered line(s) left over from a paste — "
            "they cannot answer this."
        )

    prompt = "  Proceed? [y = render / + longer / - shorter / 1-4 length / N = stop]: "
    for attempt in range(_PROCEED_MAX_ASKS):
        raw = input_fn(prompt).strip().lower()
        if raw == "y":
            return ("render", current_choice)
        if raw == "+":
            return ("relength", nudge_length(current_choice, 1))
        if raw == "-":
            return ("relength", nudge_length(current_choice, -1))
        if raw in ("1", "2", "3", "4"):
            return ("relength", raw)
        # An explicit decline, or an empty line, stops immediately as it always has.
        if raw in ("", "n", "no"):
            return ("stop", current_choice)
        if attempt == _PROCEED_MAX_ASKS - 1:
            break
        if _looks_pasted(raw):
            print_fn(
                f"  That looks like pasted text ({len(raw)} chars), not a menu choice — "
                "the script is still here."
            )
        else:
            print_fn(f"  '{raw}' isn't one of the options — the script is still here.")
        print_fn(
            "  y = render · N = stop · +/- or 1-4 = different length. "
            "(Article text belongs at the Fact prompt, via `paste`.)"
        )
    return ("stop", current_choice)


def _prompt_timing_and_privacy(
    channel_id: str,
    title: str,
    *,
    print_fn=emit,
    input_fn=ask_text,
):
    """Shared 'when + privacy' sub-prompt for the queue manager.

    Returns (scheduled_at, youtube_publish_at, privacy_status): scheduled_at is always
    now (the worker claims it); youtube_publish_at is set only for the scheduled option.
    """
    from datetime import datetime, timezone

    from analytics.post_timing import format_scheduled_local, next_optimal_post_time

    profile = get_channel_profile(channel_id)
    default_priv = profile.privacy_status_default or "private"

    subsection("When", print_fn)
    print_fn("  1) Queue now — upload on the next worker run")
    print_fn("  2) Schedule — next optimal YouTube slot (topic-aware)")
    when = input_fn("  Select 1-2 [1]: ").strip() or "1"

    privacy_map = {"1": "private", "2": "unlisted", "3": "public"}
    default_key = next((k for k, v in privacy_map.items() if v == default_priv), "1")
    subsection("Privacy", print_fn)
    print_fn(f"  1) Private  2) Unlisted  3) Public  (default: {default_priv})")
    print_fn("  Public is held unlisted first so you can eyeball the watch URL.")
    priv = input_fn(f"  Select 1-3 [{default_key}]: ").strip() or default_key
    privacy = privacy_map.get(priv, default_priv)

    publish_at = None
    if when == "2":
        publish_at = next_optimal_post_time(channel_id, title)
        print_fn(f"  YouTube publish at: {format_scheduled_local(publish_at, channel_id)}")

    return datetime.now(timezone.utc), publish_at, privacy


def _recover_rendered_upload(channel_id, recyclable, *, print_fn=emit, input_fn=ask_text) -> None:
    """Queue an upload for a rendered-but-never-uploaded run (folds in requeue_upload)."""
    import json

    from core.thumbnail_pick import ensure_thumbnail_ready
    from scripts.requeue_upload import _resolve_mp4_path
    from storage.repositories.jobs import enqueue_upload_job

    subsection("Recover rendered video (never uploaded)", print_fn)
    for i, run in enumerate(recyclable, 1):
        title = (run.title or run.selected_topic or "")[:60]
        print_fn(f"  {i}. [run {run.id}] {title}")
        print_fn(f"       {_resolve_mp4_path(run)}")

    raw = input_fn("\n  Pick # to queue (Enter = cancel): ").strip()
    if not raw or not raw.isdigit():
        print_fn("  Cancelled.")
        return
    idx = int(raw) - 1
    if idx < 0 or idx >= len(recyclable):
        print_fn("  Invalid selection.")
        return

    run = recyclable[idx]
    mp4 = _resolve_mp4_path(run)
    if not mp4:
        print_fn("  That run has no MP4 on disk anymore.")
        return

    title = run.title or run.selected_topic or ""
    scheduled_at, publish_at, privacy = _prompt_timing_and_privacy(
        channel_id, title, print_fn=print_fn, input_fn=input_fn
    )
    try:
        tags = json.loads(run.tags_json or "[]")
        if not isinstance(tags, list):
            tags = []
    except (TypeError, ValueError):
        tags = []
    thumbnail_path = ensure_thumbnail_ready(run.id)

    job = enqueue_upload_job(
        channel_id=channel_id,
        content_run_id=run.id,
        file_path=mp4,
        title=title,
        description=run.description or "",
        tags=tags,
        privacy_status=privacy,
        scheduled_at=scheduled_at,
        youtube_publish_at=publish_at,
        thumbnail_path=thumbnail_path,
    )
    print_fn(f"\n  Queued upload job {job.id} for run {run.id}. Run: py -m jobs.worker --loop 30")
    print_fn(f"  File: {mp4}")


def _requeue_deleted(channel_id, candidates, *, print_fn=emit, input_fn=ask_text) -> None:
    """Re-queue a run whose prior upload/schedule was deleted on YouTube."""
    from datetime import datetime, timezone

    from analytics.post_timing import format_scheduled_local, next_optimal_post_time
    from analytics.queue_manager import (
        format_requeue_menu_line,
        requeue_content_run,
        reset_publish_for_requeue,
    )

    profile = get_channel_profile(channel_id)

    subsection("Re-queue (deleted on YouTube before publish)", print_fn)
    for i, c in enumerate(candidates, 1):
        print_fn(f"  {i}. {format_requeue_menu_line(c, channel_id)}")

    raw = input_fn("\n  Pick run # to re-queue (Enter = cancel): ").strip()
    if not raw or not raw.isdigit():
        print_fn("  Cancelled.")
        return

    idx = int(raw) - 1
    if idx < 0 or idx >= len(candidates):
        print_fn("  Invalid selection.")
        return

    picked = candidates[idx]
    print_fn(f"\n  Selected run {picked.content_run_id}: {picked.title[:60]}")

    subsection("Re-queue action", print_fn)
    print_fn("  1) Reset only — clear publish_log (no upload job)")
    print_fn("  2) Re-queue now — upload immediately")
    print_fn("  3) Re-queue + schedule — next optimal YouTube slot")
    action = input_fn("  Select 1-3 [3]: ").strip() or "3"

    if action == "1":
        ok = reset_publish_for_requeue(picked.content_run_id, channel_id)
        print_fn("  Reset OK." if ok else "  Nothing to reset.")
        return

    privacy_map = {"1": "private", "2": "unlisted", "3": "public"}
    default_priv = profile.privacy_status_default or "private"
    default_key = next((k for k, v in privacy_map.items() if v == default_priv), "1")
    subsection("Privacy", print_fn)
    print_fn(f"  1) Private  2) Unlisted  3) Public  (default: {default_priv})")
    print_fn("  Public is held unlisted first so you can eyeball the watch URL.")
    priv = input_fn(f"  Select 1-3 [{default_key}]: ").strip() or default_key
    privacy = privacy_map.get(priv, default_priv)

    publish_at = None
    if action == "3":
        publish_at = next_optimal_post_time(channel_id, picked.title)
        print_fn(f"  YouTube publish at: {format_scheduled_local(publish_at, channel_id)}")

    try:
        job_id = requeue_content_run(
            picked.content_run_id,
            channel_id,
            privacy_status=privacy,
            youtube_publish_at=publish_at,
            scheduled_at=datetime.now(timezone.utc),
        )
        print_fn(f"\n  Queued job {job_id}. Run: py -m jobs.worker --loop 30")
    except ValueError as exc:
        print_fn(f"\n  Error: {exc}")


def run_queue_manager_interactive(
    channel_id: str,
    *,
    print_fn=emit,
    input_fn=ask_text,
) -> None:
    """Recover a rendered-but-unuploaded video, or re-queue one deleted on YouTube."""
    from analytics.queue_manager import list_requeue_candidates
    from scripts.requeue_upload import list_recyclable

    channel_id = resolve_channel_id(channel_id)

    section("Queue manager", print_fn)
    display_upload_queue(channel_id, print_fn=print_fn)

    try:
        recyclable = list_recyclable(channel_id)
    except Exception:
        recyclable = []
    candidates = list_requeue_candidates(channel_id)

    if not recyclable and not candidates:
        subsection("Nothing to recover", print_fn)
        print_fn("  No rendered-but-unuploaded videos and no deleted-on-YouTube runs.")
        return

    mode = "recover"
    if recyclable and candidates:
        subsection("What to do", print_fn)
        print_fn(f"  1) Recover a rendered video never uploaded ({len(recyclable)})")
        print_fn(f"  2) Re-queue a deleted-on-YouTube video ({len(candidates)})")
        pick = input_fn("  Select 1-2 [1]: ").strip() or "1"
        mode = "requeue" if pick == "2" else "recover"
    elif candidates:
        mode = "requeue"

    if mode == "recover":
        _recover_rendered_upload(channel_id, recyclable, print_fn=print_fn, input_fn=input_fn)
    else:
        _requeue_deleted(channel_id, candidates, print_fn=print_fn, input_fn=input_fn)


def prompt_upload_plan(
    *,
    channel_id: str | None = None,
    topic: str = "",
    print_fn=emit,
    input_fn=ask_text,
) -> UploadPlan:
    """Interactive upload timing and privacy (no CLI flags)."""
    from analytics.post_timing import (
        format_scheduled_local,
        next_optimal_post_time,
        parse_local_time_input,
    )

    profile = get_channel_profile(channel_id)
    default_priv = profile.privacy_status_default or "private"

    display_upload_queue(channel_id, print_fn=print_fn)

    optimal_at = next_optimal_post_time(channel_id or "default", topic)
    optimal_label = format_scheduled_local(optimal_at, channel_id or "default")

    subsection("Upload", print_fn)
    print_fn("  1) Skip — do not upload")
    print_fn("  2) Queue now — worker uploads when you run: py -m jobs.worker")
    print_fn("  3) Queue later — enter a time (e.g. 9:30pm, tomorrow 6pm) or minutes")
    print_fn(f"  4) Schedule on YouTube for {optimal_label} — next open slot (topic-aware)")
    print_fn("  5) Recover / re-queue a rendered video — open queue manager")
    timing = input_fn("  Select 1-5 [1]: ").strip() or "1"

    if timing == "5":
        run_queue_manager_interactive(channel_id or "default", print_fn=print_fn, input_fn=input_fn)
        return UploadPlan(mode="skip")

    if timing == "1":
        return UploadPlan(mode="skip")

    privacy_map = {"1": "private", "2": "unlisted", "3": "public"}
    default_key = next(
        (k for k, v in privacy_map.items() if v == default_priv),
        "1",
    )
    subsection("Privacy", print_fn)
    print_fn(f"  1) Private  2) Unlisted  3) Public  (channel default: {default_priv})")
    print_fn("  Public is held unlisted first so you can eyeball the watch URL.")
    priv = input_fn(f"  Select 1-3 [{default_key}]: ").strip() or default_key
    privacy_status = privacy_map.get(priv, default_priv)

    now = datetime.now(timezone.utc)
    if timing == "2":
        return UploadPlan(mode="queue", scheduled_at=now, privacy_status=privacy_status)

    if timing == "3":
        raw = input_fn(
            "  Upload time — 9:30pm, tomorrow 6pm, 2026-07-25 18:00, or minutes [60]: "
        ).strip()
        scheduled = parse_local_time_input(raw, channel_id or "default", after=now) if raw else None
        if scheduled is None:
            # Empty or not a time ⇒ treat as legacy minutes-from-now (bare number / default 60).
            try:
                minutes = max(1, int(raw)) if raw else 60
            except ValueError:
                minutes = 60
            scheduled = now + timedelta(minutes=minutes)
        # The local worker claims when scheduled_at <= now, so never schedule in the past.
        min_at = now + timedelta(minutes=1)
        if scheduled < min_at:
            scheduled = min_at
        print_fn(f"  Scheduled for: {format_scheduled_local(scheduled, channel_id or 'default')}")
        return UploadPlan(
            mode="queue",
            scheduled_at=scheduled,
            privacy_status=privacy_status,
        )

    if timing == "4":
        publish_at = next_optimal_post_time(channel_id or "default", topic, after=now)
        label = format_scheduled_local(publish_at, channel_id or "default")
        print_fn(f"  YouTube will publish at: {label}")
        print_fn(
            "  Run worker once to upload the file; your PC does not need to be on at publish time."
        )
        if privacy_status == "unlisted":
            print_fn(
                "  Note: YouTube scheduled API publishes as public at that time; "
                "use private + manual if you need unlisted."
            )
        return UploadPlan(
            mode="queue",
            scheduled_at=now,
            youtube_publish_at=publish_at,
            privacy_status=privacy_status,
        )

    return UploadPlan(mode="skip")


def display_summary(
    *,
    timings: dict[str, float],
    title: str,
    mp4_path: str = "",
    thumbnail_path: str = "",
    cost: dict[str, float] | None = None,
    script: str = "",
    print_fn=emit,
):
    subsection("Summary", print_fn)
    if timings.get("signals_and_variants"):
        print_fn(f"  Discovery: {format_timing(timings['signals_and_variants'])}")
    if timings.get("variant_scoring"):
        print_fn(f"  Variant scoring: {format_timing(timings['variant_scoring'])}")
    print_fn(f"  Title: {title}")
    if mp4_path:
        print_fn(f"  Video: {mp4_path}")
    if thumbnail_path:
        print_fn(f"  Thumbnail: {thumbnail_path}")

    from core.cost_meter import escaped_free_first, format_cost_line, llm_cost_by_provider

    # Per-provider LLM split (O12): the free-first chain means most calls should land
    # on a $0 provider, which the aggregate `llm $x` hides. Fail-open to the plain line.
    try:
        from core.cost_meter import llm_cost_by_stage
        from core.llm_router import get_usage

        usage = get_usage()
        by_provider = llm_cost_by_provider(usage)
        by_stage = llm_cost_by_stage(usage)
    except Exception:
        by_provider = {}
        by_stage = {}
    cost_line = format_cost_line(
        cost,
        llm_by_provider=by_provider,
        llm_by_stage=by_stage,
        escaped_free_first_llm=escaped_free_first(),
    )
    if cost_line:
        print_fn(f"  {cost_line}")
    if cost is not None:
        try:
            from core.pinned_status import set_pin_cost

            set_pin_cost(float(cost.get("total") or 0.0))
        except Exception as exc:
            logger.debug("pin cost skipped: %s", exc)
    try:
        from core.operator_timer import format_line as operator_time_line

        op_line = operator_time_line()
        if op_line:
            print_fn(f"  {op_line}")
    except Exception as exc:
        logger.debug("operator timer line skipped: %s", exc)
    try:
        from core.cost_meter import format_standard_billed_line

        std = format_standard_billed_line(script)
        if std:
            print_fn(f"  {std}")
    except Exception as exc:
        logger.debug("standard-billed line skipped: %s", exc)

    from apis.apify_client import apify_disabled, apify_status

    if apify_disabled():
        print_fn(f"  ⚠ Apify disabled this session — {apify_status()}")
