import requests

from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_OK,
    classify_exception,
    classify_http,
    make_signal,
)


def get_autocomplete_data(topic):
    """
    Uses Google Suggest unofficial endpoint for keyword expansion.
    """

    try:
        url = "https://suggestqueries.google.com/complete/search"
        params = {
            "client": "firefox",
            "q": topic,
        }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            status, detail = classify_http(response.status_code, response.text)
            return make_signal(
                connected=False,
                active=False,
                status=status,
                status_detail=detail,
            )

        suggestions = response.json()[1]

        score = min(len(suggestions) * 10, 100)

        return make_signal(
            connected=True,
            active=len(suggestions) > 0,
            score=score,
            confidence=0.7,
            data=suggestions[:5],
            status=STATUS_OK if suggestions else STATUS_INACTIVE,
        )

    except Exception as e:
        status, detail = classify_exception(e)
        return make_signal(
            connected=False,
            active=False,
            status=status,
            status_detail=detail,
        )
