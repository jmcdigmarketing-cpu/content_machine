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
                    "comment_id": str(c.get("comment_id") or ""),
                }
            )
    return out


def _comment(q: dict[str, Any]) -> dict[str, str]:
    return {
        "video_id": str(q.get("video_id") or ""),
        "comment_id": str(q.get("comment_id") or ""),
        "text": str(q.get("text") or ""),
    }


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
                if len(cluster["comments"]) < 10:
                    cluster["comments"].append(_comment(q))
                break
        else:
            clusters.append(
                {
                    "question": q["text"],
                    "count": 1,
                    "videos": [q["video_id"]] if q["video_id"] else [],
                    "examples": [q["text"]],
                    "comments": [_comment(q)],
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


def _key(question: str) -> str:
    from core.channel_context import normalize_seed_topic

    return normalize_seed_topic(str(question or "")).strip().lower()


def answered(channel_id: str) -> dict[str, dict[str, Any]]:
    """{question key: {run_id, video_id}} - stored questions a run has answered (#942).

    A run answers a question when its topic is the question, or when the best-bet pick it
    was made from was that "viewers asked" option. `video_id` is None until it is live.
    """
    keys = {_key(c.get("question") or "") for c in load(channel_id).get("clusters") or []}
    keys.discard("")
    if not keys:
        return {}
    try:
        from storage.repositories.content_runs import get_content_run_repository
        from storage.repositories.publish_log import get_publish_log_repository

        runs = get_content_run_repository().list_for_channel(channel_id)
        logs = get_publish_log_repository().list_timed_outcomes(channel_id)
    except Exception as exc:
        logger.debug("answered questions unavailable: %s", exc)
        return {}
    video_by_run = {
        log.content_run_id: log.youtube_video_id for log in logs if log.youtube_video_id
    }
    out: dict[str, dict[str, Any]] = {}
    for run in runs:
        asked = {_key(getattr(run, "input_topic", "")), _key(getattr(run, "selected_topic", ""))}
        try:
            features = json.loads(getattr(run, "features_json", None) or "{}")
        except (TypeError, ValueError):
            features = {}
        pick = features.get("best_bet") if isinstance(features, dict) else None
        if isinstance(pick, dict):
            offered = pick.get("offered") or []
            rank = pick.get("picked")
            if isinstance(rank, int) and 1 <= rank <= len(offered):
                chosen = offered[rank - 1] or {}
                if chosen.get("source") == "mailbag":
                    asked.add(_key(chosen.get("topic") or ""))
        for key in asked & keys:
            entry = {"run_id": int(run.id), "video_id": video_by_run.get(run.id)}
            if key not in out or (out[key]["video_id"] is None and entry["video_id"]):
                out[key] = entry
    return out


def top_question(channel_id: str, *, exclude: set[str] | None = None) -> dict[str, Any] | None:
    """The most-asked stored question `MIN_ASKERS`+ viewers asked that no run has answered
    and that is not in `exclude` (topics compared the way best bet stores them)."""
    skip = {_key(t) for t in exclude or set()} | set(answered(channel_id))
    for cluster in load(channel_id).get("clusters") or []:
        if int(cluster.get("count") or 0) < MIN_ASKERS:
            return None
        question = str(cluster.get("question") or "").strip()
        if question and _key(question) not in skip:
            return cluster
    return None


def reply_drafts(channel_id: str, data: dict[str, Any] | None = None) -> list[str]:
    """Ready-to-paste replies for answered questions; nothing is posted (operator)."""
    data = load(channel_id) if data is None else data
    done = answered(channel_id)
    lines: list[str] = []
    for cluster in data.get("clusters") or []:
        entry = done.get(_key(cluster.get("question") or ""))
        if entry is None:
            continue
        lines.append(f'  "{cluster["question"]}" - answered by run {entry["run_id"]}')
        if not entry["video_id"]:
            lines.append("    reply drafts once its video is live")
            continue
        reply = f"Answered this one here: https://youtu.be/{entry['video_id']}"
        for comment in (cluster.get("comments") or [])[:5]:
            if comment.get("video_id") and comment.get("comment_id"):
                link = (
                    f"https://www.youtube.com/watch?v={comment['video_id']}"
                    f"&lc={comment['comment_id']}"
                )
                lines.append(f'    reply on {link}: "{reply}"')
    return lines


def mailbag_lines(channel_id: str, data: dict[str, Any] | None = None) -> list[str]:
    data = load(channel_id) if data is None else data
    if not data:
        return [f"Mailbag - {channel_id}: nothing read yet (py -m scripts.ops mailbag reads it)"]
    clusters = data.get("clusters") or []
    done = answered(channel_id)
    lines = [
        f"Mailbag - {channel_id}: {len(clusters)} question(s) from {data.get('comments', 0)} "
        f"comments on {data.get('videos', 0)} video(s)"
    ]
    for c in clusters[:10]:
        videos = len(c.get("videos") or [])
        where = f" ({videos} videos)" if videos > 1 else ""
        mark = " (answered)" if _key(c.get("question") or "") in done else ""
        lines.append(
            f"  {c['count']} viewer{'s' if c['count'] != 1 else ''}: {c['question']}{where}{mark}"
        )
    if top_question(channel_id) is not None:
        lines.append(f'  asked by {MIN_ASKERS}+ viewers -> offered as a best bet ("viewers asked")')
    drafts = reply_drafts(channel_id, data)
    if drafts:
        lines.append("  Answered - reply drafts (you post them):")
        lines.extend(drafts)
    return lines
