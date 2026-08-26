"""Persistent no-console launcher for the localhost review booth."""

import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.review_booth import serve_booth  # noqa: E402


if __name__ == "__main__":
    serve_booth(os.getenv("CONTENT_CHANNEL") or "tapin")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
