import os
import re

import requests

CACHE_DIR = os.path.join("assets", "cache")


def safe_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name)[:80]


def download_file(url: str, dest_path: str, timeout: int = 120) -> str:
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if os.path.isfile(dest_path) and os.path.getsize(dest_path) > 0:
        return dest_path

    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)

    return dest_path
