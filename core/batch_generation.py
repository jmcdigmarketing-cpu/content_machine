"""Batch generation — N ideas → N draft scripts in one unattended pass.

Roadmap "Efficiency & integrations": feeds A/B and volume-with-variation
without babysitting the interactive flow. Strictly headless (no input()) and
render-free: each topic runs discovery → best variant → recommended length →
script/title/description, then saves a review-ready draft folder under
output/<channel>/drafts/<timestamp>-<slug>/ with the same quality checks the
interactive flow shows (hook score, authenticity verdict, grounding flags).

Nothing is rendered or published — drafts are cheap (LLM + signals only), so
an unattended batch can't burn TTS credits or trip the cadence guardrail.

    py -m core.batch_generation --channel tapin --count 3
    py -m core.batch_generation --channel moneywise "Fed rate cut" "CPI print"
    py -m core.batch_generation --file ideas.txt        # one topic per line
    py -m scripts.ops batch-drafts --channel tapin --count 3

Topic sources, in priority order: explicit CLI topics → --file lines →
best-bet recommendations for the channel.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.batch_generation")


@dataclass
class DraftOutcome:
    topic: str
    ok: bool = False
    title: str = ""
    variant: str = ""
    score: float = 0.0
    hook_score: int | None = None
    hook_verdict: str = ""
    authenticity_verdict: str = ""
    authenticity_failed: list[str] = field(default_factory=list)  # #1213
    experiment_arm: str = ""
    ungrounded: list[str] = field(default_factory=list)
    unsupported_claims: int = 0
    fact_conflicts: int = 0
    run_id: int | None = None
    path: str = ""
    error: str = ""
    seconds: float = 0.0
    reused: bool = False  # #760 - an unreviewed draft for this topic already existed
    # #1159: what `ops script-check --idea` prints - the script and its finished-script check.
    script: str = ""
    script_clean: dict | None = None


@contextmanager
def hook_arm_env(arm: tuple[str, str, str] | None) -> Iterator[None]:
    """#1502: the "off" arm turns the hook rewrite off for this one draft (HOOK_REGEN_ENABLED,
    read by `hook_score.hook_regen_enabled`), and puts the setting back after."""
    if not arm or arm[1] != "off":
        yield
        return
    before = os.environ.get("HOOK_REGEN_ENABLED")
    os.environ["HOOK_REGEN_ENABLED"] = "false"
    try:
        yield
    finally:
        if before is None:
            os.environ.pop("HOOK_REGEN_ENABLED", None)
        else:
            os.environ["HOOK_REGEN_ENABLED"] = before


def hook_options(script: str, passes: Any, *, limit: int = 3) -> list[str]:
    """#1503: the script's first sentence, then up to two openers the hook rewrite wrote that
    failed only on "no better than the current opener" (or were kept) - [] without any."""
    import ast

    from core.hook_score import extract_hook

    current = extract_hook(script or "")
    rows: list[Any] = []
    for entry in passes if isinstance(passes, list) else []:
        if isinstance(entry, dict) and entry.get("name") == "improve_hook":
            raw = entry.get("variants")
            if isinstance(raw, str):
                try:
                    raw = ast.literal_eval(raw)
                except (ValueError, SyntaxError):
                    raw = []
            rows.extend(raw if isinstance(raw, list) else [])
    options = [current] if current else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        refused = str(row.get("refused") or "")
        opener = str(row.get("opener") or "").strip()
        if opener and opener not in options and (not refused or refused.startswith("no better")):
            options.append(opener)
        if len(options) >= limit:
            break
    return options if len(options) > 1 else []


def _slug(topic: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "draft"


def _drafts_dir(channel_id: str) -> str:
    from core.output_paths import channel_output_root

    path = os.path.join(channel_output_root(channel_id), "drafts")
    os.makedirs(path, exist_ok=True)
    return path


_REUSE_DAYS = 3


def unreviewed_draft(channel_id: str, topic: str, *, max_age_days: float = _REUSE_DAYS):
    """(folder, meta) of a recent draft for this topic nobody has reviewed, else None.

    A second batch the same week used to pay for discovery and the script again for a
    topic already waiting in `ops batch-review` (#760).
    """
    key = " ".join((topic or "").lower().split())
    try:
        root = _drafts_dir(channel_id)
        names = sorted(os.listdir(root), reverse=True)
    except OSError:
        return None
    for name in names:
        folder = os.path.join(root, name)
        try:
            with open(os.path.join(folder, "meta.json"), encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(meta, dict) or meta.get("review"):
            continue
        if " ".join(str(meta.get("topic") or "").lower().split()) != key:
            continue
        try:
            age = datetime.now() - datetime.fromisoformat(str(meta.get("created_at")))
        except (TypeError, ValueError):
            continue
        if age.total_seconds() <= max_age_days * 86400:
            return folder, meta
    return None


def collect_topics(
    channel_id: str,
    topics: list[str] | None = None,
    file: str | None = None,
    count: int = 3,
    *,
    picks: dict[str, dict] | None = None,
    held_back: list[str] | None = None,
    notes: list[str] | None = None,
    wide: int = 0,
    gate: dict[str, int] | None = None,
    news_only: bool = False,
) -> list[str]:
    """Explicit topics → file lines → best bets, capped at `count` for implicit sources.

    ``picks`` (optional) is filled with each best-bet topic's `pick_record` (#913) so the
    run records that the batch took it and at which rank; explicit and file topics are
    not picks. ``held_back`` (optional) gets the headlines the topic gate kept for the menu
    (#1595). The day's countdown (#1847) and dated moments and long videos (decision 84) come
    on top of `count` - even at 0; ``notes`` gets why a dated entry due today was skipped.
    #1653 (wave 152): ``wide`` drafts instead of `count` when that many pass the topic gate;
    ``gate`` (optional) gets how many passed. #1666 (wave 156): ``news_only`` - the 1 PM step -
    takes the gated ideas and the preview alone: no series, dated extras or follow-up (overnight
    makes those).
    """
    if topics:
        return [t.strip() for t in topics if t.strip()]
    if file:
        with open(file, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
        return lines
    try:
        from core.best_bet import get_idea_menu, marquee_names, pick_record
        from core.success.formats import rotated_out, without_rotated

        rotated = rotated_out(channel_id)  # #1692 (wave 159): a format below the median rests
        if count <= 0:
            # #1847, decision 84: drafts are waiting, so nothing else is - but a countdown or a
            # dated moment is made on its day or not at all. No menu: it fetches feeds and
            # makes the previews' calls.
            from core.series.countdown import countdown_idea
            from core.series.dated import dated_ideas
            from core.series.last_night import last_night_ideas
            from core.series.recap import debate_ideas, matchup_ideas, recap_ideas

            alone = _unique([countdown_idea(channel_id), countdown_idea(channel_id, ahead=1),
                             *dated_ideas(channel_id, notes=notes),
                             *long_breakout_ideas(channel_id),
                             *recap_ideas(channel_id, notes=notes),
                             *matchup_ideas(channel_id, notes=notes),  # #1892
                             *debate_ideas(channel_id),  # #1673
                             *last_night_ideas(channel_id)])  # #1999, #1877  # fmt: skip
            alone = without_rotated(alone, rotated)
            if picks is not None:
                for bet in alone:
                    picks[bet.topic] = pick_record([bet], 1, by="batch")
            return [b.topic for b in alone]
        ideas, previews = get_idea_menu(channel_id, notes=notes, prefer_ahead=True)  # #1670
        ideas = without_rotated(ideas, rotated)  # #1692
        extra: list[Any] = []
        if not news_only:  # #1666: the 1 PM step leaves the series and dated extras to overnight
            extra = [b for b in ideas if getattr(b, "source", "") in DATED_SOURCES]
            # Wave 135 (the operator: "a day ahead"): tomorrow's countdown too, scheduled for its
            # own noon - days 21 and 20 were lost to a PC that was off at 5 AM.
            from core.series.countdown import countdown_idea
            from core.series.explainers import explainer_ideas
            from core.series.last_night import last_night_ideas
            from core.series.parts import part_two_ideas
            from core.series.profiles import profile_ideas
            from core.series.recap import debate_ideas, matchup_ideas, recap_ideas
            from core.series.shapes import patch_ideas

            extra = _unique([*extra, countdown_idea(channel_id, ahead=1),
                             *long_breakout_ideas(channel_id),  # #1740
                             *recap_ideas(channel_id, notes=notes),  # #1722
                             *matchup_ideas(channel_id, notes=notes),  # #1892
                             *debate_ideas(channel_id),  # #1673
                             *last_night_ideas(channel_id),  # #1999, #1877
                             *profile_ideas(channel_id),  # #1686
                             *patch_ideas(channel_id),  # #1688
                             *part_two_ideas(channel_id),  # #1700
                             *explainer_ideas(channel_id)])  # #1680  # fmt: skip
            extra = without_rotated(extra, rotated)  # #1692
        names = marquee_names(channel_id)
        from core.best_bet import crossover_names

        gate_names = [*names, *crossover_names(channel_id)]  # #1620: a crossover travels too
        kept: list[Any] = []
        moment = datetime.now(timezone.utc)
        known = known_subject_check()  # #1605
        for bet in ideas:
            if getattr(bet, "source", "") in DATED_SOURCES:
                continue
            told = self_story(bet.topic) if self_story_hold() else ""
            if told:  # #2026: it stays in the menu - the operator's to tell, never overnight's
                if notes is not None:
                    notes.append(f'A story about machine-made content ("{told}") was left for '
                                 f"you in the menu: {bet.topic[:90]} (#2026)")  # fmt: skip
                continue
            if stale_idea(bet, moment):  # #1607: past 36 hours on under three outlets
                if held_back is not None:
                    held_back.append(bet.topic)
                continue
            outlets = int(getattr(bet, "outlets", 0) or 0)
            if story_passes_gate(bet.topic, source=str(getattr(bet, "source", "") or ""),
                                 outlets=outlets, names=gate_names, known=known):  # #1620, #1605  # fmt: skip
                kept.append(bet)
            elif held_back is not None:
                held_back.append(bet.topic)
        kept = lead_first(kept, channel_id)  # #1867, #1613, #1612, #1599
        from core.series.dated import channel_day, launch_names

        kept = one_per_subject(kept, names, exempt=launch_names(channel_id, channel_day(channel_id)),
                               held_back=held_back)  # #1606  # fmt: skip
        if gate is not None:
            gate["passed"] = len(kept)
        if wide > count and len(kept) >= wide:  # #1653: five drafts when five pass the gate
            count = wide
        # #1593 (decision 81): at most one preview a night, marquee only - #1670: a game 24-48
        # hours away first, a day ahead of it.
        from core.best_bet import ahead_first

        marquee = ahead_first(
            [p for p in previews if preview_qualifies(str(getattr(p, "kind", "") or ""))]
        )
        # Decision 66: an idea, then the preview, then the other ideas.
        candidates: list[Any] = [*kept[:1], *marquee[:1], *kept[1:]]
        chosen = candidates[:count]
        night_gaming_share(channel_id, chosen, candidates, extra)  # #1968 (S15)
        held = _swap_holdouts(chosen, candidates)
        if picks is not None:
            for rank, bet in enumerate(chosen, 1):
                if bet.topic in held:  # #83: recorded at its rank in the top ten it came from
                    record = pick_record(candidates, candidates.index(bet) + 1, by="batch")
                    record["holdout"] = True
                else:
                    record = pick_record(chosen, rank, by="batch")
                picks[bet.topic] = record
            for bet in extra:
                picks[bet.topic] = pick_record([bet], 1, by="batch")
            if not news_only and "part 1" not in rotated:  # #1700: the lead story, told in two
                from core.series.parts import part_one

                first = part_one(chosen, names, channel_id)
                if first and first in picks:
                    picks[first]["part"] = 1
        if news_only:
            return [b.topic for b in chosen]
        out = _with_follow_up(channel_id, [b.topic for b in chosen], held, picks)
        return [*(b.topic for b in extra), *out]
    except Exception as exc:
        logger.warning("No topics given and best bets unavailable: %s", exc)
        return []


# decision 84: extra drafts on their day; #1724 a season's explainer when its season is named
DATED_SOURCES = ("countdown", "moment", "long", "season")


STALE_HOURS = 36.0  # #1607
STALE_OUTLETS = 3


def stale_idea(bet: Any, now: datetime) -> bool:
    """#1607 (B01.11): a headline whose story broke more than `STALE_HOURS` ago and that fewer
    than `STALE_OUTLETS` outlets still carry - it is not tonight's news. Unknown age: not stale."""
    if getattr(bet, "source", "") != "trending":
        return False
    try:
        broke = datetime.fromisoformat(str(getattr(bet, "first", "") or ""))
    except ValueError:
        return False
    broke = broke if broke.tzinfo else broke.replace(tzinfo=timezone.utc)
    old = now - broke > timedelta(hours=STALE_HOURS)
    return old and int(getattr(bet, "outlets", 0) or 0) < STALE_OUTLETS


def one_per_subject(
    ideas: list[Any],
    names: list[str],
    *,
    exempt: list[str] | None = None,
    held_back: list[str] | None = None,
) -> list[Any]:
    """#1606 (B01.10): one idea a marquee subject a night - the second waits for tomorrow (it
    stays in the menu). A subject with an active launch-week `slots` row (#1868) keeps two."""
    from apis.topic_tokens import names_any

    free = list(exempt or [])
    seen: list[str] = []
    out: list[Any] = []
    for bet in ideas:
        topic = str(getattr(bet, "topic", "") or "")
        named = [n for n in names or [] if names_any(topic, [n])]
        clash = [n for n in named if any(names_any(n, [s]) or names_any(s, [n]) for s in seen)]
        if clash and not any(names_any(n, free) or names_any(f, [n]) for n in clash for f in free):
            if held_back is not None:
                held_back.append(topic)
            continue
        seen.extend(named)
        out.append(bet)
    return out


def lead_first(
    ideas: list[Any],
    channel_id: str,
    *,
    now: datetime | None = None,
    week: list[str] | None = None,
) -> list[Any]:
    """Wave 152: what leads the night, highest first - a launch-week story on five outlets
    (#1867), an injury to a marquee name (#1613), a story naming a numbered card or its main
    event in its fight week (#1612, `week` - read from ESPN's calendar when None), a marquee
    name's competitor breakout at `OUTLIER_FIRST`x (#1599). Each moves its first idea to the
    front, the lowest first, so the highest leads. The rest keep their order."""
    from apis.topic_tokens import names_any
    from core.best_bet import (
        OUTLIER_FIRST,
        crossover_names,
        crossover_story,
        injury_story,
        marquee_names,
        trade_story,
    )
    from core.series.dated import channel_day, jump_first, launch_names

    names = marquee_names(channel_id)
    crossovers = crossover_names(channel_id)
    if week is None:
        from core.series.recap import fight_week

        week = fight_week(now=now)

    def front(items: list[Any], test: Callable[[str, Any], bool]) -> list[Any]:
        for i, bet in enumerate(items):
            if test(str(getattr(bet, "topic", "") or ""), bet):
                return [bet, *items[:i], *items[i + 1 :]]
        return items

    # #1620 (wave 155): a celebrity crossover leads the plain headlines - the lowest lead
    out = front(list(ideas), lambda topic, bet: getattr(bet, "source", "") == "trending"
                and crossover_story(topic, str(getattr(bet, "domain", "") or ""), crossovers))  # fmt: skip
    out = front(out, lambda topic, bet: (
        float(getattr(bet, "outlier", 0) or 0) >= OUTLIER_FIRST and names_any(topic, names)))  # fmt: skip
    if week:
        out = front(out, lambda topic, _bet: names_any(topic, week))
    out = front(out, lambda topic, _bet: trade_story(topic, names))  # #1614 (wave 159)
    out = front(out, lambda topic, _bet: injury_story(topic, names))
    return jump_first(out, launch_names(channel_id, channel_day(channel_id, now)))


def night_gaming_share(
    channel_id: str, chosen: list[Any], candidates: list[Any], extra: list[Any]
) -> int:
    """#1968 (S15, decision 98): while gaming leads the organic views, the night's drafts - its
    dated ones included - carry the menu's gaming share (`GAMING_FLOOR` of five). On 11-02 every
    night offered one series, one preview and one headline, so gaming was one in three while it
    earned 67% of the views; the menu's floor never reached the night. A plain headline gives
    way to the next gaming idea in line - never the series or the preview. Returns the swaps."""
    try:
        from core.best_bet import GAMING_FLOOR, _gaming_leads

        total = len(chosen) + len(extra)
        if not chosen or not _gaming_leads(channel_id):
            return 0
        need = -(-total * GAMING_FLOOR // 5)  # ceil: 3 of 5, 2 of 3
        have = sum(1 for b in [*chosen, *extra] if getattr(b, "domain", "") == "gaming")
        spare = [b for b in candidates[len(chosen) :] if getattr(b, "domain", "") == "gaming"]
        swaps = 0
        while have < need and spare:
            plain = [i for i, b in enumerate(chosen)
                     if getattr(b, "domain", "") != "gaming"
                     and getattr(b, "source", "") not in ("series", "schedule")]  # fmt: skip
            if not plain:
                break
            chosen[plain[-1]] = spare.pop(0)
            have += 1
            swaps += 1
        return swaps
    except Exception as exc:
        logger.debug("night gaming share skipped: %s", exc)
        return 0


def _unique(bets: list[Any]) -> list[Any]:
    """The ideas that are not None, each topic once, in order."""
    seen: set[str] = set()
    out: list[Any] = []
    for bet in bets:
        if bet is not None and bet.topic not in seen:
            seen.add(bet.topic)
            out.append(bet)
    return out


OUTLETS_MIN = 3  # #1595 (decision 81): an overnight story is on three outlets, or a marquee name
_PREVIEW_KINDS = ("national", "league", "ufc_numbered")


def story_passes_gate(
    topic: str,
    *,
    source: str,
    outlets: int,
    names: list[str],
    known: Callable[[str], bool] | None = None,
) -> bool:
    """#1595: a headline (`trending`) fills an overnight slot on `OUTLETS_MIN` outlets or when it
    names a marquee name. Series, replays, the follow-up and the calendar are not headlines.
    #1966 (decision 97): a death story fills no slot, whatever its source. #1605 (wave 156):
    ``known`` says whether the headline names a subject a casual fan knows - it passes too."""
    from core.authenticity import is_death_story

    if is_death_story(topic or ""):
        return False
    if source != "trending":
        return True
    from apis.topic_tokens import names_any

    if outlets >= OUTLETS_MIN or names_any(topic or "", names):
        return True
    return bool(known is not None and known(topic or ""))


# #2026 (decision 113): a story about machine-made or low-effort content. On 11-11 a viewer wrote
# under "Steam Review Queue Congestion": "You are part of the problem. Do not reccomend channel"
# (2 likes) - a machine-voiced channel reporting on machine-made games. Specific phrases only:
# "AI teammates" or "the enemy AI" is a game's own AI and is a story like any other.
_SELF_STORY_RE = re.compile(
    r"\b(?:ai|a\.i\.)[- ]?(?:generated|made|written|voiced|slop|spam|art|content|shovelware|"
    r"crackdown|disclosures?|voices?|videos?|channels?|games)\b"
    r"|\bgenerative ai\b|\bgen[- ]?ai\b|\bslop\b|\bshovelware\b|\basset[- ]flips?\b"
    r"|\blow[- ]effort (?:games?|content|releases?|uploads?|videos?|channels?)\b"
    r"|\b(?:content|video) farms?\b|\bfaceless channels?\b"
    r"|\bmachine[- ](?:made|generated|written)\b",
    re.IGNORECASE,
)


def self_story_hold() -> bool:
    """`SELF_STORY_HOLD=false` lets these stories through like any other."""
    return os.getenv("SELF_STORY_HOLD", "true").strip().lower() not in ("0", "false", "no", "off")


def self_story(text: str) -> str:
    """#2026: the phrase that makes `text` a story about machine-made content, else ""."""
    found = _SELF_STORY_RE.search(text or "")
    return found.group(0) if found else ""


def known_subject_check() -> Callable[[str], bool] | None:
    """#1605: the gate's casual-fan check - Wikipedia's 30-day pageviews over the floor - or None
    when `KNOWN_SUBJECTS` is off (the suite pins it). Each pass is logged ("Derrick Henry:
    134,234 Wikipedia views in 30 days"). Never raises."""
    if os.getenv("KNOWN_SUBJECTS", "true").strip().lower() in ("0", "false", "no", "off"):
        return None

    def check(topic: str) -> bool:
        try:
            from apis import wikipedia_pageviews_api as wiki

            name, views = wiki.known_subject(topic)
        except Exception as exc:
            logger.debug("known subject check skipped: %s", exc)
            return False
        if name:
            logger.info("topic gate: %s has %s Wikipedia views in 30 days - a subject fans know "
                        "(#1605): %s", name, f"{views:,}", topic[:80])  # fmt: skip
        return bool(name)

    return check


def preview_qualifies(kind: str) -> bool:
    """#1593: a national broadcast, a league's own marquee note or a numbered UFC card. A team
    the channel covered, a Fight Night, an award and the other games stay in the menu."""
    return kind in _PREVIEW_KINDS


def topic_gate_line(held: list[str]) -> str:
    """The overnight report's line for the stories the gate held back (#1595), or ""."""
    if not held:
        return ""
    noun = "story" if len(held) == 1 else "stories"
    shown = "; ".join(t[:60] for t in held[:2]) + ("; ..." if len(held) > 2 else "")
    return (
        f"The topic gate held back {len(held)} {noun} on fewer than {OUTLETS_MIN} outlets "
        f"(in the menu): {shown} (#1595)"
    )


FOLLOW_UP_DAYS = 14  # a follow-up on old news is not one


def follow_up_topic(channel_id: str, *, now: datetime | None = None) -> str:
    """#1452 (wave 117, the operator: in one of its draft slots): a follow-up on a recent video
    that brought 2+ subscribers, "" when there is none or it was drafted already. On 10-20 the
    morning named run 162 (the Pistons bench, 2 subscribers) and nothing drafted one."""
    try:
        from analytics.growth import _rows, subscriber_flags
        from storage.repositories.content_runs import get_content_run_repository

        moment = now or datetime.now(timezone.utc)
        for row in subscriber_flags(_rows(channel_id)):
            published = row.get("published")
            if not published or (moment - published).days > FOLLOW_UP_DAYS:
                continue
            run = (
                get_content_run_repository().get(int(row["run_id"])) if row.get("run_id") else None
            )
            title = str(getattr(run, "title", "") or row.get("title") or "").strip()
            if not title or _followed_up(channel_id, title):  # once per video, in any wording
                continue
            # #1536 (wave 118 drafted it, wave 119): the original's date - "what has happened
            # since" drew last season's "clinched the No. 1 seed" into run 179.
            day = f"{published:%b} {published.day}"
            return f'Follow-up to "{title}" ({day}): what has happened since {day}'
        for title, published in breakouts(channel_id, now=moment):  # #1601
            if not _followed_up(channel_id, title):
                day = f"{published:%b} {published.day}"
                return f'Follow-up to "{title}" ({day}): what has happened since {day}'
    except Exception as exc:
        logger.debug("follow-up topic skipped: %s", exc)
    return ""


BREAKOUT_VIEWS = 300  # #1601 (B01.5): organic views in a video's first day
BREAKOUT_HOURS = 48


def breakouts(channel_id: str, *, now: datetime | None = None) -> list[tuple[str, datetime]]:
    """#1601 (wave 145): (title, published) for each video whose first day brought
    `BREAKOUT_VIEWS` organic views, judged in the last `BREAKOUT_HOURS` - most views first.
    #1452 drafted a follow-up only for two subscribers; a breakout compounds while it is
    fresh. The first-day verdict (#49, `metrics["first_day"]`) holds the 24-hour views."""
    from analytics.first_day import _metrics
    from storage.repositories.publish_log import get_publish_log_repository, video_title

    moment = now or datetime.now(timezone.utc)
    found: list[tuple[int, str, datetime]] = []
    for row in get_publish_log_repository().list_uploaded_for_channel(channel_id) or []:
        verdict = _metrics(row).get("first_day")
        if not isinstance(verdict, dict) or int(verdict.get("views") or 0) < BREAKOUT_VIEWS:
            continue
        try:
            judged = datetime.fromisoformat(str(verdict.get("judged_at") or ""))
        except ValueError:
            continue
        judged = judged if judged.tzinfo else judged.replace(tzinfo=timezone.utc)
        if moment - judged > timedelta(hours=BREAKOUT_HOURS):
            continue
        title = video_title(row, fallback="").strip()
        published = getattr(row, "published_at", None) or judged - timedelta(days=1)
        if isinstance(published, datetime) and published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        if title:
            found.append((int(verdict.get("views") or 0), title, published))
    return [(title, when) for _views, title, when in sorted(found, key=lambda f: -f[0])]


LONG_BREAKOUT_VIEWS = 1000  # #1740 (B06.19): organic views
LONG_BREAKOUT_DAYS = 5


def long_breakouts(channel_id: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """#1740 (B06.19, wave 146): each Short published in the last `LONG_BREAKOUT_DAYS` days with
    `LONG_BREAKOUT_VIEWS` organic views (#1977: a promoted Short's ads are not interest) -
    {title, published, views, names, domain}, most views first. Not a compilation or long video."""
    from analytics.youtube_metrics import organic_lifetime
    from core.ypp_readiness import _organic_views
    from storage.repositories.content_runs import get_content_run_repository
    from storage.repositories.publish_log import get_publish_log_repository, is_seeded, video_title

    moment = now or datetime.now(timezone.utc)
    runs = get_content_run_repository()
    found: list[dict[str, Any]] = []
    for row in get_publish_log_repository().list_uploaded_for_channel(channel_id) or []:
        published = getattr(row, "published_at", None)
        if not isinstance(published, datetime) or is_seeded(row) or not row.content_run_id:
            continue
        published = published if published.tzinfo else published.replace(tzinfo=timezone.utc)
        if not timedelta(0) <= moment - published <= timedelta(days=LONG_BREAKOUT_DAYS):
            continue
        try:
            metrics = json.loads(getattr(row, "metrics_json", None) or "{}") or {}
        except (TypeError, ValueError):
            continue
        known = organic_lifetime(metrics)
        views = known if known is not None else int(_organic_views(metrics))
        if views < LONG_BREAKOUT_VIEWS:
            continue
        run = runs.get(int(row.content_run_id))
        try:
            features = json.loads(getattr(run, "features_json", "") or "{}") or {}
        except (TypeError, ValueError):
            features = {}
        if features.get("compilation") or features.get("long_form"):
            continue
        title = video_title(row, fallback="").strip()
        if title:
            found.append({"title": title, "published": published, "views": views,
                          "names": list((features.get("entity_research") or {}).get("names") or []),
                          "domain": str(getattr(run, "domain", "") or "gaming")})  # fmt: skip
    return sorted(found, key=lambda f: -int(f["views"]))


def long_breakout_ideas(
    channel_id: str,
    *,
    now: datetime | None = None,
    headlines: Callable[[str, dict[str, Any], datetime], list[dict[str, Any]]] | None = None,
) -> list[Any]:
    """#1740: one long video a night (source "long", after your review - decision 84) on the
    biggest `long_breakouts` Short not drafted yet, written from the week's headlines naming its
    subject. A Short past 1,000 views is a topic people look for; never raises."""
    try:
        from core.best_bet import BestBetResult
        from core.series.countdown import feed_headlines, headline_facts

        moment = now or datetime.now(timezone.utc)
        for item in long_breakouts(channel_id, now=moment):
            topic = f'The full story behind "{item["title"]}"'
            if series_drafted(channel_id, topic):
                continue
            names = [str(n) for n in item["names"] if str(n).strip()]
            facts: list[str] = []
            if names:
                lines = (headlines or feed_headlines)(
                    channel_id, {"domain": item["domain"]}, moment
                )
                facts = headline_facts(names, lines, now=moment, hours=24 * 7, limit=12)
            days = max(1, (moment - item["published"]).days)
            return [BestBetResult(
                topic=topic, domain=item["domain"], avg_engaged_rate=0.0, source="long",
                supporting_runs=0, facts=facts, draft_kind="long",
                rationale=f"breakout · {item['views']:,} organic views in {days} day(s) - a long "
                "video, after your review",
            )]  # fmt: skip
    except Exception as exc:
        logger.debug("long breakout idea skipped: %s", exc)
    return []


def _followed_up(channel_id: str, title: str) -> bool:
    """A follow-up on this title was drafted already - wave 118's words or wave 119's."""
    from core.channel_context import recent_input_topics

    prefix = f'follow-up to "{title}"'.lower()
    if any(
        str(t).strip().lower().startswith(prefix) for t in recent_input_topics(channel_id, limit=60)
    ):
        return True
    return unreviewed_draft(channel_id, f'Follow-up to "{title}"') is not None


def _with_follow_up(
    channel_id: str, topics: list[str], held: set[str], picks: dict[str, dict] | None
) -> list[str]:
    """The night's last slot that is not a holdout goes to the follow-up; its pick record is
    dropped - a follow-up is not a best bet. Two slots or more only."""
    if len(topics) < 2:
        return topics
    follow = follow_up_topic(channel_id)
    slots = [i for i, topic in enumerate(topics) if topic not in held]
    if not follow or not slots or follow in topics:
        return topics
    i = slots[-1]
    if picks is not None:
        picks.pop(topics[i], None)
    logger.info("overnight: %s takes the slot of %s", follow, topics[i])
    return [*topics[:i], follow, *topics[i + 1 :]]


def _swap_holdouts(chosen: list, candidates: list) -> set[str]:
    """#83: the night's holdout slots each take another of the top ten; their topics."""
    try:
        from core.predictions.holdouts import holdout_choice, next_slots

        slots = next_slots(len(chosen))
    except Exception as exc:
        logger.debug("holdouts skipped: %s", exc)
        return set()
    held: set[str] = set()
    day = datetime.now().strftime("%Y-%m-%d")
    for index, is_holdout in enumerate(slots):
        if not is_holdout:
            continue
        other = holdout_choice(candidates, {b.topic for b in chosen}, seed=f"{day}:{index}")
        if other is not None:
            chosen[index] = other
            held.add(other.topic)
    return held


def pick_facts(best_bet: dict | None) -> list[str]:
    """The lines a series pick is written from (#991), or []."""
    return [str(f) for f in ((best_bet or {}).get("facts") or []) if str(f).strip()]


def series_drafted(channel_id: str, topic: str, *, redo_set_aside: bool = False) -> bool:
    """This week's series topic is already a draft or a run (#991): it is made once a week.

    #1964 (wave 145): with ``redo_set_aside`` (a countdown day), a run whose draft was rejected
    or whose render was retired does not count. Run 226, the Nov 3 countdown, was rejected at
    review and no night would have drafted the day again."""
    try:
        key = " ".join(topic.lower().split())
        if redo_set_aside:
            from storage.repositories.content_runs import get_content_run_repository

            aside = set_aside_runs(channel_id, key)
            runs = get_content_run_repository().list_for_channel(channel_id)[:60]
            for run in runs:
                seed = " ".join(str(run.input_topic or run.selected_topic or "").lower().split())
                if seed == key and int(run.id) not in aside and not _retired(run):
                    return True
            return unreviewed_draft(channel_id, topic) is not None
        from core.channel_context import recent_input_topics

        if any(str(t).strip().lower() == key for t in recent_input_topics(channel_id, limit=60)):
            return True
        return unreviewed_draft(channel_id, topic) is not None
    except Exception as exc:
        logger.debug("series lookup skipped: %s", exc)
        return False


def set_aside_runs(channel_id: str, key: str) -> set[int]:
    """#1964: the runs whose draft for this topic (normalised) was rejected at review."""
    out: set[int] = set()
    try:
        root = _drafts_dir(channel_id)
        names = os.listdir(root)
    except OSError:
        return out
    for name in names:
        try:
            with open(os.path.join(root, name, "meta.json"), encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(meta, dict):
            continue
        review = meta.get("review")
        if not isinstance(review, dict) or review.get("decision") != "rejected":
            continue
        if " ".join(str(meta.get("topic") or "").lower().split()) == key:
            try:
                out.add(int(str(meta.get("run_id"))))
            except (TypeError, ValueError):
                continue
    return out


def _retired(run: Any) -> bool:
    """#1964: a render retired as wrong (`stale_renders`, wave 140) - its day may be made again."""
    try:
        features = json.loads(getattr(run, "features_json", None) or "{}")
    except (TypeError, ValueError):
        return False
    return isinstance(features, dict) and bool(features.get("retired_at"))


# #1637 (B02.16, wave 157): length by format as an experiment. Measured 11-06 over 60 days: news
# Shorts ran a median 72 s, previews 70 s - twice the 30-45 s and 45-60 s the bridge names. A news
# or preview draft between these dates takes the less-used arm: "format" writes news at the Short
# preset (100-150 words, 30-45 s) and a preview at 150-200 words (45-60 s); "learned" keeps the
# recommender's length. `LENGTH_TRIAL=false` stops it; the weekly report reads it on stayed share
# and first-week views (`length_trial_lines`).
LENGTH_LEVER = "length_by_format"
LENGTH_TRIAL = ("2026-11-07", "2026-11-21")
LENGTH_ARMS = ("format", "learned")


def format_length(intent: str) -> tuple[str, tuple[int, int] | None] | None:
    """(length choice, word range) the "format" arm gives a news draft or a preview, else None."""
    from core.angle_intent import ANGLE_NEWS, ANGLE_PREVIEW

    if intent == ANGLE_NEWS:
        return "1", None
    if intent == ANGLE_PREVIEW:
        return "2", (150, 200)
    return None


def length_trial_arm(
    channel_id: str, intent: str, *, today: date | None = None
) -> tuple[str, str, tuple[int, int] | None] | None:
    """(arm, length choice, word range) for a news or preview draft inside `LENGTH_TRIAL`, the arm
    with fewer drafts first - None outside it, for another draft, or with `LENGTH_TRIAL` off."""
    if os.getenv("LENGTH_TRIAL", "true").strip().lower() in ("0", "false", "no", "off"):
        return None
    day = (today or date.today()).isoformat()
    shape = format_length(intent)
    if shape is None or not LENGTH_TRIAL[0] <= day <= LENGTH_TRIAL[1]:
        return None
    try:
        from core.experiments import _assignments

        rows = _assignments(channel_id, LENGTH_LEVER)
    except Exception as exc:
        logger.debug("length arms unread: %s", exc)
        rows = []
    counts = {arm: sum(1 for r in rows if r.get("arm") == arm) for arm in LENGTH_ARMS}
    arm = min(LENGTH_ARMS, key=lambda a: counts[a])
    return arm, shape[0], shape[1]


def _record_draft_features(
    run_id: int | None, shape: str, channel_id: str, *, beat: bool = True
) -> None:
    """Wave 157: the run's shape (#1676, #1674, #1688) and - for a Short (`beat`) - the re-hook
    beat second its prompt was given (#1645), for the weekly readouts. Never raises."""
    if not run_id:
        return
    updates: dict[str, Any] = {}
    if shape:
        updates["shape"] = shape
    try:
        from core.retention import rehook_beat_second

        second = rehook_beat_second(channel_id) if beat else None
        if second is not None:
            updates["rehook_beat_s"] = second
    except Exception as exc:
        logger.debug("re-hook beat unread: %s", exc)
    if not updates:
        return
    try:
        from core.run_features import merge_features

        merge_features(run_id, updates)
    except Exception as exc:
        logger.debug("draft features not recorded for run %s: %s", run_id, exc)


def profile_length(topic: str, best_bet: dict | None) -> str:
    """#1686: "1" (the Short preset, 30-45 s) for a "Who is ...?" pick, else ""."""
    return "1" if pick_source(topic, best_bet) == "profile" else ""


def _length_choice(channel_id: str, topic: str) -> str:
    try:
        from core.length_recommender import get_recommended_length

        return get_recommended_length(channel_id, topic).length_choice
    except Exception:
        return "2"


def authenticity_fields(report: Any) -> dict[str, Any]:
    """#1213: the verdict and the checks that failed it, for the draft record."""
    return {
        "authenticity_verdict": str(report.verdict),
        "authenticity_failed": [
            c.name for c in (getattr(report, "checks", None) or []) if not c.passed
        ],
    }


def generate_draft(
    topic: str,
    channel_id: str,
    *,
    key_facts: list[str] | None = None,
    best_bet: dict | None = None,
    own_idea: bool = False,
) -> DraftOutcome:
    """One headless draft: discovery → best variant → script → saved folder.

    ``key_facts`` (optional) are shared operator ground truth applied to this
    topic — same ``run_pipeline(key_facts=)`` path as ``auto_generate --facts-file``.
    ``best_bet`` is the topic's `pick_record` when the batch took it from the best bets.

    ``own_idea`` (#1159): `topic` is an idea the operator typed. It is written the way angle
    1 writes it in `main.py` - `idea_angle`'s wording, index -1, the idea as the brief, no
    generated angle and no experiment directive. `ops script-check --idea` had passed index
    0, the first generated angle: runs 140-142 were reported as the operator's ideas and were
    written from angles a model made up.
    """
    from core.pipeline import run_discovery, run_pipeline

    out = DraftOutcome(topic=topic)
    started = time.time()

    key_facts = [*pick_facts(best_bet), *(key_facts or [])] or None  # #991: a series pick's
    # #1151 / #1169: a schedule pick knows when its game is; ahead of it, the angles and the
    # script are written as a preview.
    event_at = _game_start(topic, best_bet) or _named_event_start(topic)
    from core.facts.event_dates import PREVIEW_MIN_LEAD_HOURS, game_started, starts_within

    upcoming = bool(event_at) and game_started(event_at) is False
    if upcoming and starts_within(event_at, PREVIEW_MIN_LEAD_HOURS):
        # #1577: run 193 was drafted 31 minutes before its kickoff.
        out.error = (
            f"its game starts in under {PREVIEW_MIN_LEAD_HOURS:.0f} hours - too close to draft, "
            "render and decide (#1577)"
        )
        return out
    # #1301: the brief carries the call the preview was offered with.
    preview = preview_for(topic, best_bet, upcoming=upcoming)

    machine_intent = draft_intent(  # #1588; #1594 a headline is news
        own_idea=own_idea, preview=preview, source=pick_source(topic, best_bet)
    )
    if own_idea:
        discovery = run_discovery(topic, channel_id=channel_id, brief=topic)
    elif preview:
        discovery = run_discovery(
            topic, channel_id=channel_id, brief=preview, intent=machine_intent
        )
    else:
        discovery = run_discovery(topic, channel_id=channel_id, intent=machine_intent)
    experiment: tuple[str, str, str] | None = None
    if own_idea:
        from apis.topic_variants import idea_angle

        variant_index = -1
        best_topic = idea_angle(topic, channel_id) or topic
        best_score, best_signals = 0.0, discovery.base_signals
    else:
        if not discovery.evaluated:
            out.error = "discovery returned no scored variants"
            return out
        # The one ranking rule — this used to `max` on the displayed score alone and
        # so picked arbitrarily whenever the composites tied, which is every run.
        from core.pipeline import best_variant_index

        variant_index = best_variant_index(
            discovery.evaluated, discovery.raw_scores, discovery.angle_scores
        )
        best_topic, best_score, best_signals = discovery.evaluated[variant_index]

        # Active script-lever A/B experiment: the least-used arm's directive
        # shapes this draft (thumbnail levers apply at render, not here).
        try:
            from core.experiments import next_arm

            experiment = next_arm(channel_id, kind="script")
        except Exception as exc:
            logger.debug("next_arm skipped: %s", exc)
    hook_arm: tuple[str, str, str] | None = None
    if not own_idea:
        try:  # #1502: the hook rewrite on or off for this draft
            from core.experiments import next_arm

            hook_arm = next_arm(channel_id, kind="hook")
        except Exception as exc:
            logger.debug("hook arm skipped: %s", exc)
    shape_arm = None if own_idea else preview_shape_arm(channel_id, preview)  # #1366
    out.variant, out.score = best_topic, float(best_score or 0)

    from core.facts.selection import select_headless_facts
    from core.vault.relevance import build_relevance_corpus

    corpus = build_relevance_corpus(best_signals, operator_facts=key_facts or [])
    packed = select_headless_facts(key_facts, topic=topic, corpus=corpus) if key_facts else None
    # #1850 (decision 84): a long video - Extended, chapters from its angles, 16:9 after review
    long_form = (best_bet or {}).get("draft_kind") == "long"
    length_choice = (
        "4"
        if long_form
        else profile_length(topic, best_bet) or _length_choice(channel_id, best_topic)
    )
    long_kwargs: dict[str, Any] = {}
    if long_form:
        from core.series.long_form import long_word_range

        long_kwargs["chapter_angles"] = [str(v) for v, *_ in discovery.evaluated][:5]
        long_kwargs["word_range"] = long_word_range(topic, len(key_facts or []))  # #1732
    # #1637 (wave 157): news at 30-45 s and previews at 45-60 s against the learned length
    length_trial = (
        None if own_idea or long_form or profile_length(topic, best_bet)
        else length_trial_arm(channel_id, machine_intent)
    )  # fmt: skip
    # #1799 (wave 159): a news draft's voice on trial, balanced within its length arm
    voice_arm = None
    if not own_idea and not long_form:
        from core.voice.trial import voice_trial_arm

        voice_arm = voice_trial_arm(channel_id, machine_intent,
                                    length_arm=length_trial[0] if length_trial else "")  # fmt: skip
    # #1719 (wave 160): the follow line's wording on trial - recorded only for a draft whose
    # last line is the trial's (a countdown, a series or a debate has its own reason)
    from core.spaced_queue import long_slot_words
    from core.success.follow_trial import FOLLOW_LEVER, follow_arm, follow_wording

    follow_pick = None if own_idea or long_form or preview else follow_arm(channel_id)
    follow_line = "" if preview else follow_brief(best_bet, channel_id=channel_id, arm=follow_pick)
    if follow_pick and follow_line != follow_wording(follow_pick, long_slot_words()):
        follow_pick = None
    if length_trial is not None and length_trial[0] == "format":
        length_choice = length_trial[1]
        if length_trial[2]:
            long_kwargs["word_range"] = length_trial[2]
    # #1676 / #1674 / #1688 (wave 157): the story's shape - a stat-shock, a ranking, a patch
    from core.series.shapes import draft_shape, shape_brief

    shape = "" if own_idea or long_form else draft_shape(topic, pick_source(topic, best_bet))
    if shape:  # #1692 (wave 159): a shape rotated out drafts the headline plainly
        from core.success.formats import _SHAPES, rotated_out

        if _SHAPES.get(shape) in rotated_out(channel_id):
            shape = ""
    if pick_source(topic, best_bet) == "explainer" and not long_form:  # #1680: about 60 s
        length_choice = "2"
        long_kwargs["word_range"] = EXPLAINER_WORDS
    with hook_arm_env(hook_arm):  # #1502
        result = run_pipeline(
            topic,
            discovery=discovery,
            variant_index=variant_index,
            length_choice=length_choice,
            proceed_video=False,
            channel_id=channel_id,
            # #1967 (wave 145): only words that say what the video is for are its idea - your
            # own, or a preview's matchup and call. The arm, the shape and the follow line are
            # directions: as "THE OPERATOR'S IDEA" they were checked as unanswered (2 of 5
            # drafts on 11-02) and paid a premium rewrite.
            creative_brief=topic if own_idea else preview,
            directions=""
            if own_idea
            else "\n".join(
                part
                for part in (
                    shape_arm[2] if shape_arm else "",
                    shape_brief(shape, topic),  # wave 157
                    experiment[2] if experiment else "",
                    # #1699 (S02): the format's true reason to follow, in its last line
                    follow_line,
                    _long_opener(channel_id) if long_form else "",  # #1745
                )
                if part
            ),
            key_facts=packed,
            relevance_corpus=corpus,
            best_bet=best_bet,
            own_idea=own_idea,
            own_topic=best_topic if own_idea else "",
            **long_kwargs,
        )
    if hook_arm and result.run_id:
        try:
            from core.experiments import record_assignment

            record_assignment(channel_id, result.run_id, hook_arm[0], hook_arm[1])
        except Exception as exc:
            logger.debug("hook arm not recorded: %s", exc)
    if shape_arm and result.run_id:
        try:
            from core.experiments import record_assignment

            record_assignment(channel_id, result.run_id, shape_arm[0], shape_arm[1])
        except Exception as exc:
            logger.debug("preview shape not recorded: %s", exc)
    if length_trial is not None and result.run_id:
        try:
            from core.experiments import record_assignment

            record_assignment(channel_id, result.run_id, LENGTH_LEVER, length_trial[0])
        except Exception as exc:
            logger.debug("length arm not recorded: %s", exc)
    if voice_arm and result.run_id:
        try:
            from core.experiments import record_assignment
            from core.voice.trial import VOICE_LEVER

            record_assignment(channel_id, result.run_id, VOICE_LEVER, voice_arm)
        except Exception as exc:
            logger.debug("voice arm not recorded: %s", exc)
    if follow_pick and result.run_id:
        try:
            from core.experiments import record_assignment

            record_assignment(channel_id, result.run_id, FOLLOW_LEVER, follow_pick)
        except Exception as exc:
            logger.debug("follow arm not recorded: %s", exc)
    _record_draft_features(result.run_id, shape, channel_id, beat=length_choice in ("1", "2"))
    if (best_bet or {}).get("part") == 1 and result.run_id:  # #1700: the pair opens
        from core.series.parts import record_part_one

        record_part_one(channel_id, topic, int(result.run_id), str(result.script or ""), key_facts)
    # #779: a script-only run always comes back aborted with "proceed_video=False" - the
    # pipeline records that as "drafted". Treating it as a failure kept 0 of 3 drafts on
    # the first real overnight run.
    drafted = result.abort_reason == "proceed_video=False"
    if (result.aborted and not drafted) or not (result.script or "").strip():
        out.error = result.abort_reason or "pipeline produced no script"
        return out
    out.title, out.run_id = result.title, result.run_id
    out.script = str(result.script or "")
    out.script_clean = result.features.get("script_clean")

    if experiment:
        lever, arm, _ = experiment
        out.experiment_arm = f"{lever}={arm}"
        try:
            from core.experiments import record_assignment

            record_assignment(channel_id, result.run_id, lever, arm)
        except Exception as exc:
            logger.debug("record_assignment skipped: %s", exc)

    # Same quality surface the interactive flow prints, persisted instead.
    try:
        from core.hook_score import score_script_hook

        hook = score_script_hook(result.script)
        out.hook_score, out.hook_verdict = hook.score, hook.verdict
    except Exception as exc:
        logger.debug("score_script_hook skipped: %s", exc)
    fact_count = 0
    used = (result.features or {}).get("fact_lines")
    if isinstance(used, int) and not isinstance(used, bool):
        fact_count = used  # #1217: the count the run was written from, not a second fetch
    else:
        try:
            from core.facts.enrichment import _fact_line_count, enrich_facts

            fact_count = _fact_line_count(
                enrich_facts(best_topic, best_signals, channel_id=channel_id, seed_topic=topic)
            )
        except Exception as exc:
            logger.debug("_fact_line_count skipped: %s", exc)
    recap: dict[str, Any] = {}
    if not own_idea and _recap_rewrite_enabled():  # #1936 (decision 92): one rewrite first
        try:
            result.script, recap = recap_rewrite(
                result.script, packed, best_topic, intent=machine_intent
            )
            if recap.get("kept") and result.run_id:
                from core.run_trace import write_full_script

                write_full_script(result.run_id, result.script)
        except Exception as exc:
            logger.debug("recap rewrite skipped: %s", exc)
    try:
        from core.authenticity import evaluate_authenticity, series_key

        fields = authenticity_fields(
            evaluate_authenticity(
                result.script,
                channel_id,
                fact_count=fact_count,
                exclude_run_id=result.run_id,
                series=series_key(str((best_bet or {}).get("title_stem") or "")),  # #1958
            )
        )
        out.authenticity_verdict = fields["authenticity_verdict"]
        out.authenticity_failed = fields["authenticity_failed"]
    except Exception as exc:
        logger.debug("evaluate_authenticity skipped: %s", exc)
    out.ungrounded = list(result.features.get("ungrounded_entities") or [])
    out.unsupported_claims = len(
        (result.features.get("claim_verification") or {}).get("unsupported") or []
    )
    out.fact_conflicts = len(result.features.get("fact_conflicts") or [])

    # #1151: say when the draft already calls the result of a game not yet played.
    unplayed = ""
    if upcoming:
        from core.facts.event_dates import unplayed_result

        unplayed = unplayed_result(str(result.title or ""), topic) or unplayed_result(
            result.script, topic
        )

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = os.path.join(_drafts_dir(channel_id), f"{stamp}-{_slug(best_topic)}")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "draft.md"), "w", encoding="utf-8") as f:
        f.write(f"# {result.title or best_topic}\n\n")
        f.write(f"**Topic:** {topic}\n**Angle:** {best_topic} (score {best_score})\n\n")
        f.write("## Script\n\n")
        f.write(result.script.strip() + "\n\n")
        f.write("## Description\n\n")
        f.write((result.description or "").strip() + "\n")
        if result.tags:
            f.write("\n## Tags\n\n" + ", ".join(result.tags) + "\n")
    meta = {
        "topic": topic,
        "variant": best_topic,
        "variant_score": best_score,
        "title": result.title,
        "run_id": result.run_id,
        "channel_id": channel_id,
        "own_idea": bool(own_idea),  # #1159
        "length_choice": length_choice,
        "hook_score": out.hook_score,
        "hook_verdict": out.hook_verdict,
        # #1503: the opener and the rewrite's sound runners-up, picked from at review
        "hook_options": hook_options(result.script, result.features.get("script_passes")),
        "authenticity_verdict": out.authenticity_verdict,
        "authenticity_failed": list(out.authenticity_failed),
        "recap_rewrite": recap or None,  # #1936
        "script_clean": result.features.get("script_clean"),  # #1143
        # #1150: run 139's title was flagged and overnight rendered it - the flag stopped here.
        "title_warnings": list(result.features.get("title_warnings") or []),
        # #1151; #1286: a headline naming a coming event (run 160) records that event's start.
        "event_at": draft_event_at(event_at, best_bet)
        or _named_event_start(f"{topic} {result.title or ''}")
        or None,
        # #1847: a countdown's day passing reads as that, not as a game starting
        **({"series": "countdown"} if (best_bet or {}).get("title_stem") else {}),
        # #1724: a season explainer is not news - it takes the weekly long slot (#1727)
        **({"series": "season"} if pick_source(topic, best_bet) == "season" else {}),
        # #1850: a long video; #1856 what YouTube suggests for its subject ([] = nobody searches)
        **(
            {"kind": "long", "search_suggestions": result.features.get("search_suggestions")}
            if long_form
            else {}
        ),
        # #1870: when its entry says it goes public
        **(
            {"publish_at": (best_bet or {}).get("publish_at")}
            if (best_bet or {}).get("publish_at")
            else {}
        ),
        "unplayed_result": unplayed or None,
        "fact_count": fact_count,
        "ungrounded_entities": out.ungrounded,
        "tier_warnings": result.features.get("tier_warnings") or [],
        "fact_conflicts": result.features.get("fact_conflicts") or [],
        "claim_verification": result.features.get("claim_verification"),
        # #965: settled or fresh, and whether anyone pasted facts for it.
        "research": result.features.get("research"),
        "key_facts_count": len(packed or []),
        "experiment": out.experiment_arm or None,
        "cost": result.features.get("cost"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str)

    out.path, out.ok, out.seconds = folder, True, round(time.time() - started, 1)
    return out


def _named_event_start(text: str, *, now: datetime | None = None) -> str:
    """#1286: the start of a coming event `text` names, or "". Only a coming one: a headline
    about a card already fought is a recap, and a recap has no window to miss."""
    try:
        from core.seasonal_calendar import _start_of, event_for

        _name, start = event_for(text)
    except Exception as exc:
        logger.debug("named event unread: %s", exc)
        return ""
    when = _start_of(start) if start else None
    if when is None or when <= (now or datetime.now(timezone.utc)):
        return ""
    return start


def preview_shape_arm(channel_id: str, preview: str) -> tuple[str, str, str] | None:
    """#1366 (decision 78): the shape a preview draft takes - the `preview_shape` experiment's
    next arm - or None for any other draft, or while the experiment is not running."""
    if not preview:
        return None
    try:
        from core.experiments import next_arm

        return next_arm(channel_id, kind="preview")
    except Exception as exc:
        logger.debug("preview shape skipped: %s", exc)
        return None


# Wave 159 (defect, live 11-07): a series idea that names a coming card keeps its own shape. "Gane
# vs. Hokit: who wins at UFC 334?" and "UFC 334: Gane vs. Hokit - how they match up" named the card,
# `_named_event_start` found it ahead, and both were drafted as previews - a call where the debate
# leaves the question open, a preview brief on a 6-8 minute match-up.
OWN_SHAPE_SOURCES = ("debate", "long", "explainer", "profile", "part2", "patch", "season")
EXPLAINER_WORDS = (165, 200)  # #1680: "in 60 seconds" at 3.3 words a second


def keeps_own_shape(source: str) -> bool:
    """A pick whose menu source writes its own shape - never turned into a preview by the event its
    topic names."""
    return source in OWN_SHAPE_SOURCES


def preview_for(topic: str, best_bet: dict | None, *, upcoming: bool) -> str:
    """The preview brief a draft takes when its event is ahead, or "" - never for a series idea
    that writes its own shape (`keeps_own_shape`)."""
    if not upcoming or keeps_own_shape(pick_source(topic, best_bet)):
        return ""
    return draft_brief(topic, best_bet)


def draft_intent(*, own_idea: bool, preview: str, source: str = "") -> str:
    """#1588: what a draft is - "" for the operator's own idea (its words are read for cues),
    "preview" for a coming game, "default" otherwise. Headline words ("vs.", "reaction") and
    the machine's own brief ("what is at stake") had been read as the operator's ask.
    #1594 (decision 81): a headline (`trending`) is "news" - the story and why fans care."""
    from core.angle_intent import ANGLE_DEFAULT, ANGLE_NEWS, ANGLE_PREVIEW

    if own_idea:
        return ""
    if preview:
        return ANGLE_PREVIEW
    # #1965 (wave 145): a countdown is the day's news on its subject. Read as "default", run 226
    # took the repeat-coverage table's "what changed since launch" for a game not yet out.
    # #1608: a "more of what worked" idea is a fresh headline - news too.
    # #1999 (wave 153): last night's result is news - what it means.
    if source == "debate":  # #1673 (wave 155): "who wins?" - both sides' case, no pick
        from core.angle_intent import ANGLE_COMPARISON

        return ANGLE_COMPARISON
    if source == "explainer":  # #1680 (wave 159): what to know before it starts
        from core.angle_intent import ANGLE_EXPLAINER

        return ANGLE_EXPLAINER
    # #1686 (wave 156): "Who is ...?" is news - who they are and why they are in it now.
    # #1688: a patch; #1700: a part 2 is the story's news, the day after
    news = ("trending", "countdown", "worked", "result", "profile", "patch", "part2")
    return ANGLE_NEWS if source in news else ANGLE_DEFAULT


def pick_source(topic: str, best_bet: dict | None) -> str:
    """The menu source of the option `topic` was taken as ("trending", "series", ...), or ""."""
    for option in (best_bet or {}).get("offered") or []:
        if isinstance(option, dict) and option.get("topic") == topic:
            return str(option.get("source") or "")
    return ""


def draft_event_at(event_at: str, best_bet: dict | None) -> str:
    """#1847: a draft's deadline - its game's start, else a countdown's day end. The checks built
    for a kickoff then render it first, slot it before it, hold it after and retire it."""
    return event_at or str((best_bet or {}).get("deadline") or "")


def _recap_rewrite_enabled() -> bool:
    return os.getenv("RECAP_REWRITE", "true").strip().lower() not in ("0", "false", "no", "off")


def recap_rewrite(
    script: str, facts: list[str] | None, topic: str, *, intent: str = ""
) -> tuple[str, dict[str, Any]]:
    """#1936 (decision 92, the operator: "rewrite once, then show the cost"): a draft today's
    detector reads as a recap gets one more insight pass before it reaches review. (script,
    {tried, kept, ...the pass's record}); ({} and the script as it was) when it has a take."""
    from core.authenticity import has_insight

    if not (script or "").strip() or has_insight(script):
        return script, {}
    from core.content_engine import insight_pass

    new, record = insight_pass(script, "\n".join(facts or []), topic, intent=intent)
    kept = bool(new) and new != script and has_insight(new)
    return (new if kept else script), {"tried": True, "kept": kept, **record}


_DAYS_RE = re.compile(r"\b(\d+) days? to launch\b", re.I)


def _long_opener(channel_id: str) -> str:
    """#1745: the opener the measured long videos taught, or "" (never raises)."""
    try:
        from analytics.hook_learning import long_opener_guidance

        return long_opener_guidance(channel_id)
    except Exception as exc:
        logger.debug("long opener guidance skipped: %s", exc)
        return ""


def follow_brief(
    best_bet: dict | None,
    *,
    channel_id: str = "tapin",
    today: date | None = None,
    arm: str | None = None,
) -> str:
    """#1699 (S02, B05.3): the true reason to follow a format has, as the script's last line - "",
    for a format without one. A preview with a call has its own (#1322, `preview_brief`); 4 of the
    channel's 162 subscribers in 28 days came from its videos.

    - a countdown: there is one every day until launch, and tomorrow's number;
    - a launch moment: the subject's countdown, while it runs;
    - a long video: the Week in Review at the weekly long slot (#1727: "every Sunday"; it said
      "every Monday" while the three went out Tuesday, Tuesday and Monday)."""
    bet = best_bet or {}
    offered = bet.get("offered") or []
    raw = bet.get("picked")
    picked = raw if isinstance(raw, int) else 1
    chosen = offered[picked - 1] if isinstance(offered, list) and 0 < picked <= len(offered) else {}
    source = str((chosen or {}).get("source") or "")
    if source == "debate":  # #1642 (wave 155): a debate ends on the honest question
        return (" End on the honest question, once - who wins? - and leave it open: no pick, and "
                "no call to comment.")  # fmt: skip
    # #1700 (wave 158): part 1 ends on what part 2 answers; part 2 opens on the answer
    from core.series.parts import part_brief

    if source == "part2":
        return part_brief(2, str((chosen or {}).get("topic") or ""))
    if bet.get("part") == 1:
        return part_brief(1)
    lead = " End on why to follow, in your own words, once:"
    if bet.get("title_stem") or source == "countdown":
        found = _DAYS_RE.search(str(bet.get("title_stem") or ""))
        left = int(found.group(1)) - 1 if found else None
        example = (
            f"Tomorrow: {left} days to go - follow so you don't miss a day."
            if left and left > 0
            else "It's out tomorrow - follow for launch day."
        )
        return f'{lead} there is one of these every day until launch - for example "{example}"'
    from core.spaced_queue import long_slot_words

    when = long_slot_words()
    if bet.get("draft_kind") == "long" or source == "long":
        return (
            " End on why to subscribe, in your own words, once: the Week in Review comes out "
            f'{when} - for example "Subscribe - the Week in Review lands {when}."'
        )
    if not bet:
        return ""  # an idea of your own: it says what it means to
    topic = str((chosen or {}).get("topic") or "")
    from apis.topic_tokens import names_any
    from core.series.countdown import series_rows

    if source != "moment":  # #1729 (decision 96): the full video on the subject, when public
        from core.series import long_form

        subject = long_form.public_long_subject(channel_id, topic)
        if subject:
            return (f"{lead} the full {subject} video is up - for example \"The full {subject} "
                    f'breakdown is on the channel."')  # fmt: skip
    day = today or date.today()
    for row in series_rows(channel_id):
        if row.get("kind") != "countdown":
            continue
        try:
            until = date.fromisoformat(str(row.get("until") or "")[:10])
        except ValueError:
            continue
        names = [str(n) for n in row.get("names") or [row.get("subject")] if n]
        if day < until and (source == "moment" or names_any(topic, names)):
            subject = str(row.get("subject") or "the launch")
            return (f"{lead} there is a {subject} countdown Short every day until launch - for "
                    f'example "Follow - the {subject} countdown is here every day until launch."')  # fmt: skip
    if source == "moment":
        return ""
    # #1943 (S02): a trending Short's true reason - the Week in Review, at its weekly time;
    # #1719 (wave 160): on trial Nov 8-21 against "the next big story lands here first"
    from core.success.follow_trial import follow_wording

    return follow_wording(arm, when)


def draft_brief(topic: str, best_bet: dict | None) -> str:
    """The preview brief for a coming game or card - with the call it was offered with (#1301)
    - or "". main.py and overnight both write a preview from it; main.py wrote none."""
    from core.facts.event_dates import game_started, preview_brief

    event_at = _game_start(topic, best_bet) or _named_event_start(topic)
    if not event_at or game_started(event_at) is not False:
        return ""
    offered = (best_bet or {}).get("offered") or []
    call = next(
        (
            str(option.get("call") or "")
            for option in offered
            if isinstance(option, dict) and option.get("topic") == topic
        ),
        "",
    )
    return preview_brief(event_at, call=call)


def _game_start(topic: str, best_bet: dict | None) -> str:
    """The start of the game `topic` names when the pick came off the schedule, else ""."""
    offered = (best_bet or {}).get("offered") or []
    if not any(
        isinstance(option, dict)
        and option.get("topic") == topic
        and option.get("source") == "schedule"
        for option in offered
    ):
        return ""
    try:
        from core.seasonal_calendar import event_start

        return str(event_start(topic) or "")
    except Exception as exc:
        logger.debug("game start unavailable for %r: %s", topic, exc)
        return ""


def run_batch(
    channel_id: str,
    topics: list[str],
    *,
    key_facts: list[str] | None = None,
    picks: dict[str, dict] | None = None,
) -> list[DraftOutcome]:
    """Generate a draft per topic; one failure never kills the batch.

    ``key_facts`` apply to every topic (one overnight digest, N drafts). ``picks`` maps
    a best-bet topic to its `pick_record` (#913).
    """
    from apis.register_signals import franchise_batch_cache

    outcomes: list[DraftOutcome] = []
    with franchise_batch_cache(topics, channel_id=channel_id):
        for i, topic in enumerate(topics, 1):
            logger.info("Batch draft %d/%d: %s", i, len(topics), topic)
            existing = unreviewed_draft(channel_id, topic)
            if existing is not None:
                folder, meta = existing
                outcomes.append(
                    DraftOutcome(
                        topic=topic,
                        ok=True,
                        reused=True,
                        title=str(meta.get("title") or ""),
                        variant=str(meta.get("variant") or ""),
                        run_id=meta.get("run_id"),
                        path=folder,
                    )
                )
                continue
            try:
                pick = (picks or {}).get(topic)
                if pick:
                    outcome = generate_draft(topic, channel_id, key_facts=key_facts, best_bet=pick)
                else:
                    outcome = generate_draft(topic, channel_id, key_facts=key_facts)
                outcomes.append(outcome)
            except Exception as exc:
                logger.warning("Draft failed for %r: %s", topic, exc)
                outcomes.append(DraftOutcome(topic=topic, error=str(exc)))
    try:
        from core.pipeline import finalize_run_observability

        finalize_run_observability()
    except Exception as exc:
        logger.debug("finalize_run_observability skipped: %s", exc)
    try:
        from core.events import emit_event

        emit_event(
            "batch_completed",
            {
                "channel_id": channel_id,
                "requested": len(topics),
                "saved": sum(1 for o in outcomes if o.ok),
                "drafts": [
                    {"topic": o.topic, "ok": o.ok, "title": o.title, "path": o.path}
                    for o in outcomes
                ],
            },
        )
    except Exception as exc:
        logger.debug("batch_completed event not emitted: %s", exc)
    return outcomes


def render_summary(outcomes: list[DraftOutcome]) -> str:
    lines = ["", "Batch drafts", "=" * 40]
    for o in outcomes:
        if o.reused:
            lines.append(f"  KEEP {o.title or o.topic} - draft already waiting for review")
            lines.append(f"       {o.path}")
        elif o.ok:
            hook = f"hook {o.hook_score}" if o.hook_score is not None else "hook n/a"
            auth = o.authenticity_verdict or "n/a"
            flags = f", {len(o.ungrounded)} ungrounded" if o.ungrounded else ""
            if o.unsupported_claims:
                flags += f", {o.unsupported_claims} unsupported claim(s)"
            if o.fact_conflicts:
                flags += f", {o.fact_conflicts} fact conflict(s)"
            arm = f", A/B {o.experiment_arm}" if o.experiment_arm else ""
            lines.append(f"  OK   {o.title or o.variant}")
            lines.append(f"       {hook} ({o.hook_verdict}), authenticity {auth}{flags}{arm}")
            lines.append(f"       {o.path}  [{o.seconds:.0f}s]")
        else:
            lines.append(f"  FAIL {o.topic} — {o.error}")
    made = sum(1 for o in outcomes if o.ok)
    lines.append(f"  {made}/{len(outcomes)} drafts saved")
    if made:
        lines.append("  Review them: py -m scripts.ops batch-review")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="N ideas -> N draft scripts, unattended")
    parser.add_argument("topics", nargs="*", help="Topics (default: best bets)")
    parser.add_argument("--channel", default="tapin", help="Channel id (default: tapin)")
    parser.add_argument("--file", default=None, help="File with one topic per line")
    parser.add_argument(
        "--count", type=int, default=3, help="How many best-bet topics when none given"
    )
    parser.add_argument(
        "--facts-file",
        default="",
        help="Operator key facts (paste-block file) applied to every draft in the batch",
    )
    args = parser.parse_args(argv)

    from core.run_mode import CostModeBlocked, apply_and_guard

    try:
        apply_and_guard()
    except CostModeBlocked as exc:
        print(f"  {exc}")
        return 2

    from core.operator_facts import load_key_facts

    key_facts = load_key_facts(args.facts_file)
    picks: dict[str, dict] = {}
    topics = collect_topics(args.channel, args.topics, args.file, args.count, picks=picks)
    if not topics:
        print("No topics to draft (give topics, --file, or record analytics for best bets).")
        return 1
    outcomes = run_batch(args.channel, topics, key_facts=key_facts or None, picks=picks)
    print(render_summary(outcomes))
    return 0 if any(o.ok for o in outcomes) else 1


if __name__ == "__main__":
    from core.console_encoding import ensure_utf8_stdout

    ensure_utf8_stdout()  # #767: redirected / scheduled runs are cp1252
    raise SystemExit(main())
