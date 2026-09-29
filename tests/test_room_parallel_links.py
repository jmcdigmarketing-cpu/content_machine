"""#910: the facts room reads every pasted link at once.

`core/link_facts` kept the page title, publish date and line counts in one module-level
`_last_extract_report`, so two pages read at the same time would have swapped titles.
The room (#860) therefore read links one after another. `extract_facts_with_report`
returns each page's report with its lines; the room reads links concurrently under
`FACTS_ROOM_DEADLINE_S`, keeps paste order, and names a link that ran out of time. The
terminal prompt's `last_extract_report` behaves exactly as before.
"""

from __future__ import annotations

import os
import threading
import time
import unittest
from typing import ClassVar
from unittest.mock import patch

URLS = [f"https://example.com/story-{i}" for i in range(3)]


def _slow_reader(delay=0.3):
    def read(url):
        time.sleep(delay)
        n = url.rsplit("-", 1)[1]
        return [f"Line from story {n} about Topuria and Holloway."], {"title": f"Page {n}"}

    return read


def _gather(read, **kw):
    from core.facts.room import gather

    return gather(
        "Topuria Holloway", "tapin", pasted_lines=list(URLS), read_url=read,
        flag_off_topic=lambda lines, **_k: [], load_vault=lambda corpus: [], **kw,
    )  # fmt: skip


class ParallelTests(unittest.TestCase):
    def test_links_are_read_at_the_same_time(self):
        started = time.monotonic()
        rows = _gather(_slow_reader(0.3))
        elapsed = time.monotonic() - started
        self.assertEqual(len(rows), 3)
        self.assertLess(elapsed, 0.75, f"3 x 0.3 s read one after another took {elapsed:.2f}s")

    def test_each_line_keeps_its_own_page(self):
        rows = _gather(_slow_reader(0.05))
        for row in rows:
            n = row.url.rsplit("-", 1)[1]
            self.assertEqual(row.source, f"Page {n}")
            self.assertIn(f"story {n}", row.line)

    def test_paste_order_survives(self):
        def uneven(url):
            n = int(url.rsplit("-", 1)[1])
            time.sleep(0.2 - n * 0.08)  # the last link finishes first
            return [f"Topuria Holloway line {n}."], {"title": f"Page {n}"}

        from core.facts.room import kept

        rows = _gather(uneven)
        links = kept(rows, [r.id for r in rows]).link
        self.assertEqual(links, [f"Topuria Holloway line {n}." for n in range(3)])

    def test_a_link_past_the_deadline_is_named(self):
        def one_slow(url):
            if url.endswith("-2"):
                time.sleep(2.0)
            return _slow_reader(0.0)(url)

        unread: list[str] = []
        with patch.dict(os.environ, {"FACTS_ROOM_DEADLINE_S": "0.3"}):
            rows = _gather(one_slow, unread=unread)
        self.assertEqual(unread, [URLS[2]])
        self.assertEqual(len(rows), 2)


class ReportTests(unittest.TestCase):
    PAGE = (
        "<html><head><title>Topuria stops Holloway</title></head><body><p>"
        + (
            "Topuria knocked out Holloway in the third round at UFC 308 in Abu Dhabi on Saturday. "
            * 2
        )
        + "</p></body></html>"
    )

    def _fake_get(self, *_a, **_kw):
        class _R:
            status_code = 200
            text = self.PAGE
            content = self.PAGE.encode()
            headers: ClassVar[dict[str, str]] = {"content-type": "text/html"}
            url = "https://example.com/a"

        return _R()

    def test_the_report_comes_back_with_the_lines(self):
        from core import link_facts

        with (
            patch("requests.get", side_effect=self._fake_get),
            patch.object(link_facts, "_is_blocked_url", return_value=False),
        ):
            lines, report = link_facts.extract_facts_with_report("https://example.com/a")
        self.assertTrue(lines)
        self.assertEqual(report["title"], "Topuria stops Holloway")

    def test_reading_with_a_report_leaves_the_terminal_report_alone(self):
        from core import link_facts

        before = link_facts.last_extract_report()
        with (
            patch("requests.get", side_effect=self._fake_get),
            patch.object(link_facts, "_is_blocked_url", return_value=False),
        ):
            link_facts.extract_facts_with_report("https://example.com/a")
        self.assertEqual(link_facts.last_extract_report(), before)

    def test_the_terminal_prompt_still_gets_its_report(self):
        from core import link_facts

        with (
            patch("requests.get", side_effect=self._fake_get),
            patch.object(link_facts, "_is_blocked_url", return_value=False),
        ):
            link_facts.extract_facts_from_url("https://example.com/a")
        self.assertEqual(link_facts.last_extract_report()["title"], "Topuria stops Holloway")

    def test_concurrent_reports_do_not_mix(self):
        from core import link_facts

        def page(title):
            return (
                f"<html><head><title>{title}</title></head><body><p>"
                + f"{title} said the fight card for Saturday is now set in Abu Dhabi. " * 2
                + "</p></body></html>"
            )

        def fake_get(url, *_a, **_kw):
            time.sleep(0.05)
            title = "Alpha" if url.endswith("a") else "Beta"

            class _R:
                status_code = 200
                text = page(title)
                content = page(title).encode()
                headers: ClassVar[dict[str, str]] = {"content-type": "text/html"}

            _R.url = url
            return _R()

        out: dict[str, str] = {}

        def read(url):
            _lines, report = link_facts.extract_facts_with_report(url)
            out[url] = report.get("title")

        with (
            patch("requests.get", side_effect=fake_get),
            patch.object(link_facts, "_is_blocked_url", return_value=False),
        ):
            threads = [
                threading.Thread(target=read, args=(u,))
                for u in ("https://x.com/a", "https://x.com/b")
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(out, {"https://x.com/a": "Alpha", "https://x.com/b": "Beta"})


if __name__ == "__main__":
    unittest.main()
