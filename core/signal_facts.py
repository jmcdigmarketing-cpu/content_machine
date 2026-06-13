"""Format signal payloads into LLM-readable fact blocks."""

from __future__ import annotations

import json
from typing import Any


def _format_headlines(headlines: list) -> str:
    lines = []
    for item in headlines[:8]:
        if isinstance(item, dict):
            title = item.get("title") or ""
            source = item.get("source") or ""
            desc = item.get("description") or ""
            if title:
                line = f"- {title}"
                if source:
                    line += f" ({source})"
                if desc:
                    line += f" — {desc}"
                lines.append(line)
        elif isinstance(item, str) and item.strip():
            lines.append(f"- {item.strip()}")
    return "\n".join(lines) if lines else ""


def format_signal_facts(signals: dict[str, Any]) -> str:
    lines = []

    for name, signal in signals.items():
        if not signal.get("connected") or not signal.get("active"):
            continue

        data = signal.get("data")
        if not data:
            continue

        if name == "tapology" and isinstance(data, dict):
            if data.get("event_title") or data.get("matched_event"):
                lines.append(
                    "Tapology event: " + str(data.get("matched_event") or data.get("event_title"))
                )
            if data.get("event_date"):
                lines.append(f"Tapology date: {data['event_date']}")
            for bout in data.get("bouts") or []:
                if isinstance(bout, dict) and bout.get("red") and bout.get("blue"):
                    lines.append(f"Tapology bout: {bout['red']} vs {bout['blue']}")
                elif isinstance(bout, dict) and bout.get("main_event"):
                    lines.append(f"Tapology main: {bout['main_event']}")

        elif name == "ufc_context" and isinstance(data, dict):
            tap = data.get("tapology") or {}
            if isinstance(tap, dict):
                if tap.get("matched_event") or tap.get("event_title"):
                    lines.append(
                        "Tapology: " + str(tap.get("matched_event") or tap.get("event_title"))
                    )
                if tap.get("event_date"):
                    lines.append(f"Tapology date: {tap['event_date']}")
                for bout in tap.get("bouts") or []:
                    if isinstance(bout, dict) and bout.get("red") and bout.get("blue"):
                        lines.append(f"Card: {bout['red']} vs {bout['blue']}")

            headlines = _format_headlines(data.get("headlines") or [])
            if headlines:
                lines.append("UFC/MMA headlines:\n" + headlines)

            rss_mma = data.get("rss_headlines") or []
            if rss_mma:
                posts = [
                    f"- {p.get('title', '')} ({p.get('source', '')})"
                    for p in rss_mma[:5]
                    if isinstance(p, dict) and p.get("title")
                ]
                if posts:
                    lines.append("MMA RSS:\n" + "\n".join(posts))

            note = data.get("research_note")
            if note:
                lines.append(str(note))

        elif name == "news" and isinstance(data, dict):
            headlines = _format_headlines(data.get("headlines") or [])
            if headlines:
                lines.append("News headlines:\n" + headlines)

        elif name == "sports" and isinstance(data, list):
            teams = [
                t.get("strTeam") or t.get("strAlternate") for t in data[:3] if isinstance(t, dict)
            ]
            teams = [t for t in teams if t]
            if teams:
                lines.append(f"sports teams (API): {', '.join(teams)}")

        elif name == "youtube" and isinstance(data, dict):
            titles = data.get("titles") or []
            descriptions = data.get("descriptions") or []
            if titles:
                lines.append(
                    "YouTube — real video titles on this topic (shows what creators are "
                    "covering; use as topic evidence, NOT as facts about specific events):\n"
                    + "\n".join(f"  • {t}" for t in titles[:10] if t)
                )
            # Descriptions often contain patch note specifics — surface non-empty ones
            desc_facts = []
            for desc in descriptions[:5]:
                if not desc or not desc.strip():
                    continue
                # Take first two meaningful lines (skip empty/boilerplate)
                meaningful = [
                    ln.strip() for ln in desc.splitlines() if ln.strip() and len(ln.strip()) > 20
                ][:2]
                desc_facts.extend(meaningful)
            if desc_facts:
                lines.append(
                    "YouTube video descriptions (may contain patch/hero specifics — "
                    "use only if directly relevant):\n"
                    + "\n".join(f"  → {d}" for d in desc_facts[:6])
                )

        elif name == "stats_context" and isinstance(data, dict):
            for line in data.get("lines") or []:
                if line:
                    lines.append(f"Stats: {line}")

        elif name == "blog_rss" and isinstance(data, dict):
            headlines = _format_headlines(data.get("headlines") or [])
            if headlines:
                lines.append("Blog/RSS:\n" + headlines)

        elif name == "rawg" and isinstance(data, list):
            for game in data[:3]:
                if not isinstance(game, dict):
                    continue
                name_g = game.get("name") or ""
                if not name_g:
                    continue
                parts = [f"RAWG: {name_g}"]
                if game.get("released"):
                    parts.append(f"released {game['released']}")
                if game.get("rating"):
                    parts.append(f"rating {game['rating']}")
                genres = [
                    g.get("name")
                    for g in (game.get("genres") or [])[:3]
                    if isinstance(g, dict) and g.get("name")
                ]
                if genres:
                    parts.append("genres: " + ", ".join(genres))
                tags = [
                    t.get("name")
                    for t in (game.get("tags") or [])[:5]
                    if isinstance(t, dict) and t.get("name")
                ]
                if tags:
                    parts.append("tags: " + ", ".join(tags))
                lines.append(" — ".join(parts))

        elif name == "live_scores" and isinstance(data, dict):
            game = data.get("matched_game")
            if game:
                lines.append(
                    "ESPN live/final (use as source of truth for score and winner): "
                    f"{game.get('away_team')} {game.get('away_score')} at "
                    f"{game.get('home_team')} {game.get('home_score')} — "
                    f"{game.get('status')}"
                    + (f" — winner: {game.get('winner')}" if game.get("winner") else "")
                )

        elif name == "reddit" and isinstance(data, dict):
            posts = data.get("posts") or []
            if posts:
                post_lines = []
                for p in posts[:6]:
                    title = (p.get("title") or "").strip()
                    sub = p.get("subreddit") or ""
                    ups = p.get("ups") or 0
                    comments = p.get("comments") or 0
                    if title:
                        post_lines.append(
                            f'- r/{sub}: "{title}" ({ups:,} upvotes, {comments} comments)'
                        )
                if post_lines:
                    lines.append("Reddit community (verified hot posts):\n" + "\n".join(post_lines))

        elif name == "tiktok_trends" and isinstance(data, dict):
            videos = data.get("videos") or []
            hashtags = data.get("top_hashtags") or []
            avg_views = data.get("avg_views") or 0
            if videos:
                vid_lines = [
                    f"- \"{v.get('title', '')[:80]}\" ({v.get('views', 0):,} views)"
                    for v in videos[:5]
                    if v.get("title")
                ]
                summary = f"TikTok trending (avg {avg_views:,} views/video):\n" + "\n".join(
                    vid_lines
                )
                if hashtags:
                    summary += "\n  Top hashtags: " + ", ".join(f"#{h}" for h in hashtags[:6])
                lines.append(summary)

        elif name == "youtube_competitors" and isinstance(data, dict):
            videos = data.get("videos") or []
            median = data.get("median_duration_secs") or 0
            if videos:
                vid_lines = []
                for v in videos[:8]:
                    title = (v.get("title") or "").strip()
                    if not title:
                        continue
                    vel = v.get("velocity") or 0
                    ch = v.get("channel") or ""
                    suffix = f" ({vel:,.0f} views/day"
                    suffix += f", {ch})" if ch else ")"
                    vid_lines.append(f"  • {title}{suffix}")
                if vid_lines:
                    block = (
                        "YouTube competitor performance — videos ranking NOW for this "
                        "topic, by view velocity (proven angles/titles; topic evidence, "
                        "NOT facts about specific events):\n" + "\n".join(vid_lines)
                    )
                    if median:
                        block += f"\n  Winning length: ~{median // 60}m{median % 60:02d}s median"
                    lines.append(block)

        elif name == "twitter" and isinstance(data, dict):
            tweets = data.get("tweets") or []
            if tweets:
                tw_lines = []
                for t in tweets[:6]:
                    text = (t.get("text") or "").replace("\n", " ").strip()
                    author = t.get("author") or "?"
                    if not text:
                        continue
                    tag = " [authority]" if t.get("authority") else ""
                    tw_lines.append(f'  • @{author}{tag}: "{text}"')
                if tw_lines:
                    lines.append(
                        "Twitter/X — recent posts on this topic (attributable; treat "
                        "authority-tagged accounts as more reliable, verify specifics "
                        "before stating as fact):\n" + "\n".join(tw_lines)
                    )

        elif isinstance(data, dict | list):
            snippet = json.dumps(data, ensure_ascii=False)[:400]
            lines.append(f"{name} data: {snippet}")

    return "\n".join(lines) if lines else "No structured facts from signals."
