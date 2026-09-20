# Platform publishing setup

> **Class:** runbook · **Status:** living · **Reviewed:** 2026-09-20

## Current scope (this phase)

| Platform | Status |
|----------|--------|
| **YouTube** | Supported — `publishing.YouTubePublisher` + worker `upload` jobs |
| **TikTok** | **Deferred** — no publisher registered yet |
| **Instagram** | **Deferred** — no publisher registered yet |
| **Facebook** | Not planned |

Videos include your channel intro first (`video/intro/channel_intro.mp4`). See `video/intro/README.md`.

**Repurpose orchestration:** after render, the CLI calls `publishing.repurpose.enqueue_repurpose_jobs()` which formats metadata and enqueues one YouTube `upload` job per enabled platform in `publishers_enabled` (TikTok/Instagram names are logged as skipped until a far-future phase).

**Thumbnail scoring:** optional after thumbnail generation when `THUMBNAIL_SCORER_ENABLED=true` (vision via `OPENAI_API_KEY`, else heuristic). Scores persist in `thumbnail_scores` (Alembic `0002`).

## YouTube (use this now)

1. `YOUTUBE_UPLOAD_ENABLED=true` in `.env`
2. Google Cloud OAuth client → `config/secrets/client_secrets.json`
3. `py -m youtube.oauth_setup --channel tapin`
4. `py -m youtube.check_setup --channel tapin`
5. Worker: `py -m jobs.worker --loop 30`

Keys: [Google Cloud Console](https://console.cloud.google.com/) → Credentials → OAuth client + enable YouTube Data API v3 / YouTube Analytics API.

## TikTok & Instagram (later phase)

When you are ready, credential sources are documented below. **Do not add these to `.env` until that phase ships.**

### TikTok (future)

- Portal: [developers.tiktok.com](https://developers.tiktok.com/) → app → **Content Posting API**
- `TIKTOK_CLIENT_KEY` / `TIKTOK_CLIENT_SECRET` from the app dashboard
- `TIKTOK_OAUTH_TOKEN_FILE` after one-time OAuth

### Instagram Reels (future)

- Portal: [developers.facebook.com](https://developers.facebook.com/) → app → **Instagram Graph API** (Meta developer app only — not Facebook Page posting)
- `META_APP_ID` / `META_APP_SECRET` from app Settings → Basic
- `INSTAGRAM_ACCOUNT_ID` — Instagram professional account ID via Graph API
- `INSTAGRAM_OAUTH_TOKEN_FILE` after OAuth with `instagram_content_publish`

### Shared (future)

```env
AI_CONTENT_DISCLOSURE_LABEL=Created with AI assistance
```
