"""Audience questions + content gaps from YouTube comments on a topic's top videos.

The richest source of *new angles*: what viewers are still asking after watching the
best existing coverage is, by definition, what nobody has answered yet.

**Free-first, unlike the catalog entry.** `config/apify_sources.json` templates this as
`streamers/youtube-comments-scraper`, which would bill Apify credits for data the
official Data API already serves under a key we hold. `commentThreads.list` costs
**1 quota unit per video** against a 10,000/day budget, so the whole signal is ~103
units (one 100-unit search + N comment reads) versus a paid actor run. The catalog
entry is left in place for parity but this signal never calls it.

Comments are **audience language, not verified fact** — `signal_facts` labels them as
questions/discussion so the script prompt can't mistake a viewer's guess for a source.

Contract notes:
- Quota is checked before the search *and* before each comment read, so a partial
  budget yields partial results rather than a hard failure.
- Videos with comments disabled return 403 `commentsDisabled`; that is a normal
  per-video skip, not a signal failure.
- Never raises (`apis/CLAUDE.md`); no cache of its own (`_fetch_one` already caches).
"""

from __future__ import annotations

import os
import re
from collections import Counter
from typing import Any

from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    STATUS_QUOTA,
    classify_exception,
    make_signal,
)
from apis.youtube_quota import (
    UNITS_VIDEOS_LIST,
    format_quota_detail,
    has_quota_for_search,
    record_usage,
)
from core.logging import get_logger

logger = get_logger("apis.youtube_comments")

# Words that dominate any comment section without carrying a topic signal.
_STOP = frozenset(
    """the and for you your that this with have has had was were are but not all can
    just like get got dont don't didn't its it's they them their there then than what
    when where who why how out one two too very much more most some any own same about
    would could should will need make made take does did been being over into from
    still only also because after before again even really thing things guys video
    videos watch watching people time good great best better bad worse love hate
    think know say said see saw look looks going gonna want wanted""".split()
)

_QUESTION_RE = re.compile(r"[^.!?]*\?")

# Comment sections are crude; these lines feed the script prompt on an
# advertiser-facing channel, so drop the obvious offenders rather than trusting the
# LLM to launder them. Substring match is deliberate (catches -ing/-ed variants).
_PROFANITY = ("fuck", "shit", "bitch", "cunt", "dick", "asshole", "bastard", "retard")


def _is_clean(text: str) -> bool:
    lowered = (text or "").lower()
    return not any(word in lowered for word in _PROFANITY)


def _max_videos() -> int:
    try:
        return max(1, min(int(os.getenv("YOUTUBE_COMMENTS_MAX_VIDEOS", "3")), 10))
    except ValueError:
        return 3


def _max_comments() -> int:
    try:
        return max(5, min(int(os.getenv("YOUTUBE_COMMENTS_PER_VIDEO", "25")), 100))
    except ValueError:
        return 25


def _clean(text: str) -> str:
    return " ".join((text or "").replace("\n", " ").split())


def topic_tokens(topic: str) -> set[str]:
    """Meaningful words from the topic, for relevance-checking a question."""
    return {w for w in re.findall(r"[a-z0-9']{3,}", (topic or "").lower()) if w not in _STOP}


def _is_useful_question(text: str, topic: str = "") -> bool:
    """A question worth surfacing as an angle, not chat noise.

    Relevance is the point: these become *content gaps to answer*, so a question that
    shares nothing with the topic is not a gap in our coverage. Run 66 surfaced only
    "What about Alaska?" from 25 comments on a GTA VI video — exactly 18 chars (the old
    floor) and unrelated to the topic.
    """
    stripped = text.strip()
    if len(stripped) < 25 or len(stripped) > 200:
        return False
    if not _is_clean(stripped):
        return False
    lowered = stripped.lower()
    # "who else watching?", "sub to my channel" are noise, not content gaps.
    noise = ("who else", "anyone else", "who's here", "whos here", "sub to")
    if any(n in lowered for n in noise):
        return False
    # "first" only signals bait when the comment IS the claim ("first?", "im first").
    # As a substring it also matches legitimate questions — "why is it on Netflix
    # first?" was being thrown away with the bait.
    if re.fullmatch(r"(i'?m\s+|im\s+)?first[\s!?.]*", lowered):
        return False

    wanted = topic_tokens(topic)
    if not wanted:
        return True  # no topic to compare against — keep the old behaviour
    words = set(re.findall(r"[a-z0-9']{3,}", lowered))
    return bool(words & wanted)


def _themes(comments: list[dict[str, Any]], topic: str, limit: int = 8) -> list[str]:
    """Recurring vocabulary the audience uses, minus the topic's own words."""
    topic_words = set(re.findall(r"[a-z']{3,}", topic.lower()))
    counter: Counter[str] = Counter()
    for c in comments:
        if not _is_clean(str(c.get("text", ""))):
            continue
        for word in re.findall(r"[a-z']{4,}", str(c.get("text", "")).lower()):
            if word in _STOP or word in topic_words:
                continue
            counter[word] += 1
    return [w for w, n in counter.most_common(limit) if n >= 2]


def _fetch_comments(youtube, video_id: str, limit: int) -> list[dict[str, Any]]:
    """Top comments for one video. Returns [] when comments are off or unavailable."""
    try:
        response = (
            youtube.commentThreads()
            .list(
                part="snippet",
                videoId=video_id,
                order="relevance",
                maxResults=limit,
                textFormat="plainText",
                fields=(
                    "items(snippet/topLevelComment/snippet/textDisplay,"
                    "snippet/topLevelComment/snippet/likeCount,snippet/totalReplyCount)"
                ),
            )
            .execute()
        )
    except Exception as exc:
        # commentsDisabled / videoNotFound are routine; log and move on.
        logger.debug("comments unavailable for %s: %s", video_id, exc)
        return []

    record_usage(units=UNITS_VIDEOS_LIST)
    out: list[dict[str, Any]] = []
    for item in response.get("items") or []:
        snippet = ((item.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
        text = _clean(snippet.get("textDisplay", ""))
        if not text:
            continue
        out.append(
            {
                "text": text[:280],
                "likes": int(snippet.get("likeCount") or 0),
                "replies": int((item.get("snippet") or {}).get("totalReplyCount") or 0),
                "video_id": video_id,
            }
        )
    return out


def gather_comment_intel(topic: str) -> dict[str, Any]:
    """Questions, top comments and themes for a topic. Never raises."""
    from apis.youtube_api import _get_youtube_client, _search_videos

    youtube = _get_youtube_client()
    search = _search_videos(youtube, topic)
    record_usage()  # search.list + the videos.list the helper implies

    video_ids = [
        item["id"]["videoId"]
        for item in (search.get("items") or [])
        if (item.get("id") or {}).get("kind") == "youtube#video"
        and (item.get("id") or {}).get("videoId")
    ][: _max_videos()]

    comments: list[dict[str, Any]] = []
    scanned = 0
    for video_id in video_ids:
        if not has_quota_for_search():
            logger.debug("stopping comment scan early — quota low")
            break
        fetched = _fetch_comments(youtube, video_id, _max_comments())
        if fetched:
            scanned += 1
            comments.extend(fetched)

    questions: list[str] = []
    seen: set[str] = set()
    for c in sorted(comments, key=lambda c: -(c["likes"] + c["replies"] * 2)):
        for raw in _QUESTION_RE.findall(c["text"]):
            q = _clean(raw)
            if not _is_useful_question(q, topic):
                continue
            key = q.lower()[:60]
            if key in seen:
                continue
            seen.add(key)
            questions.append(q)
            if len(questions) >= 8:
                break
        if len(questions) >= 8:
            break

    clean = [c for c in comments if _is_clean(c["text"])]
    top = sorted(clean, key=lambda c: -(c["likes"] + c["replies"] * 2))[:6]
    return {
        "questions": questions,
        "top_comments": [{"text": c["text"], "likes": c["likes"]} for c in top],
        "themes": _themes(comments, topic),
        "videos_scanned": scanned,
        "comment_count": len(comments),
    }


def get_youtube_comments_signal(topic: str) -> dict[str, Any]:
    from apis.youtube_api import _youtube_key

    if not _youtube_key():
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set YOUTUBE_API_KEY in .env",
        )
    if not has_quota_for_search():
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_QUOTA,
            status_detail=f"Daily quota exhausted — {format_quota_detail()}",
        )

    try:
        data = gather_comment_intel(topic)
        if not data.get("comment_count"):
            return make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail="No comments found (or comments disabled on top videos)",
                data=data,
            )
        # Questions are the payload that matters; raw comment volume alone is weak.
        score = min(30 + len(data["questions"]) * 8 + data["videos_scanned"] * 5, 95)
        return make_signal(
            connected=True,
            active=True,
            score=float(score),
            confidence=0.7,  # audience language, not verified fact
            status=STATUS_OK,
            status_detail=(
                f"{data['comment_count']} comments from {data['videos_scanned']} video(s), "
                f"{len(data['questions'])} question(s)"
            ),
            data=data,
        )
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)
