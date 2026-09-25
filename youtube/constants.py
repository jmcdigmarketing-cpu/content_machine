SCOPE_YOUTUBE_UPLOAD = "https://www.googleapis.com/auth/youtube.upload"
SCOPE_YT_ANALYTICS_READONLY = "https://www.googleapis.com/auth/yt-analytics.readonly"
# Read access to the channel's own videos/playlists — used by the publisher's
# crash-recovery / duplicate-upload check (_find_video_on_channel) and any
# OAuth-based read of the user's uploads.
SCOPE_YOUTUBE_READONLY = "https://www.googleapis.com/auth/youtube.readonly"
# #601: create franchise playlists and add each upload to them. Tokens made before this only
# carry the three scopes below it; they keep working, and playlists wait for one re-consent
# (py -m youtube.oauth_setup --channel tapin).
SCOPE_YOUTUBE_MANAGE = "https://www.googleapis.com/auth/youtube"

# Default OAuth for TapIn / full pipeline (upload + read + metrics learning)
OAUTH_SCOPES_UPLOAD = [SCOPE_YOUTUBE_UPLOAD]
OAUTH_SCOPES_FULL = [
    SCOPE_YOUTUBE_UPLOAD,
    SCOPE_YOUTUBE_READONLY,
    SCOPE_YT_ANALYTICS_READONLY,
    SCOPE_YOUTUBE_MANAGE,
]

# Back-compat alias used by oauth module
SCOPES = OAUTH_SCOPES_FULL

UPLOAD_QUOTA_UNITS = 1600
