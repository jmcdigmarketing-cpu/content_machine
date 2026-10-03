"""The comment mailbag: what your own viewers ask (#114).

The `youtube_comments` signal reads comments on *other* channels' videos about a topic.
Nothing read the questions under the channel's own uploads - the most direct demand signal
a channel has. `fetch` asks the YouTube Data API for the top comment threads on the
channel's newest uploads (`commentThreads.list`, 1 unit per video, `MAILBAG_VIDEOS`
videos), keeps the questions (the same filters the signal uses), and clusters them by the
words they share (`apis/topic_tokens`). The clusters are stored in
`data/mailbag_<channel>.json`.

A question two or more viewers asked becomes a best-bet candidate ("viewers asked"), and
`ops mailbag` lists them. Fetching happens in `ops mailbag`, and in the metrics sync only
with `MAILBAG_SYNC=true`.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("analytics.mailbag")

MAILBAG_TEMPLATE = os.path.join(DATA_DIR, "mailbag_{channel}.json")
MIN_ASKERS = 2
_MIN_SHARED = 2


def sync_enabled() -> bool:
    return os.getenv("MAILBAG_SYNC", "").strip().lower() in ("1", "true", "yes")


def _videos_to_read() -> int:
    try:
        return max(1, min(int(os.getenv("MAILBAG_VIDEOS", "") or 10), 50))
    except ValueError:
        return 10


def _path(channel_id: str) -> str:
    return MAILBAG_TEMPLATE.format(channel=channel_id)


def _words(text: str) -> set[str]:
    from apis.topic_tokens import content_tokens, distinctive_tokens

    return set(distinctive_tokens(content_tokens(text, min_len=3)))


def questions_from_comments(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """[{text, likes, video_id}] - each comment's questions, by the signal's own filters."""
    from apis.youtube_comments_signal import _QUESTION_RE, _clean, _is_useful_question

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for c in comments:
        for raw in _QUESTION_RE.findall(str(c.get("text") or "")):
            q = _clean(raw)
            key = q.lower()
            if key in seen or not _is_useful_question(q):
                continue
            seen.add(key)
            out.append(
                {
                    "text": q,
                    "likes": int(c.get("likes") or 0) + 2 * int(c.get("replies") or 0),
                    "video_id": str(c.get("video_id") or ""),
                }
            )
    return out


def cluster_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Greedy clusters: a question joins the first cluster whose lead question shares
    `_MIN_SHARED`+ distinctive words with it. Biggest cluster first; the most-liked
    question leads each."""
    clusters: list[dict[str, Any]] = []
    for q in sorted(questions, key=lambda q: -q["likes"]):
        words = _words(q["text"])
        for cluster in clusters:
            if len(words & cluster["_words"]) >= _MIN_SHARED:
                cluster["count"] += 1
                if q["video_id"] and q["video_id"] not in cluster["videos"]:
                    cluster["videos"].append(q["video_id"])
                if len(cluster["examples"]) < 3:
                    cluster["examples"].append(q["text"])
                break
        else:
            clusters.append(
                {
                    "question": q["text"],
                    "count": 1,
                    "videos": [q["video_id"]] if q["video_id"] else [],
                    "examples": [q["text"]],
                    "_words": words,
                }
            )
    clusters.sort(key=lambda c: -c["count"])
    for c in clusters:
        c.pop("_words", None)
    return clusters


def fetch(channel_id: str) -> dict[str, Any]:
    """Read the newest uploads' comments, cluster the questions, store and return them."""
    from apis.youtube_api import _get_youtube_client
    from apis.youtube_comments_signal import _fetch_comments, _max_comments
    from core.success.videos import channel_videos

    videos = channel_videos(channel_id, include_seeded=False)[: _videos_to_read()]
    youtube = _get_youtube_client()
    comments: list[dict[str, Any]] = []
    read = 0
    for video in videos:
        fetched = _fetch_comments(youtube, video.video_id, _max_comments())
        if fetched:
            read += 1
            comments.extend(fetched)
    data = {
        "channel_id": channel_id,
        "fetched_at": time.time(),
        "videos": read,
        "comments": len(comments),
        "clusters": cluster_questions(questions_from_comments(comments)),
    }
    os.makedirs(os.path.dirname(_path(channel_id)) or ".", exist_ok=True)
    tmp = f"{_path(channel_id)}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, _path(channel_id))
    return data


def load(channel_id: str) -> dict[str, Any]:
    try:
        with open(_path(channel_id), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def top_question(channel_id: str, *, exclude: set[str] | None = None) -> dict[str, Any] | None:
    """The most-asked stored question `MIN_ASKERS`+ viewers asked, not in `exclude`."""
    exclude = exclude or set()
    for cluster in load(channel_id).get("clusters") or []:
        if int(cluster.get("count") or 0) < MIN_ASKERS:
            return None
        question = str(cluster.get("question") or "").strip()
        if question and question.lower() not in exclude:
            return cluster
    return None


def mailbag_lines(channel_id: str, data: dict[str, Any] | None = None) -> list[str]:
    data = load(channel_id) if data is None else data
    if not data:
        return [f"Mailbag - {channel_id}: nothing read yet (py -m scripts.ops mailbag reads it)"]
    clusters = data.get("clusters") or []
    lines = [
        f"Mailbag - {channel_id}: {len(clusters)} question(s) from {data.get('comments', 0)} "
        f"comments on {data.get('videos', 0)} video(s)"
    ]
    for c in clusters[:10]:
        videos = len(c.get("videos") or [])
        where = f" ({videos} videos)" if videos > 1 else ""
        lines.append(
            f"  {c['count']} viewer{'s' if c['count'] != 1 else ''}: {c['question']}{where}"
        )
    if clusters and int(clusters[0].get("count") or 0) >= MIN_ASKERS:
        lines.append(f'  asked by {MIN_ASKERS}+ viewers -> offered as a best bet ("viewers asked")')
    return lines
