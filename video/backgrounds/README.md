# Local gameplay backgrounds

## Foggy / hazy stock B-roll?

Vague topics (e.g. `trendy nba finals video`) used to pull **abstract fog/bokeh** from Pexels. The pipeline now rewrites queries to literal game footage and skips abstract tags. For best results, add real clips below or set `BACKGROUND_MODE=local`. Optional Claude: `ANTHROPIC_API_KEY` + `BACKGROUND_LLM_PROVIDER=anthropic`.

Drop `.mp4` / `.mov` clips here for **hybrid** mode (default on TapIn).

`license.yaml` is JSON-compatible YAML so the runtime can read it without an
extra dependency. The file in this directory covers every local clip below it.
Place another `license.yaml` in a subfolder to override the metadata for that
folder; the nearest file to the selected clip wins. The selected metadata is
persisted as the background asset's attribution.

Suggested layout (this tree already has clips under the nested game folders):

```
video/backgrounds/
  gaming/
    multiplayer games/
      Fortnite/
      Marvel Rivals/
    open world/
      GTA V/
    sports/
      UFC 5/
```

Mute source audio **before** dropping clips here (NVIDIA ShadowPlay / Instant Replay
keeps game + Discord). Remux is enough when the file is already H.264:

`ffmpeg -y -i input.mp4 -map 0:v:0 -c:v copy -an -movflags +faststart output.mp4`

HEVC `.mov` can fail hybrid compose and fall back to stock — convert those to
H.264 `.mp4`. Folder names are matched against the original topic (`fortnite`
in the topic picks `gaming/multiplayer games/Fortnite`). A GTA topic still
needs a `GTA V` (or similarly named) folder; otherwise it can draw a
non-matching game.

Hybrid render uses ~45% of runtime from a local clip (per channel `hybrid_local_ratio`), then stock B-roll from Pexels/Pixabay/Coverr for the rest, **hard-cut with no fade**. That join is the operator's 2026-08-26 complaint: live-action stock is often unrelated, and gameplay → reality with no transition is disorienting ([decisions.md](../../docs/decisions.md) §26). Do not add more stock sources to "fix" it. Prefer more clips in this folder, or `background_mode: local`.

Set `BACKGROUND_MODE=stock` in `.env` to use stock only, or `local` for gameplay only. `SCENE_MATCHED_BROLL` concatenates extra stock per script beat — do not enable it for TapIn.
