"""
Import existing JSON memory files into PostgreSQL (one-time).

    py -m storage.migrate_json
"""

import os

from config.paths import CHANNEL_MEMORY_FILE, PERFORMANCE_MEMORY_FILE, ROOT_DIR
from storage.db import check_database_connection, is_database_configured
from storage.repositories.channel_memory import (
    JsonChannelMemoryRepository,
    PostgresChannelMemoryRepository,
)
from storage.repositories.performance_memory import (
    JsonPerformanceMemoryRepository,
    PostgresPerformanceMemoryRepository,
)


def main():
    if not is_database_configured():
        print("DATABASE_URL is not set.")
        return 1

    ok, detail = check_database_connection()
    if not ok:
        print(f"Connection failed: {detail}")
        return 1

    json_ch = JsonChannelMemoryRepository()
    pg_ch = PostgresChannelMemoryRepository()
    data = json_ch.load_all()
    count = 0
    for topic, scores in data.items():
        for score in scores:
            pg_ch.add_score(topic, score)
            count += 1
    print(f"Migrated {count} topic scores from {CHANNEL_MEMORY_FILE}")

    perf_path = PERFORMANCE_MEMORY_FILE
    if not os.path.exists(perf_path):
        perf_path = os.path.join(ROOT_DIR, "performance_memory.json")
    if os.path.exists(perf_path):
        json_perf = JsonPerformanceMemoryRepository()
        pg_perf = PostgresPerformanceMemoryRepository()
        entries = json_perf.load_all()
        for entry in entries:
            pg_perf.log_performance(entry)
        print(f"Migrated {len(entries)} performance entries from {perf_path}")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
