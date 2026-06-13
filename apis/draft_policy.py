import re
from datetime import datetime

DRAFT_MONTH = 6
DRAFT_DAY = 23


def extract_year(topic):
    match = re.search(r"(19|20)\d{2}", topic)
    if match:
        return int(match.group())
    return None


def determine_draft_status(topic):
    year = extract_year(topic)
    current_date = datetime.now()
    current_year = current_date.year

    if not year:
        year = current_year

    draft_date = datetime(year, DRAFT_MONTH, DRAFT_DAY)

    if year > current_year:
        return "future_projection", year

    if year < current_year:
        return "historical", year

    if current_date < draft_date:
        return "upcoming", year
    else:
        return "completed", year
