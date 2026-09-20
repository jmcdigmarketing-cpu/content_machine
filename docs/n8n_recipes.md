# n8n companion recipes

> **Class:** runbook · **Status:** living · **Reviewed:** 2026-09-20

Practical [n8n](https://n8n.io) automations driven by Content Machine's outbound
webhook ([`core/events.py`](../core/events.py)). Each recipe below names the
event it triggers on, the payload fields it consumes, and its setup steps, and
ships with an importable example workflow under
[`workflows/n8n/`](../workflows/n8n/).

Nothing here changes pipeline behaviour: event delivery is strictly
fire-and-forget (daemon thread, short timeout, never raises), so a dead or slow
n8n instance can never stall a run.

## How the outbound webhook works

Configure in `.env` (see the block near the bottom of
[`.env.example`](../.env.example)):

```dotenv
EVENT_WEBHOOK_URL=http://localhost:5678/webhook/content-machine
EVENT_WEBHOOK_EVENTS=video_published   # optional csv filter; unset = all events
EVENT_WEBHOOK_TIMEOUT=5                # seconds, default 5
```

Every event is POSTed as one JSON envelope:

```json
{
  "event": "<event type>",
  "at": "2026-07-11T14:03:21+00:00",
  "payload": { "...": "event-specific fields, see catalog below" }
}
```

Two things shape every recipe:

- **One URL.** `core/events.py` posts to a single `EVENT_WEBHOOK_URL`. All event
  types arrive at the same endpoint, so an n8n workflow should branch on
  `{{ $json.body.event }}` (an If or Switch node) before acting. Each example
  workflow below already starts with that filter.
- **n8n nests the body.** n8n's Webhook node wraps the request, so the envelope
  lives under `body`: the event type is `{{ $json.body.event }}`, the timestamp
  is `{{ $json.body.at }}`, and fields are `{{ $json.body.payload.<field> }}`.

## Event catalog

Field lists below come straight from the emitters in this repo -- if you touch
an emitter, update this table.

### `run_completed` -- emitted by `core/pipeline.py` after every pipeline run

| Field | Type | Notes |
| --- | --- | --- |
| `channel_id` | string | e.g. `tapin`, `moneywise` |
| `run_id` | int/null | `content_runs` row id for joins |
| `status` | string | `rendered`, `drafted`, or `aborted` |
| `topic` | string | topic the run scripted |
| `title` | string | generated video title |
| `score` | number | topic score at selection time |
| `abort_reason` | string | empty when the run did not abort |

### `video_published` -- emitted by `publishing/youtube_publisher.py` after a successful upload

| Field | Type | Notes |
| --- | --- | --- |
| `platform` | string | `youtube` |
| `video_id` | string | YouTube video id |
| `url` | string | `https://youtu.be/<id>` (empty if no id) |
| `status` | string | `uploaded` (live now) or `scheduled` |
| `channel_id` | string | Content Machine channel id |
| `content_run_id` | int/null | joins back to the pipeline run |
| `title` | string | title as uploaded |
| `scheduled_for` | string | YouTube `publishAt` when scheduled, else empty |

### `batch_completed` -- emitted by `core/batch_generation.py` after `run_batch`

| Field | Type | Notes |
| --- | --- | --- |
| `channel_id` | string | channel the batch drafted for |
| `requested` | int | topics requested |
| `saved` | int | drafts that succeeded |
| `drafts` | array | one object per topic: `{topic, ok, title, path}` |

### `overnight_completed` -- emitted by `core/overnight.py` after the overnight operator

| Field | Type | Notes |
| --- | --- | --- |
| `channel_id` | string | channel drafted overnight |
| `requested` | int | best-bet topics attempted |
| `drafted` | int | drafts that succeeded |
| `dossiers` | int | vault dossiers written |
| `health` | string | one-line channel health summary (may be empty) |

### `analyst_briefing` -- emitted by `core/analyst_agent.py` after the weekly briefing

| Field | Type | Notes |
| --- | --- | --- |
| `channel_id` | string | channel the briefing covers |
| `briefing` | string | full prose briefing text |

## Common setup (once)

1. Run n8n (self-hosted is the natural fit -- `docker run -p 5678:5678
   n8nio/n8n` or `npx n8n`). Note the base URL, e.g. `http://localhost:5678`.
2. Import a recipe: n8n > Workflows > "Import from File" > pick a JSON from
   `workflows/n8n/`.
3. Open the workflow's Webhook node and copy its **production** URL (the
   `/webhook/...` path, not `/webhook-test/...`).
4. Set `EVENT_WEBHOOK_URL` in `.env` to that URL and **activate** the workflow
   (toggle top-right). Only one recipe can own the URL at a time -- to run
   several at once, see "Running more than one recipe" below.
5. Smoke-test without running the pipeline:

   ```powershell
   $body = '{"event":"run_completed","at":"2026-07-11T00:00:00+00:00","payload":{"channel_id":"tapin","run_id":1,"status":"rendered","topic":"test topic","title":"Test Title","score":42,"abort_reason":""}}'
   Invoke-RestMethod -Method Post -ContentType "application/json" -Uri $env:EVENT_WEBHOOK_URL -Body $body
   ```

   or verify the emitter end-to-end from Python:

   ```powershell
   py -c "from core.events import emit_event; emit_event('run_completed', {'channel_id': 'tapin', 'run_id': 1, 'status': 'rendered', 'topic': 't', 'title': 'T', 'score': 42, 'abort_reason': ''}, wait=True)"
   ```

## Recipe 1: cross-post a published video

**File:** [`workflows/n8n/crosspost_video_published.json`](../workflows/n8n/crosspost_video_published.json)

**What it does:** when a video goes live on YouTube, posts the title + short
link to a second platform (X/Mastodon/Telegram/Buffer -- anything with an n8n
node or an HTTP API), so every upload gets a free second surface.

**Triggers on:** `video_published`, only when `payload.status == "uploaded"`.
Scheduled uploads (`status == "scheduled"`) are skipped because the video is not
watchable yet -- if you want to announce scheduled videos too, branch on
`payload.scheduled_for` instead and say "premieres at ...".

**Payload fields consumed:** `status` (gate), `title`, `url`, `channel_id`.

**Flow:** Webhook -> If (`body.event == "video_published"` and
`body.payload.status == "uploaded"`) -> HTTP Request.

**Setup:**

1. Import, point `EVENT_WEBHOOK_URL` at the Webhook node, activate.
2. Replace the placeholder HTTP Request node with your real target:
   - X (Twitter): swap in n8n's **X** node, credential via its OAuth flow, text
     `={{ $json.body.payload.title }} {{ $json.body.payload.url }}`.
   - Telegram channel: swap in the **Telegram** node (sendMessage) with a bot
     token; same expression for the text.
   - Any webhook-based service: keep the HTTP Request node and just change the
     URL/body mapping.
3. Optional: branch per channel on `{{ $json.body.payload.channel_id }}` so
   `tapin` and `moneywise` cross-post to different accounts.

## Recipe 2: Discord digest for batch drafts

**File:** [`workflows/n8n/discord_batch_digest.json`](../workflows/n8n/discord_batch_digest.json)

**What it does:** after a draft batch finishes, posts a one-message digest to a
Discord channel -- saved/requested count plus a per-topic OK/FAIL line -- so you
can review overnight output from your phone.

**Triggers on:** `batch_completed`. The overnight operator calls `run_batch`
internally, so overnight drafting produces this event too; if you also want the
overnight summary line (health, dossier count), duplicate the workflow and key
the copy to `overnight_completed` (`channel_id`, `requested`, `drafted`,
`dossiers`, `health` -- no `drafts` array on that event).

**Payload fields consumed:** `channel_id`, `saved`, `requested`, `drafts[]`
(`topic`, `ok`, `title` per entry).

**Flow:** Webhook -> If (`body.event == "batch_completed"`) -> Code (format the
digest string) -> HTTP Request (Discord webhook).

**Setup:**

1. In Discord: Server Settings > Integrations > Webhooks > New Webhook, pick
   the channel, copy the webhook URL.
2. Import the workflow and paste that URL into the **Post to Discord** node
   (replacing the `.../YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN` placeholder).
3. Point `EVENT_WEBHOOK_URL` at the Webhook node, activate.
4. Digest text lives in the **Format digest** Code node -- edit freely. Keep a
   Discord message under 2000 characters; the node truncates the topic list as
   a guard.

## Recipe 3: Google Sheets run log

**File:** [`workflows/n8n/sheets_run_log.json`](../workflows/n8n/sheets_run_log.json)

**What it does:** appends one row per pipeline run to a Google Sheet --
timestamp, channel, run id, status, topic, title, score, abort reason -- giving
you a zero-maintenance run ledger you can pivot/chart outside the repo.

**Triggers on:** `run_completed` (every run, including aborts -- the
`status`/`abort_reason` columns are the point; filter in the If node if you
only want rendered runs).

**Payload fields consumed:** all of them -- `channel_id`, `run_id`, `status`,
`topic`, `title`, `score`, `abort_reason` -- plus the envelope's `at` timestamp.

**Flow:** Webhook -> If (`body.event == "run_completed"`) -> Google Sheets
(append row).

**Setup:**

1. Create a Google Sheet with a header row:
   `at | channel_id | run_id | status | topic | title | score | abort_reason`.
2. Import the workflow. On the **Append run row** node, attach a Google Sheets
   credential (n8n walks you through the OAuth consent) and point Document/Sheet
   at your spreadsheet (replace the `YOUR_SPREADSHEET_ID` placeholder).
3. Point `EVENT_WEBHOOK_URL` at the Webhook node, activate.
4. No-Google alternative: swap the Sheets node for an **Airtable**, **Baserow**,
   or **Postgres** node -- the column mapping expressions carry over unchanged.

## Running more than one recipe

`EVENT_WEBHOOK_URL` is a single URL, so to run several recipes at once pick one:

- **Router workflow (recommended):** one workflow whose Webhook node owns the
  production URL, followed by a **Switch** node on `{{ $json.body.event }}`
  with one output per event type; wire each output to an **Execute Workflow**
  node that calls the matching recipe (each recipe still works when invoked
  this way -- the If filter simply passes).
- **Merge into one workflow:** import one recipe, then copy the action nodes of
  the others behind additional If branches off the same Webhook node.

Leave `EVENT_WEBHOOK_EVENTS` unset when routing in n8n; use it only when a
single recipe is active and you want the emitter itself to drop everything else
(e.g. `EVENT_WEBHOOK_EVENTS=video_published`).

## Recipe 4: weekly-report cron

**File:** [`workflows/n8n/weekly_report.json`](../workflows/n8n/weekly_report.json)

**What it does:** once a week, runs `py -m scripts.ops weekly-report` on the
operator machine (Execute Command). This is **not** a pipeline stall: Content
Machine events stay fire-and-forget; this recipe is an inbound cron that shells
out to ops.

**Triggers on:** n8n Schedule (Monday 09:00 by default). No webhook required.

**Flow:** Schedule Trigger -> Execute Command (`py -m scripts.ops weekly-report`).

**Setup:**

1. Import the workflow. Set the Execute Command node's working directory to the
   Content Machine repo (or use an absolute `py -m` from a wrapper script).
2. Activate. Adjust the cron if Monday 09:00 is the wrong slot.
3. Optional: swap Execute Command for an HTTP Request to a local helper — still
   do not hook this into `run_pipeline`.

## Notes for maintainers

- The example JSONs are minimal by design: Webhook -> If -> action, no
  credentials embedded. n8n regenerates node ids/webhook ids on import.
- `workflows/*.json` is gitignored (that pattern only matches direct children;
  it exists for large machine-specific ComfyUI graphs). `workflows/n8n/*.json`
  is tracked on purpose -- keep the examples small and credential-free.
- If you add or change an `emit_event(...)` call site, update the event catalog
  above and, if the shape changed, the affected recipe's field mapping.
