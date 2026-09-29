"""#905: refresh the contract fixtures from the live APIs, on the operator's PC.

The eighteen `tests/fixtures/signal_payloads/*.json` were written from each provider's
documented shape, because the build container cannot reach the APIs (#626, #906).
`ops record-payloads` runs each pinned signal once with the operator's own keys, keeps
the body of the pinned call, trims it to the fields the fixture already holds, and says
what the live answer no longer carries. `--apply` writes it. Nothing here touches the
network: `requests` is replaced by a fake that answers like a live API would.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

LIVE_RAWG = {
    "count": 3,
    "next": "https://api.rawg.io/api/games?page=2",
    "results": [
        {"id": 3498, "slug": "grand-theft-auto-vi", "name": "Grand Theft Auto VI",
         "released": "2026-11-19", "rating": 0, "genres": [{"name": "Action", "id": 4}],
         "background_image": "https://media.rawg.io/x.jpg", "tags": [1, 2, 3]},
        {"id": 3499, "slug": "gta-vi-2", "name": "Grand Theft Auto VI Online",
         "released": "2026-12-01", "rating": 0, "genres": []},
        {"id": 1, "slug": "x", "name": "X", "released": "2020-01-01", "rating": 1, "genres": []},
    ],
}  # fmt: skip


def _resp(body, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body
    resp.text = json.dumps(body)
    resp.headers = {}
    return resp


class _Folder(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self._tmp.name)
        src = Path(__file__).resolve().parent / "fixtures" / "signal_payloads" / "rawg.json"
        (self.folder / "rawg.json").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        self.env = patch.dict(os.environ, {"RAWG_API_KEY": "live-key-from-env"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self._tmp.cleanup()

    def _record(self, live, **kw):
        from apis.payload_recorder import record_all

        with patch("requests.get", return_value=_resp(live)) as fake:
            reports = record_all(self.folder, **kw)
        return reports, fake


class TrimTests(unittest.TestCase):
    def test_trim_keeps_the_fixture_shape_and_two_items(self):
        from apis.payload_recorder import trim_like

        old = {
            "count": 1,
            "results": [{"name": "a", "released": "2020", "genres": [{"name": "x"}]}],
        }
        new = trim_like(LIVE_RAWG, old)
        self.assertEqual(sorted(new), ["count", "results"])
        self.assertEqual(len(new["results"]), 2)
        self.assertEqual(sorted(new["results"][0]), ["genres", "name", "released"])
        self.assertEqual(new["results"][0]["genres"], [{"name": "Action"}])

    def test_missing_fields_are_named(self):
        from apis.payload_recorder import missing_paths

        old = {"results": [{"name": "a", "released": "2020"}]}
        new = {"results": [{"name": "a"}]}
        self.assertEqual(missing_paths(old, new), ["results[].released"])


class RecordTests(_Folder):
    def test_dry_run_reports_and_writes_nothing(self):
        before = (self.folder / "rawg.json").read_text(encoding="utf-8")
        reports, _fake = self._record(LIVE_RAWG)
        self.assertEqual(reports[0].signal, "rawg")
        self.assertEqual(reports[0].outcome, "recorded")
        self.assertEqual((self.folder / "rawg.json").read_text(encoding="utf-8"), before)

    def test_the_live_key_is_used_not_the_fixtures_test_key(self):
        _reports, fake = self._record(LIVE_RAWG)
        self.assertIn("live-key-from-env", str(fake.call_args))
        self.assertNotIn("test-key", str(fake.call_args))

    def test_apply_writes_the_trimmed_body_and_dates_the_note(self):
        self._record(LIVE_RAWG, apply=True, today="2026-09-29")
        fixture = json.loads((self.folder / "rawg.json").read_text(encoding="utf-8"))
        self.assertEqual(len(fixture["response"]["results"]), 2)
        self.assertNotIn("background_image", fixture["response"]["results"][0])
        self.assertIn("Recorded 2026-09-29 from the live API", fixture["note"])

    def test_a_lost_field_is_reported(self):
        live = json.loads(json.dumps(LIVE_RAWG))
        for item in live["results"]:
            item.pop("released")
        reports, _fake = self._record(live)
        self.assertIn("results[].released", reports[0].missing)

    def test_drift_is_reported_and_never_applied(self):
        before = (self.folder / "rawg.json").read_text(encoding="utf-8")
        reports, _fake = self._record({"games": []}, apply=True)
        self.assertEqual(reports[0].outcome, "schema drift")
        self.assertEqual((self.folder / "rawg.json").read_text(encoding="utf-8"), before)

    def test_no_key_is_skipped(self):
        with patch.dict(os.environ, {"RAWG_API_KEY": ""}):
            reports, fake = self._record(LIVE_RAWG)
        self.assertEqual(reports[0].outcome, "skipped")
        fake.assert_not_called()

    def test_one_signal_by_name(self):
        from apis.payload_recorder import record_all

        with patch("requests.get") as fake:
            self.assertEqual(record_all(self.folder, only="tmdb"), [])
        fake.assert_not_called()


class OpsTests(_Folder):
    def test_the_verb(self):
        from scripts.ops import COMMANDS

        buf = io.StringIO()
        with (
            patch("requests.get", return_value=_resp(LIVE_RAWG)),
            patch("apis.payload_recorder.FIXTURES", self.folder),
            redirect_stdout(buf),
        ):
            code = COMMANDS["record-payloads"][1](Namespace(target=None, apply=False))
        self.assertEqual(code, 0)
        self.assertIn("rawg", buf.getvalue())
        self.assertIn("dry run", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
