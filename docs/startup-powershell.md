# Content OS — Windows PowerShell startup commands

Run everything from the project root:

```powershell
cd C:\Users\jonma\OneDrive\Desktop\content_machine
```

Optional (recommended each new terminal):

```powershell
.\.venv\Scripts\Activate.ps1
```

If activation is blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (once), then retry.

---

## One-time (new machine or after `git pull` with schema changes)

```powershell
pip install -r requirements.txt
copy .env.example .env
# Edit .env — DATABASE_URL, OPENAI_API_KEY, ELEVEN_API_KEY, YOUTUBE_UPLOAD_ENABLED=true, etc.
# OAuth: config/secrets/client_secrets.json + py -m youtube.oauth_setup --channel tapin

py -m scripts.ops all-setup --channel tapin
alembic upgrade head
```

`all-setup` runs: migrate-layout → init-db → migrate-schema → seed → validate → check-youtube.

---

## Every session (normal workflow)

**Terminal 1 — create content (interactive)**

```powershell
cd C:\Users\jonma\OneDrive\Desktop\content_machine
.\.venv\Scripts\Activate.ps1
py main.py
```

In the CLI: channel **TapIn (2)** → **Create new video (1)** → topic → variants → length → **y** to render → queue upload when prompted.

**Terminal 2 — process upload/render jobs (leave running)**

```powershell
cd C:\Users\jonma\OneDrive\Desktop\content_machine
.\.venv\Scripts\Activate.ps1
py -m jobs.worker --loop 30
```

Or via ops:

```powershell
py -m scripts.ops worker --loop 30
```

Upload jobs must reach the worker **before** the scheduled YouTube `publishAt` time (worker uploads soon; YouTube publishes at the slot).

---

## Quick checks (any time)

```powershell
py -m scripts.ops status --channel tapin
py -m youtube.check_setup --channel tapin
py -m scripts.ops list
```

---

## After a crash during render (e.g. FFmpeg died mid-run)

1. **See what finished**

```powershell
py -m scripts.ops status --channel tapin
py -m scripts.requeue_upload --channel tapin
```

2. **If MP4 exists for the run** (run id shown in CLI, e.g. 13) — queue upload only:

```powershell
py -m scripts.requeue_upload --channel tapin --run-id 13 --queue
py -m jobs.worker
```

3. **If only MP3 exists / render incomplete** — safest path is run `py main.py` again with the same topic (new run), or delete the partial file under `output\tapin\video\` and re-render from the interactive flow.

4. **Stuck pending job** (worker not running):

```powershell
py -m jobs.worker --loop 30
```

---

## Optional / periodic

```powershell
# Once per day (competitor + SEO hints)
py -m scripts.ops daily-sync --channel tapin

# After videos have views on YouTube
py -m analytics.sync_metrics --channel tapin

# Re-queue after you deleted a scheduled video on YouTube
py main.py
# → Queue manager (2)
# or:
py -m scripts.queue_manage --channel tapin

# Standalone topic score (no full pipeline)
py -m core.opportunity --topic "Your topic" --channel tapin --json

# Unit tests
py -m scripts.ops test
```

---

## Optional features (.env)

```env
CHANNEL_INTRO_ENABLED=true
THUMBNAIL_SCORER_ENABLED=false
REPURPOSE_PUBLISH_ENABLED=true
YOUTUBE_UPLOAD_ENABLED=true
CONTENT_CHANNEL_ID=tapin
```

## FFmpeg render stuck (no % for many minutes)

1. **Stop the run:** `Ctrl+C` in the `py main.py` window.
2. **Retry with simple FFmpeg** (no progress pipe — avoids a Windows deadlock):

```powershell
$env:FFMPEG_SIMPLE_RUN="true"
py main.py
```

3. **Or disable channel intro** (second encode pass):

```powershell
$env:CHANNEL_INTRO_ENABLED="false"
py main.py
```

4. Check Task Manager — end any orphan `ffmpeg.exe` before restarting.

Expected time for a ~2 minute video: about **2–6 minutes** encode, not 40+.

---

## Prerequisites on PATH

- **FFmpeg** and **ffprobe** (render + channel intro concat)
- **PostgreSQL** running if `DATABASE_URL` is set in `.env`

Verify FFmpeg:

```powershell
ffmpeg -version
ffprobe -version
```
