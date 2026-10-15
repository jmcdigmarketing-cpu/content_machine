# Initiative — one video, three feeds (cross-platform learning)

> **Class:** plan · **Status:** living · **Reviewed:** 2026-10-14

The operator, 2026-10-14, after TikTok and Instagram posting shipped (wave 89): *"create a big
initiative for cursor to lead"*. Offered four, they chose this one. **Cursor leads it**; it is
offered, not assigned - the operator says when, relative to Phase A of
[cursor_brief_2026-10.md](cursor_brief_2026-10.md). Every step is a numbered item in
[backlog.md](backlog.md) (#1194-#1199); the backlog line is the spec, this page is the order,
the files and the definition of done.

## Why

Since wave 89 a video public on YouTube is scheduled on TikTok and Instagram through Buffer
(decisions_2026-10.md §54). Nothing reads their results back. Every recommender - the best-bet
domain weights, the length, the post time, the hook learning - still learns from YouTube
alone, where the channel has 69 subscribers and a median of 83 first-week views. TikTok and
Instagram may like different topics, lengths, hours and first lines; today nobody would know.

## What there is to build on

- **The sent posts.** `data/crosspost_<channel>.json` `posts[run_id][tiktok|instagram]`:
  `state` (scheduled / sent / error / skipped / cancelled), `post_id`, `due_at`, `sent_at`,
  `link`. Written by `publishing/crosspost.send_due` and `sync_status` (wave 89).
- **Buffer's API** through `publishing/buffer_api.py` - the only client; add a call there, never a
  second one. `Post.metrics` is a list of `{name, type, unit, value}` (count or percentage; 0
  when the network does not report it), refreshed by Buffer about daily (`metricsUpdatedAt`).
  `aggregatedPostMetrics` sums a period. Free plan: 100 requests / 15 min, 250 / day, shared
  with the posting round - read metrics in one `posts` query per channel, not one per post.
- **YouTube's side**: `storage/repositories/performance_memory.py`, `analytics/post_timing.py`
  (slots), `analytics/hook_learning.py` (`rank_openers`, learned trait gaps), `core/best_bet.py`
  (domain weights), `core/experiments.py` / `core/experiment_stats.py` (the experiment ledger,
  #919), `analytics/weekly_report.py`, `analytics/growth.py`. Shrinkage and confidence tags
  (#352, `core/recommender_confidence.py`) are how a thin sample is shown.

## The steps, in order

1. **#1195 `[M]` read the metrics back.** Each sent post's metrics, once a day, into a
   per-platform store beside `performance_memory` keyed by (run, platform); the metric names
   kept as Buffer gives them, views/likes/comments/shares/saves mapped to one shape. Done when
   `ops crosspost status` shows views per platform and a test replays a recorded `posts`
   response (no network).
2. **#1196 `[M]` per-platform recommenders.** Domain weights, length and post time learned per
   feed with the existing shrinkage; under the confidence floor a platform falls back to
   YouTube's. `send_due`'s slot comes from the platform's own times once they are confident.
   Done when the recommenders name the platform they learned from and the fallback is tested.
3. **#1197 `[M]` captions and first lines per platform.** TikTok shows the first line over the
   video; Instagram's caption is read. A variant per platform from the same facts (never a new
   claim), A/B'd through the experiment ledger. Done when the ledger reports a winner per
   platform with its interval.
4. **#1198 `[S]` "which feed liked what".** A section of `ops weekly-report` and a row of
   `ops growth`: views per platform, the best video on each, what each feed preferred.
5. **#1199 `[S]` platform health on the morning screen.** A post Buffer reports `error`, a
   paused queue, a disconnected channel, a request budget near its limit.

## Rules

The project rules are in [CLAUDE.md](../CLAUDE.md) and the mailbox is
[handoff.md](handoff.md) - read both slots first, write yours last. Tests first and watched
failing on unmodified code; no network in tests; never write the real `data/` stores from a
test (patch `publishing.crosspost.CROSSPOST_TEMPLATE`); the suite pins `CROSSPOST_AUTO=false`.
Done means `ruff check .`, `ruff format --check .`, `python scripts/mypy_ratchet.py` (98 or
fewer), the suite forward and `py -m scripts.ops test --order reverse`. A defect a live run
exposes gets a case in `tests/regression_corpus.json`. Every new function has a production
caller. Never commit `.env`.

## The prompt to paste into Cursor

```text
You are the Cursor agent on content_machine (C:\dev\content_machine); Claude Code works here too.
1. git pull. Read docs/handoff.md first, both slots; check the Claude slot's HEAD with
   `git log <sha>..HEAD --oneline` and `git status --short`.
2. Read docs/initiative_cross_platform.md in full - it is this initiative's order, files and
   definition of done; each step's spec is its line in docs/backlog.md (#1194-#1199).
3. Do the steps in order, one commit each: #1195 metrics back from Buffer, #1196 per-platform
   recommenders, #1197 captions and first lines per platform, #1198 the weekly section, #1199
   platform health. Buffer calls go through publishing/buffer_api.py only.
4. Tests first: watch each new test fail on unmodified code and say how many did in the commit.
   No network in tests. Done means ruff, ruff format --check, scripts/mypy_ratchet.py, the
   suite forward and `py -m scripts.ops test --order reverse`.
5. Write your handoff slot as your last edit of each session, and sign commits with your trailer.
```
