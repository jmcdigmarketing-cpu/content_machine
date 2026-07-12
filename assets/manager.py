import os

from assets.ai_video_provider import AIVideoProvider
from assets.base import AssetProvider
from assets.category import detect_category
from assets.composite import try_compose_hybrid
from assets.local_provider import LocalAssetProvider
from assets.pexels_provider import PexelsAssetProvider
from assets.pixabay_provider import PixabayAssetProvider
from assets.types import AssetResult
from config.settings import get_settings
from core.logging import get_logger

logger = get_logger("assets")

_PROVIDERS = {
    "local": LocalAssetProvider,
    "pexels": PexelsAssetProvider,
    "pixabay": PixabayAssetProvider,
    "ai_video": AIVideoProvider,
}

VALID_BACKGROUND_MODES = ("hybrid", "stock", "local")


def resolve_background_mode(channel_id=None) -> str:
    from config.channels import get_channel_profile, resolve_channel_id

    profile = get_channel_profile(resolve_channel_id(channel_id))
    mode = (profile.background_mode or get_settings().background_mode or "hybrid").lower()
    if mode not in VALID_BACKGROUND_MODES:
        logger.warning("Unknown background_mode=%s — using hybrid", mode)
        return "hybrid"
    return mode


def _provider_chain(channel_id=None, *, include_local: bool = True) -> list[AssetProvider]:
    from config.channels import get_channel_profile, resolve_channel_id

    profile = get_channel_profile(resolve_channel_id(channel_id))
    order = profile.asset_provider_order or get_settings().asset_provider_order
    # AI video-gen (Pillar 6): when AI_VIDEO_PROVIDER is set, prefer generated footage
    # at the front of the chain even if it isn't in ASSET_PROVIDER_ORDER — it fails open
    # to the stock/local providers below when ComfyUI is unreachable. Off by default.
    if "ai_video" not in order and AIVideoProvider().is_configured():
        order = ["ai_video", *order]
    chain = []
    for name in order:
        if name == "local" and not include_local:
            continue
        cls = _PROVIDERS.get(name)
        if not cls:
            continue
        provider = cls()
        if provider.is_configured() or name == "local":
            chain.append(provider)
    if include_local and not any(p.name == "local" for p in chain):
        chain.append(LocalAssetProvider())
    return chain


def _background_search_topic(topic: str, channel_id=None) -> str:
    from apis.topic_fanout import parse_subtopics, primary_search_query
    from assets.background_query import resolve_background_query

    subs = parse_subtopics(topic)
    if subs:
        return primary_search_query(topic)
    category = detect_category(topic)
    return resolve_background_query(topic, category, channel_id)


def _find_from_chain(
    topic: str,
    category: str,
    chain: list[AssetProvider],
    *,
    channel_id=None,
) -> AssetResult | None:
    search_topic = _background_search_topic(topic, channel_id)
    last_error = None
    for provider in chain:
        try:
            result = provider.find_video(topic, category, channel_id=channel_id)
            if result and os.path.isfile(result.path):
                logger.info(
                    "Background from %s (query=%s): %s",
                    provider.name,
                    search_topic,
                    result.path,
                )
                return result
        except Exception as e:
            last_error = e
            logger.warning("%s provider failed: %s", provider.name, e)
    if last_error:
        logger.debug("Chain exhausted: %s", last_error)
    return None


def get_local_background_asset(topic: str, channel_id=None) -> AssetResult | None:
    chain = _provider_chain(channel_id, include_local=True)
    chain = [p for p in chain if p.name == "local"]
    if not chain:
        chain = [LocalAssetProvider()]
    return _find_from_chain(topic, detect_category(topic), chain, channel_id=channel_id)


def get_stock_background_asset(topic: str, channel_id=None) -> AssetResult | None:
    chain = _provider_chain(channel_id, include_local=False)
    return _find_from_chain(topic, detect_category(topic), chain, channel_id=channel_id)


def get_stock_only_background(topic: str, channel_id=None) -> AssetResult:
    asset = get_stock_background_asset(topic, channel_id)
    if asset:
        return asset
    raise Exception("No stock background video found for topic.")


def get_background_asset(
    topic: str,
    channel_id=None,
    *,
    duration: float | None = None,
) -> AssetResult:
    """
    Select background video for render.

    hybrid (default): local gameplay segment + stock B-roll when both exist;
    falls back to stock-only or local-only if one source is missing.
    """
    from config.channels import get_channel_profile, resolve_channel_id

    mode = resolve_background_mode(channel_id)
    profile = get_channel_profile(resolve_channel_id(channel_id))

    if mode == "local":
        asset = get_local_background_asset(topic, channel_id)
        if asset:
            return asset
        raise Exception(
            "No local background in video/backgrounds/. Add gameplay clips or use hybrid/stock mode."
        )

    if mode == "stock":
        return get_stock_only_background(topic, channel_id)

    # hybrid
    local = get_local_background_asset(topic, channel_id)
    stock = get_stock_background_asset(topic, channel_id)

    if duration and duration > 0:
        hybrid = try_compose_hybrid(
            local,
            stock,
            duration,
            local_ratio=profile.hybrid_local_ratio,
        )
        if hybrid:
            return hybrid
        if local and stock:
            logger.warning(
                "Hybrid compose unavailable — falling back to stock B-roll for this render"
            )

    if local and not stock:
        logger.warning("Hybrid mode: no stock clip — using local gameplay only")
        return local
    if stock and not local:
        logger.warning("Hybrid mode: no local clips in video/backgrounds/ — using stock only")
        return stock
    if stock:
        return stock

    raise Exception(
        "No background video found. Add files under video/backgrounds/ or configure stock API keys."
    )


def _scene_matched_enabled() -> bool:
    # Default OFF — a render-path feature; verify it on a real render before relying.
    return os.getenv("SCENE_MATCHED_BROLL", "").lower() in ("1", "true", "yes")


def get_scene_matched_background(
    topic: str,
    script: str,
    channel_id=None,
    *,
    duration: float,
    words: list | None = None,
) -> AssetResult | None:
    """Cut several stock clips, one per script beat, into one background.

    Returns None (so the caller falls back to the normal single/hybrid background)
    when the feature is off, the plan is trivial, any clip is missing, or compose
    fails — i.e. it only ever *upgrades* the background, never breaks the render.
    """
    if not _scene_matched_enabled() or not duration or duration <= 0:
        return None
    try:
        from assets.composite import compose_scene_matched_background
        from video.scene_plan import plan_scenes

        scenes = plan_scenes(script, topic, duration, words=words)
        if len(scenes) < 2:
            return None
        segments: list[tuple[str, float]] = []
        for sc in scenes:
            clip = get_stock_background_asset(sc.query, channel_id)
            if not clip or not getattr(clip, "path", None):
                logger.info("Scene-matched: no clip for '%s' — using normal background", sc.query)
                return None
            segments.append((os.path.abspath(clip.path), sc.end - sc.start))
        return compose_scene_matched_background(segments, duration)
    except Exception as exc:
        logger.warning("Scene-matched background failed; falling back: %s", exc)
        return None
