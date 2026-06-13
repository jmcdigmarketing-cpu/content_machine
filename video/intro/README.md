# Channel intro clip

Place your vertical (9:16) intro MP4 here. It is prepended to **every** rendered video when enabled.

Default file: `channel_intro.mp4` (copied from your brand intro).

Per-channel override in `config/channels.json`:

```json
"intro_video_file": "video/intro/channel_intro.mp4"
```

Disable globally: `CHANNEL_INTRO_ENABLED=false` in `.env`.

Custom path: `CHANNEL_INTRO_PATH=C:/path/to/intro.mp4`
