"""CLI presentation helpers."""

import os
import sys
import threading
import time
from dataclasses import dataclass
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
            self._themed_phase = lambda p: p
        self._typical = self._load_typical_timings()

    @staticmethod
    def _load_typical_timings() -> dict[str, float]:
        """Phase timings from the most recent run trace ("typ ~Ns" hints). Fail-open."""
        try:
            from core.run_trace import list_traces

            for trace in list_traces(limit=3):
                timings = trace.get("timings") or {}
                if timings:
                    return {k: float(v) for k, v in timings.items() if isinstance(v, int | float)}
        except Exception:
            pass
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


def print_domain_art(domain: str, *, topic: str = "", print_fn=print) -> None:
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


def print_bonus_art(*, key: str | None = None, print_fn=print) -> None:
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


def print_celebration(*, print_fn=print) -> None:
    """Publish-success flourish: the active theme's celebration piece, else random."""
    try:
        from core.themes import active_theme

        key = active_theme().celebration_key or None
    except Exception:
        key = None
    print_bonus_art(key=key, print_fn=print_fn)


# Publish counts that earn a milestone line (kept sparse so it stays special).
_MILESTONES = (1, 5, 10, 25, 50, 100, 250, 500, 1000)


def maybe_print_milestone(channel_id: str, *, print_fn=print) -> None:
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


def section(title: str, print_fn=print):
    from core.ascii_art import section_glyph
    from core.ui_theme import banner_line, terminal_width
    from core.ui_theme import title as theme_title

    width = terminal_width()
    print_fn()
    glyph = section_glyph(title)
    print_fn(banner_line("=", width))
    print_fn(theme_title(f"{glyph}{title}".rstrip()))
    print_fn(banner_line("=", width))


def subsection(title: str, print_fn=print):
    from core.ui_theme import subsection_label

    print_fn()
    print_fn(subsection_label(title))


def format_timing(seconds: float) -> str:
    return f"{seconds:.1f}s"


def display_database_status(print_fn=print):
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
            except Exception:
                pass


def display_competitor_pulse(channel_id: str, topic: str = "", *, print_fn=print) -> None:
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


def display_signal_health(signals: dict[str, Any], *, print_fn=print):
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
    except Exception:
        pass
    print_fn(f"  Inactive/no match: {len(inactive)} signals  (type 'v' to expand)")
    print_fn()

    expand = input("  [Enter to continue / v to view all signals]: ").strip().lower()
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
    print_fn=print,
) -> int:
    """Print variant list; return index of highest score.

    When ``channel_id`` is given, each variant whose title matches a pattern that
    has historically over-engaged on this channel is annotated "▲ proven pattern"
    — the A/B title-pattern loop surfacing learned winners at selection time.
    """
    best_i = max(range(len(evaluated)), key=lambda i: evaluated[i][1])
    subsection("Scored angles (Enter = best)", print_fn)
    print_fn("  (YouTube title is generated after key facts + script — not here.)")
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
        print_fn(f"{marker} {i}. {score_badge(score)} {variant}{hint}")
    return best_i


def display_fact_preview(
    signal_facts: str,
    research_brief=None,
    *,
    print_fn=print,
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
            short = line[:100] + ("…" if len(line) > 100 else "")
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
                print_fn(f"    · {e[:100]}")

    return is_thin


def display_signal_breakdown(signals: dict[str, Any], *, print_fn=print):
    subsection("Signal breakdown (selected variant)", print_fn)
    print_fn("  (Used in composite = connected + active + score > 0)")
    for name in SIGNAL_ORDER:
        if name not in signals:
            continue
        sig = signals[name]
        score = sig.get("score", 0)
        if sig.get("connected") and sig.get("active") and score > 0:
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


def prompt_key_facts(
    topic: str,
    channel_id: str = "default",
    *,
    print_fn=print,
    input_fn=input,
) -> list[str]:
    """Collect operator key facts (ground truth) for the script.

    Pre-fills suggestions from the Obsidian vault (if configured), then lets the
    operator accept/edit them and add more. Entry is open-ended (not capped) and
    guided across the relevancy categories that actually go stale, so the facts
    cover identity, latest result, hard numbers, and a recency anchor.
    """
    from core.obsidian_facts import is_playbook_line, load_facts

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

    # Vault scan: only TOPIC-distinctive facts are considered (a Palworld topic can
    # never surface NBA facts). Relevant matches auto-attach by default — no manual
    # accept/reject step; VAULT_FACTS_AUTO=false restores the pick prompt.
    try:
        suggestions = load_facts(topic, channel_id, require_distinctive=True)
    except Exception:
        suggestions = []
    from core.operator_facts import is_writing_tip

    suggestions = [s for s in suggestions if not is_writing_tip(s) and not is_playbook_line(s)]
    auto_attach = os.getenv("VAULT_FACTS_AUTO", "true").lower() not in ("0", "false", "no")
    if not suggestions:
        print_fn("")
        print_fn("  Vault scan: no topic-relevant facts — skipped.")
    elif auto_attach:
        print_fn("")
        print_fn(f"  Vault scan: auto-attached {len(suggestions)} topic-relevant fact(s):")
        for i, fact in enumerate(suggestions, 1):
            print_fn(f"    {i}. {fact[:120]}")
        vault_accepted.extend(suggestions)
    else:
        print_fn("")
        print_fn(f"  From your Obsidian vault ({len(suggestions)} topic-relevant match(es)):")
        for i, fact in enumerate(suggestions, 1):
            print_fn(f"    {i}. {fact}")
        choice = input_fn("  Use these? [Enter=all / n=none / e.g. '1 3'=pick]: ").strip().lower()
        if choice in ("", "y", "yes", "all"):
            vault_accepted.extend(suggestions)
        elif choice not in ("n", "no", "none"):
            for tok in choice.replace(",", " ").split():
                if tok.isdigit() and 1 <= int(tok) <= len(suggestions):
                    vault_accepted.append(suggestions[int(tok) - 1])

    print_fn("")
    print_fn("  Add facts — paste a URL, one line, or type `paste` + Enter for a multi-line block.")
    print_fn("  (Trade trackers paste well as a block. Empty line when done.)")
    from core.content_engine import key_facts_for_prompt
    from core.link_facts import (
        extract_facts_from_url,
        is_title_only,
        link_fetch_issue,
        looks_like_url,
    )
    from core.operator_facts import (
        capture_facts_to_vault,
        dedupe_facts,
        operator_key_fact_char_budget,
        parse_pasted_block,
    )

    pasted_sources: list[dict[str, str]] = []
    while True:
        fact = input_fn(
            f"  Fact {len(manual_facts) + len(link_facts) + len(vault_accepted) + 1} "
            f"(or `paste`, empty when done): "
        ).strip()
        if not fact:
            break
        if fact.lower() == "paste":
            print_fn("  >> Paste your block below (blank line when finished):")
            block_lines: list[str] = []
            while True:
                line = input_fn("    ").strip()
                if not line:
                    break
                block_lines.append(line)
            parsed = parse_pasted_block("\n".join(block_lines))
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
                    print_fn(f"    + {ex[:90]}")
                if is_title_only(extracted):
                    print_fn(
                        "    ⚠ Only got the headline — no article body scraped (JS-heavy page?). "
                        "Paste the article text as facts, or set LINK_READER_PROXY=1 to try a proxy."
                    )
                link_facts.extend(extracted)
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

    if pasted_sources:
        try:
            from core.source_capture import capture_sources

            saved = capture_sources(channel_id, topic, pasted_sources)
            if saved:
                print_fn(f"    Saved {len(pasted_sources)} source URL(s) to your vault.")
        except Exception:
            pass

    key_facts = dedupe_facts(manual_facts + link_facts + vault_accepted)

    if key_facts:
        saved_path = capture_facts_to_vault(channel_id, topic, key_facts)
        if saved_path:
            print_fn(f"  Saved all {len(key_facts)} fact(s) to vault (full set, no cap).")
        sent = key_facts_for_prompt(key_facts)
        budget = operator_key_fact_char_budget()
        print_fn(
            f"  {len(key_facts)} fact(s) collected; {len(sent)} packed for the LLM "
            f"({sum(len(s) for s in sent)} / {budget} chars)."
        )
        if len(sent) < len(key_facts):
            skipped = len(key_facts) - len(sent)
            print_fn(
                f"  Note: {skipped} fact(s) stored in vault but omitted from prompt "
                f"(char budget — raise OPERATOR_KEY_FACT_CHAR_BUDGET if needed)."
            )
    return key_facts


def display_grounding_report(
    ungrounded: list[str],
    *,
    key_facts: list[str] | None = None,
    print_fn=print,
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
                short = fact[:90] + ("…" if len(fact) > 90 else "")
                print_fn(f"    {i}. {short}")
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
            short = fact[:90] + ("…" if len(fact) > 90 else "")
            print_fn(f"    {i}. {short}")
    return True


def display_fact_engine_report(features: dict, *, print_fn=print) -> bool:
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

    tier_warnings = features.get("tier_warnings") or []
    if tier_warnings:
        print_fn(f"\n  ⚠ Grounding tiers ({len(tier_warnings)}):")
        for warning in tier_warnings[:8]:
            print_fn(f"    · {warning}")
        needs_review = True

    if display_claim_verification(features.get("claim_verification"), print_fn=print_fn):
        needs_review = True
    return needs_review


def prompt_channel_selection(*, print_fn=print, input_fn=input) -> str:
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


def display_upload_queue(channel_id: str | None = None, *, print_fn=print) -> None:
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


def prompt_startup_mode(*, print_fn=print, input_fn=input) -> str:
    """new_video | queue_manager | intelligence_report | sync_analytics | idea_intake"""
    from core.intelligence_report import intelligence_mode_enabled

    if intelligence_mode_enabled():
        return "intelligence_report"

    subsection("Start", print_fn)
    print_fn("  1) Create new video (discovery pipeline)")
    print_fn("  2) Queue manager — re-queue after YouTube delete")
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


def run_queue_manager_interactive(
    channel_id: str,
    *,
    print_fn=print,
    input_fn=input,
) -> None:
    """Interactive re-queue flow for deleted scheduled videos."""
    from datetime import datetime, timezone

    from analytics.post_timing import format_scheduled_local, next_optimal_post_time
    from analytics.queue_manager import (
        format_requeue_menu_line,
        list_requeue_candidates,
        requeue_content_run,
        reset_publish_for_requeue,
    )

    channel_id = resolve_channel_id(channel_id)
    profile = get_channel_profile(channel_id)

    section("Queue manager", print_fn)
    display_upload_queue(channel_id, print_fn=print_fn)

    candidates = list_requeue_candidates(channel_id)
    subsection("Re-queue (deleted on YouTube before publish)", print_fn)
    if not candidates:
        print_fn("  No runs with a prior upload/schedule found.")
        print_fn("  For never-uploaded MP4s: py -m scripts.requeue_upload --channel", channel_id)
        return

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


def prompt_upload_plan(
    *,
    channel_id: str | None = None,
    topic: str = "",
    print_fn=print,
    input_fn=input,
) -> UploadPlan:
    """Interactive upload timing and privacy (no CLI flags)."""
    from analytics.post_timing import format_scheduled_local, next_optimal_post_time

    profile = get_channel_profile(channel_id)
    default_priv = profile.privacy_status_default or "private"

    display_upload_queue(channel_id, print_fn=print_fn)

    optimal_at = next_optimal_post_time(channel_id or "default", topic)
    optimal_label = format_scheduled_local(optimal_at, channel_id or "default")

    subsection("Upload", print_fn)
    print_fn("  1) Skip — do not upload")
    print_fn("  2) Queue now — worker uploads when you run: py -m jobs.worker")
    print_fn("  3) Queue later — enter minutes from now")
    print_fn(f"  4) Schedule on YouTube for {optimal_label} — next open slot (topic-aware)")
    print_fn("  5) Re-queue deleted video — open queue manager (same as startup option 2)")
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
    priv = input_fn(f"  Select 1-3 [{default_key}]: ").strip() or default_key
    privacy_status = privacy_map.get(priv, default_priv)

    now = datetime.now(timezone.utc)
    if timing == "2":
        return UploadPlan(mode="queue", scheduled_at=now, privacy_status=privacy_status)

    if timing == "3":
        raw = input_fn("  Minutes until upload [60]: ").strip() or "60"
        try:
            minutes = max(1, int(raw))
        except ValueError:
            minutes = 60
        scheduled = now + timedelta(minutes=minutes)
        print_fn(f"  Scheduled for: {scheduled.astimezone().strftime('%Y-%m-%d %H:%M %Z')}")
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
    print_fn=print,
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

    from core.cost_meter import format_cost_line

    cost_line = format_cost_line(cost)
    if cost_line:
        print_fn(f"  {cost_line}")

    from apis.apify_client import apify_disabled, apify_status

    if apify_disabled():
        print_fn(f"  ⚠ Apify disabled this session — {apify_status()}")
