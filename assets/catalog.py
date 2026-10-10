import json
import os
import time

CATALOG_FILE = os.path.join("assets", "catalog.json")


def _load():
    if not os.path.exists(CATALOG_FILE):
        return {"entries": []}
    try:
        with open(CATALOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"entries": []}


def _save(data):
    os.makedirs(os.path.dirname(CATALOG_FILE), exist_ok=True)
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def register(path: str, provider: str, source_id: str, query: str, attribution: str = ""):
    data = _load()
    entries = data.setdefault("entries", [])
    for entry in entries:
        if entry.get("path") == path:
            return
    entries.append(
        {
            "path": path,
            "provider": provider,
            "source_id": source_id,
            "query": query,
            "attribution": attribution,
            "added_at": time.time(),
        }
    )
    _save(data)


def cached_paths(query: str, provider: str) -> list[str]:
    """Every on-disk clip registered for this query, oldest first."""
    data = _load()
    q = query.lower().strip()
    found: list[str] = []
    for entry in data.get("entries", []):
        if entry.get("provider") == provider and entry.get("query", "").lower() == q:
            path = entry.get("path")
            if path and os.path.isfile(path) and path not in found:
                found.append(path)
    return found


def stock_cache_hit(query: str, provider: str) -> str | None:
    """The cached stock clip for this query that this video has not already used (#1041)."""
    from assets.clip_memory import choose_stock_path, note_used

    chosen = choose_stock_path(cached_paths(query, provider))
    if chosen:
        note_used(chosen)
    return chosen


def find_cached(query: str, provider: str):
    data = _load()
    q = query.lower().strip()
    for entry in reversed(data.get("entries", [])):
        if entry.get("provider") == provider and entry.get("query", "").lower() == q:
            path = entry.get("path")
            if path and os.path.isfile(path):
                return path
    return None
