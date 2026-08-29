"""#147 thin FastAPI operator shell — localhost GET, no spend.

Reuses existing gatherers (reliability, doctor, booth, status, next). Bind
127.0.0.1 only. Default off: run `ops shell`. No POST that calls TTS, Apify,
LLM, or publish.
"""

from __future__ import annotations

from typing import Any

from core.html_report import pre_body, themed_page
from core.logging import get_logger

logger = get_logger("core.operator_shell")

BIND_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def next_sentence(channel_id: str | None = None) -> str:
    """Same ranking as `ops next`: projected-cost, vault decay, then publish blocker."""
    from core.fact_expiry import warning_lines
    from core.publish_blockers import blocking_publish_sentence
    from core.run_mode import projected_cost_block_reason

    cost = projected_cost_block_reason()
    if cost:
        return cost
    vault = warning_lines(channel_id)
    if vault:
        return vault[0]
    return blocking_publish_sentence(channel_id=channel_id)


def reliability_page() -> str:
    from core.reliability import gather, render

    return themed_page("Reliability", pre_body(render(gather())))


def doctor_page(channel_id: str = "tapin") -> str:
    from core.ops_doctor import render

    return themed_page("ops doctor", pre_body(render(channel_id=channel_id)), channel_id=channel_id)


def status_page(channel_id: str = "tapin") -> str:
    from config.channels import resolve_channel_id
    from core.status import build_status_lines

    cid = resolve_channel_id(channel_id)
    lines = [f"Status - {cid}", ""] + [f"  {line}" for line in build_status_lines(cid)]
    return themed_page("Status", pre_body("\n".join(lines) + "\n"), channel_id=cid)


def booth_page(channel_id: str = "tapin") -> str:
    from core.review_booth import booth_html, gather_booth_context

    ctx = gather_booth_context(channel_id)
    ctx.pop("thumbnail_candidates", None)
    ctx.pop("captions_path", None)
    return booth_html(**ctx)


def index_page() -> str:
    links = (
        "<ul>"
        "<li><a href='/booth'>booth</a></li>"
        "<li><a href='/reliability'>reliability</a></li>"
        "<li><a href='/doctor'>doctor</a></li>"
        "<li><a href='/next'>next</a></li>"
        "<li><a href='/status'>status</a></li>"
        "</ul>"
        "<p>Localhost GET only. No TTS, Apify, LLM, or publish.</p>"
    )
    return themed_page("Content OS shell", links, subtitle="127.0.0.1")


def create_app(*, channel_id: str = "tapin") -> Any:
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, PlainTextResponse
    except ImportError as exc:
        raise RuntimeError("FastAPI extra missing; pip install -e '.[shell]'") from exc

    app = FastAPI(title="Content OS operator shell", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return index_page()

    @app.get("/booth", response_class=HTMLResponse)
    def booth() -> str:
        return booth_page(channel_id)

    @app.get("/reliability", response_class=HTMLResponse)
    def reliability() -> str:
        return reliability_page()

    @app.get("/doctor", response_class=HTMLResponse)
    def doctor() -> str:
        return doctor_page(channel_id)

    @app.get("/next", response_class=PlainTextResponse)
    def next_route() -> str:
        return next_sentence(channel_id)

    @app.get("/status", response_class=HTMLResponse)
    def status() -> str:
        return status_page(channel_id)

    return app


def serve(*, port: int = DEFAULT_PORT, channel_id: str = "tapin") -> int:
    try:
        import uvicorn
    except ImportError:
        print("FastAPI extra missing; pip install -e '.[shell]'")
        return 1
    print(f"http://{BIND_HOST}:{int(port)}/")
    uvicorn.run(create_app(channel_id=channel_id), host=BIND_HOST, port=int(port))
    return 0
