# Post scheduling & upload queue

> **Class:** reference · **Status:** living · **Reviewed:** 2026-10-18

## Overview

Content Machine can schedule YouTube publishes at **optimal weekly slots** (per channel and topic domain) without keeping your PC on at publish time.

- **Option 4** uploads the video immediately (run worker once) and sets YouTube **`publishAt`** for the run's own slot (below).

### The slot rule (2026-10-18, #1298)

Option 4, batch-review, `requeue_upload --queue`, the shelf and `auto_generate` all take a video's slot from
`core/spaced_queue` (`slot_for_run`, `shelf_schedule`), one rule for every path:

1. **A game preview** goes before its kickoff - and when no free slot is left before it, out as it uploads
   (`_ASAP_LEAD`, a `publishAt` 45 minutes ahead, so the unlisted review hold does not apply) (#1295).
2. **News** goes inside its window - a 6 PM slot when noon and 10 PM would miss it (#1285).
3. **Everything else** takes the next free noon or 10 PM in the channel's zone, one video a slot; slots other
   uploads already hold are skipped (#1273, #1285).

The Shorts cut from one long video take free noon/10 PM slots, one a day; while a `post_time` experiment
runs, its arm still decides each run's hour (#912). The `post_schedule` below still drives the learned
"best time" display and that experiment.
- **Option 3** only delays the local worker; your machine must be on when the job runs.

## Upload queue (slot reservation)

When you create multiple videos in one session, each **option 4** pick reserves the next **open** optimal slot. Already reserved times come from:

1. **Pending/running upload jobs** with `youtube_publish_at` in the job payload  
2. **`publish_log` rows** with `status=scheduled` and a future `published_at`

The second video is scheduled **after** the first reserved slot (next slot in `channels.json` → `post_schedule`), not the same time.

### CLI visibility

- **Start of each run** (after channel select): **Publish queue** lists upcoming slots.
- **Before upload choices** (after render): queue is shown again; option 4 labels the **next open** slot.

Example:

```
-- Publish queue --
  #   When (local)              Title / job
  1.  Sat 07:00 PM EDT          UFC 250 Predictions  [pending]
  2.  Sun 12:00 PM EDT          Marvel Rivals Meta    [scheduled]

-- Upload --
  4) Schedule on YouTube for Sun 06:00 PM EDT — next open slot
```

## Configuration

Edit `channels.json` → `post_schedule` for TapIn (or other channels):

- `timezone` — e.g. `America/New_York`
- `default_slots` — weekday/hour/minute list (Monday = 0)
- `domain_slots` — overrides for `gaming`, `ufc`, `nba`, etc.

Topic text is mapped to a domain via `infer_domain()` (UFC keywords → `ufc` slots).

## Commands

```powershell
py main.py
py -m jobs.worker
```

## Idempotency & crash safety

Each content run has one `publish_log` row keyed by `run:{channel_id}:{content_run_id}`.

- If upload succeeds but the process dies before the DB updates, the next worker pass **searches your channel uploads by title** and heals the pending row instead of uploading again.
- Run `py -m storage.migrate_schema` on existing Postgres DBs to add the **unique** idempotency index.

## Analytics after publish

Do not expect metrics immediately after upload. Use:

```powershell
py -m analytics.sync_metrics --channel tapin
```

Run that hours or days after publish when YouTube Analytics has data.

## Learned slots

`learn_slots_from_analytics()` derives weekday/hour slots from your own timed publish
outcomes once ≥8 exist (`USE_LEARNED_POST_SLOTS=auto`, default). Slots are ranked by
**average** engaged-rate per bucket — not summed — so whichever day already receives the
most posts can't win on volume alone (a weekend-heavy schedule would otherwise keep
re-learning the weekend). Buckets below `min_bucket_samples` (2) are set aside unless that
would leave nothing. Until 8 timed outcomes accrue, the static `channels.json` schedule
drives the recommendation; the manual time input on upload **Option 3** (a clock time like
`9:30pm` / `tomorrow 6pm`) is always available to override it.

## Future

- Alembic migrations with FK constraints across runs → publish_log → assets  
- Optional minimum gap between publishes (e.g. 24h) via env
