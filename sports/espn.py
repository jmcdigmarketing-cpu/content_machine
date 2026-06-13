import requests

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"


def get_scoreboard():
    url = f"{BASE_URL}/scoreboard"
    response = requests.get(url, timeout=10)

    if response.status_code != 200:
        raise Exception("ESPN scoreboard fetch failed")

    return response.json()
