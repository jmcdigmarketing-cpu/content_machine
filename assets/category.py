def detect_category(topic: str) -> str:
    topic_lower = topic.lower()

    if any(
        word in topic_lower
        for word in ["nba", "nfl", "mlb", "nhl", "boxing", "ufc", "finals", "super bowl"]
    ):
        return "sports"

    if any(
        word in topic_lower
        for word in ["gaming", "2k", "fortnite", "warzone", "call of duty", "gta"]
    ):
        return "gaming"

    return "general"


def search_query(topic: str, category: str, channel_id=None) -> str:
    """Short stock-video search query (concrete footage, not vague topic paste)."""
    from assets.background_query import resolve_background_query

    return resolve_background_query(topic, category, channel_id)
