# Local gameplay backgrounds

## Foggy / hazy stock B-roll?

Vague topics (e.g. `trendy nba finals video`) used to pull **abstract fog/bokeh** from Pexels. The pipeline now rewrites queries to literal game footage and skips abstract tags. For best results, add real clips below or set `BACKGROUND_MODE=local`. Optional Claude: `ANTHROPIC_API_KEY` + `BACKGROUND_LLM_PROVIDER=anthropic`.

Drop `.mp4` / `.mov` clips here for **hybrid** mode (default on TapIn).

`license.yaml` is JSON-compatible YAML so the runtime can read it without an
extra dependency. The file in this directory covers every local clip below it.
Place another `license.yaml` in a subfolder to override the metadata for that
folder; the nearest file to the selected clip wins. The selected metadata is
persisted as the background asset's attribution.

Suggested layout:

```
video/backgrounds/
  gaming/
    marvel_rivals/
      clip1.mp4
    gta/
      clip1.mp4
  sports/
    ufc/
```

Hybrid render uses ~45% of runtime from a local clip (per channel `hybrid_local_ratio`), then stock B-roll from Pexels/Pixabay for the rest.

Set `BACKGROUND_MODE=stock` in `.env` to use stock only, or `local` for gameplay only.
