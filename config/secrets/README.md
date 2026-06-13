# Local secrets (gitignored)

Place OAuth and API credential files here — never commit them.

| File | Purpose |
|------|---------|
| `client_secrets.json` | Google OAuth client (YouTube upload + analytics) |
| `youtube_token.json` | Default channel OAuth token (after `py -m youtube.oauth_setup`) |
| `youtube_token_tapin.json` | TapIn channel token (path set in `config/channels.json`) |
Override paths via `.env`:

- `YOUTUBE_OAUTH_CLIENT_SECRETS`
- `YOUTUBE_OAUTH_TOKEN_FILE`
