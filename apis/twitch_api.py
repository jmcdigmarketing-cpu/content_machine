"""Twitch Helix — live viewership by game (best real-time gaming demand signal)."""

from __future__ import annotations

import os
import re
import time

import requests

from apis.cache_manager import build_key, get_cached, set_cache
from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    classify_exception,
    classify_http,
    make_signal,
)
from core import process_state

_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "").strip()
_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "").strip()
_TTL = 60 * 60
_TOKEN: tuple[str, float] | None = None


def _app_token() -> str | None:
    global _TOKEN
    if not _CLIENT_ID or not _CLIENT_SECRET:
        return None
    if _TOKEN and time.time() < _TOKEN[1]:
        return _TOKEN[0]
    try:
        resp = requests.post(
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
                "grant_type": "client_credentials",
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        token = data.get("access_token")
        expires = int(data.get("expires_in", 3600))
        if token:
            _TOKEN = (token, time.time() + expires - 60)
            return token
    except Exception:
        return None
    return None


def _topic_game_hint(topic: str) -> str:
    text = re.sub(r"\b(game|gaming|meta|tier|list|20\d{2})\b", "", topic, flags=re.I)
    return re.sub(r"\s+", " ", text).strip().lower()


def get_twitch_signal(topic: str) -> dict:
    if not _CLIENT_ID or not _CLIENT_SECRET:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set TWITCH_CLIENT_ID + TWITCH_CLIENT_SECRET",
        )

    cache_key = build_key("twitch", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    token = _app_token()
    if not token:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Twitch OAuth token failed",
        )

    headers = {
        "Client-ID": _CLIENT_ID,
        "Authorization": f"Bearer {token}",
    }
    hint = _topic_game_hint(topic)

    try:
        top = requests.get(
            "https://api.twitch.tv/helix/games/top",
            params={"first": 25},
            headers=headers,
            timeout=12,
        )
        if top.status_code != 200:
            status, detail = classify_http(top.status_code, top.text)
            return make_signal(connected=False, active=False, status=status, status_detail=detail)

        games = top.json().get("data") or []
        matched = []
        for g in games:
            name = (g.get("name") or "").lower()
            if hint and (
                hint in name or name in hint or any(w in name for w in hint.split() if len(w) > 3)
            ):
                matched.append(g)

        streams_resp = requests.get(
            "https://api.twitch.tv/helix/streams",
            params={"first": 20, "game_id": matched[0]["id"]} if matched else {"first": 20},
            headers=headers,
            timeout=12,
        )
        viewers = 0
        if streams_resp.status_code == 200:
            for s in streams_resp.json().get("data") or []:
                viewers += int(s.get("viewer_count") or 0)

        if not matched and not viewers:
            sig = make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail="Twitch: no game/viewership match",
            )
            set_cache(cache_key, sig, ttl_seconds=_TTL)
            return sig

        score = min(45 + (viewers // 5000) + len(matched) * 8, 98)
        sig = make_signal(
            connected=True,
            active=True,
            score=float(score),
            confidence=0.9,
            status=STATUS_OK,
            status_detail=f"Twitch: {viewers:,} viewers"
            + (f" ({matched[0].get('name')})" if matched else ""),
            data={"games": matched[:3] or games[:5], "viewers": viewers},
        )
        set_cache(cache_key, sig, ttl_seconds=_TTL)
        return sig
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)


# --- process-global state reset (#827) --------------------------------------
def _reset_process_state() -> None:
    global _TOKEN
    _TOKEN = None


process_state.register_reset("apis.twitch_api", _reset_process_state)
