# Platform publishing setup

> **Class:** runbook · **Status:** living · **Reviewed:** 2026-10-05

## Current scope (this phase)

| Platform | Status |
|----------|--------|
| **YouTube** | Supported — `publishing.YouTubePublisher` + worker `upload` jobs |
| **TikTok** | **Through Buffer (Phase M, #968)** — the operator schedules the pack Content OS makes; no TikTok app (its review refuses personal apps - caveat below) |
| **Instagram** | **Through Buffer (Phase M, #968)** — same pack; Instagram must be a Professional (Creator or Business) account for Buffer to post Reels. A direct Graph API publisher (#952) stays parked as an option |
| **Facebook** | Not planned |

Videos include your channel intro first (`video/intro/channel_intro.mp4`). See `video/intro/README.md`.

**Repurpose orchestration:** after render, the CLI calls `publishing.repurpose.enqueue_repurpose_jobs()` which formats metadata and enqueues one YouTube `upload` job per enabled platform in `publishers_enabled` (TikTok/Instagram names are logged as skipped: those go out through Buffer, #968).

**Thumbnail scoring:** optional after thumbnail generation when `THUMBNAIL_SCORER_ENABLED=true` — vision goes through the LLM router (`core.llm_router.complete` with image parts, whichever premium-tier provider is live), else the heuristic scorer. Scores persist in `thumbnail_scores` (Alembic `0002`).

## YouTube (use this now)

1. `YOUTUBE_UPLOAD_ENABLED=true` in `.env`
2. Google Cloud OAuth client → `config/secrets/client_secrets.json`
3. `py -m youtube.oauth_setup --channel tapin`
4. `py -m youtube.check_setup --channel tapin`
5. Worker: `py -m jobs.worker --loop 30`

Keys: [Google Cloud Console](https://console.cloud.google.com/) → Credentials → OAuth client + enable YouTube Data API v3 / YouTube Analytics API / YouTube Reporting API (thumbnail impressions and click-through, #951; same sign-in).

**"YouTube sign-in ... has expired or been revoked" (#961).** Google refused the saved token
(`invalid_grant`). Run `py -m youtube.oauth_setup --channel tapin` and repeat the command that
stopped. If it happens again about a week later, the OAuth consent screen (Google Auth Platform ->
Audience) is in **Testing**, where Google ends every sign-in after 7 days: press **Publish app**
and give the policy site's home page and privacy links (below). Google lets an unverified app
serve a handful of users; the sign-in then shows a "Google hasn't verified this app" warning,
which you pass once via Advanced.

## The policy site (#956)

TikTok, Instagram (Meta) and Google's OAuth consent screen each ask for a privacy policy URL.
TikTok also asks for terms of service, linked from the website itself rather than behind a
menu, on a site that describes the app; Meta asks for data-deletion instructions. One static
site serves all of them - separate sites are not needed.

1. **Build it:** `py -m scripts.ops policy-site --name "<name to show>" --email "<contact>"
   --output-dir C:\dev\policy_site`. The name and address go only into the built pages, never
   into this repo; use an address you are happy to publish.
2. **Host it free** - plain pages, no credentials, no connection to the PC:
   - GitHub Pages serves a free account's Pages only from a public repository, so make a
     separate small public repo (e.g. `contentos-site`), upload the four files, then Settings ->
     Pages -> deploy from the main branch. content_machine stays private.
   - Or Cloudflare Pages / Netlify: upload the folder.
3. **Give each app the addresses** (`.../index.html`, `privacy.html`, `terms.html`,
   `data-deletion.html`):
   - TikTok: developer portal -> the app -> URL properties -> verify by **URL prefix**: download
     TikTok's signature file and upload it next to the pages. Verifying by domain needs a DNS
     record, which a free `github.io` address cannot have; a custom domain is optional.
   - Meta: App settings -> Basic -> Privacy Policy URL, and User data deletion -> the
     data-deletion page as the instructions URL.
   - Google: OAuth consent screen -> App home page and Privacy policy link.
4. When the app starts reading or sending something new, rebuild and re-upload; the pages
   carry their effective date. The privacy page says what reaches an AI provider (viewers'
   comment questions, the channel's own titles and view counts - `core/signal_facts`,
   `core/success/winners.winners_block`); keep it true when that changes.

**TikTok caveat (2026-10-04).** TikTok's
[app review guidelines](https://developers.tiktok.com/doc/app-review-guidelines) say apps "must
not be for private or personal use", and an
[unaudited app](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post) can
post only private (`SELF_ONLY`) videos, to accounts set to private, for at most 5 users in 24
hours. A personal Content OS app is unlikely to pass review, so the site alone does not open
TikTok publishing: TikTok Studio's own scheduler or an already-audited posting service are the
realistic routes (#952). Instagram differs: an app used only by people with a role on it runs on
Standard Access, without App Review or Business Verification
([Instagram content publishing](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/content-publishing)).

## TikTok & Instagram through Buffer (operator, 2026-10-05)

Buffer schedules TikToks and Instagram Reels and posts them with the PC off, so no developer app,
token or policy page is needed for either. Once #968 ships, the crosspost verb writes a
folder per rendered video (mp4, `tiktok.txt`, `instagram.txt`, `slot.txt`); upload it in Buffer
for each channel at the suggested slot, then mark it posted with the verb's done flag. Turn on
each platform's own AI-generated label in Buffer's composer where offered - the caption carries
the disclosure line either way. The direct-API notes below are kept for the parked #952.

## TikTok & Instagram direct APIs (parked, #952)

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
