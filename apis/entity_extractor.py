import re


def extract_entities(topic):
    entities = {"year": None, "team": None, "league": None, "game_title": None}

    year_match = re.search(r"(19|20)\d{2}", topic)
    if year_match:
        entities["year"] = year_match.group()

    leagues = ["nba", "nfl", "mlb", "nhl"]
    for league in leagues:
        if league in topic.lower():
            entities["league"] = league.upper()

    # Basic team detection heuristic (expandable later)
    words = topic.split()
    if len(words) >= 2:
        entities["team"] = " ".join(words[:2])

    return entities
