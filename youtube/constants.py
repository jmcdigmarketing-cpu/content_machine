SCOPE_YOUTUBE_UPLOAD = "https://www.googleapis.com/auth/youtube.upload"
SCOPE_YT_ANALYTICS_READONLY = "https://www.googleapis.com/auth/yt-analytics.readonly"

# Default OAuth for TapIn / full pipeline (upload + metrics learning)
OAUTH_SCOPES_UPLOAD = [SCOPE_YOUTUBE_UPLOAD]
OAUTH_SCOPES_FULL = [SCOPE_YOUTUBE_UPLOAD, SCOPE_YT_ANALYTICS_READONLY]

# Back-compat alias used by oauth module
SCOPES = OAUTH_SCOPES_FULL

UPLOAD_QUOTA_UNITS = 1600
