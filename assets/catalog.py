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


def find_cached(query: str, provider: str):
    data = _load()
    q = query.lower().strip()
    for entry in reversed(data.get("entries", [])):
        if entry.get("provider") == provider and entry.get("query", "").lower() == q:
            path = entry.get("path")
            if path and os.path.isfile(path):
                return path
    return None
