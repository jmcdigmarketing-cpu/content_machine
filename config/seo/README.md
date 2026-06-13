# Channel SEO profiles

One JSON file per channel: `{channel_id}.json` (e.g. `tapin.json`).

Used for:

- YouTube **title / description / tags** rules in the LLM prompt
- **Default tags** merged into every upload
- **RSS feed URLs** for the research brief (Phase H)
- **seo_refresh_queries** for periodic tag hint updates

Refresh trending tags (weekly recommended):

```powershell
py -m analytics.seo_refresh --channel tapin
# or
py -m scripts.ops seo-refresh --channel tapin
```

Hints are written to `data/seo_hints_{channel_id}.json` and picked up on the next content run.
