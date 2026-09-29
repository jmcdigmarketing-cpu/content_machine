"""#860: the facts room - every pasted link read at once, ranked, kept or dropped by tick.

Run 98 spent 7.9 of 11.2 operator minutes at the key-facts prompt: one URL at a time, an
off-topic question per link, then a separate vault review. In the run window the paste
box already held everything; the prompt still walked it line by line. Now, when a run
window is attached (`core.ask_bridge.current_bridge`), `prompt_key_facts_result` reads the
whole paste, flags off-topic link lines, offers the vault, ranks every line by #548's
confidence, and asks once - a `facts_room` request the window answers with the ticked
rows. What happens next is unchanged: typed lines stay operator tier, link lines link
tier, vault lines keep their note, and the same selector picks what rides in the prompt.
The terminal keeps the old prompt; `ops facts-room` prints the same ranked table.
`FACTS_ROOM=false` turns the room off in the window too.
"""

from __future__ import annotations

import io
import os
import tempfile
import threading
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from unittest.mock import patch

from core.facts.store import FactRecord

TOPIC = "Topuria vs Holloway UFC 308"
URL = "https://www.espn.com/mma/story/topuria-holloway"
PAGE = [
    "Topuria knocked out Holloway in round 3 at UFC 308 in Abu Dhabi.",
    "Subscribe to our newsletter for the latest deals on sneakers.",
]
TYPED = "Topuria is the UFC featherweight champion."
VAULT = FactRecord(
    claim="Holloway held the BMF title before UFC 308.",
    tier="vault",
    relevance_score=0.8,
    note_path="tapin/holloway.md",
)


def _reader(url):
    return list(PAGE), {"title": "ESPN: Topuria stops Holloway", "published": None}


def _off_topic(lines, **_kw):
    return [line for line in lines if "sneakers" in line]


class GatherTests(unittest.TestCase):
    def _rows(self, pasted):
        from core.facts.room import gather

        return gather(
            TOPIC,
            "tapin",
            pasted_lines=pasted,
            read_url=_reader,
            flag_off_topic=_off_topic,
            load_vault=lambda corpus: [VAULT],
        )

    def test_every_source_lands_in_one_ranked_list(self):
        rows = self._rows([TYPED, URL])
        kinds = sorted(r.kind for r in rows)
        self.assertEqual(kinds, ["link", "link", "typed", "vault"])
        values = [r.confidence.value for r in rows]
        self.assertEqual(values, sorted(values, reverse=True))
        self.assertEqual([r.id for r in rows], [1, 2, 3, 4])

    def test_link_lines_carry_their_page(self):
        rows = self._rows([URL])
        link = next(r for r in rows if r.line == PAGE[0])
        self.assertEqual(link.source, "ESPN: Topuria stops Holloway")
        self.assertEqual(link.url, URL)
        self.assertEqual(link.tier, "link")

    def test_off_topic_lines_are_flagged_and_unticked(self):
        rows = self._rows([URL])
        junk = next(r for r in rows if "sneakers" in r.line)
        self.assertTrue(junk.off_topic)
        self.assertFalse(junk.keep)
        self.assertEqual(junk.confidence.label, "low")

    def test_typed_and_confident_vault_lines_start_ticked(self):
        rows = self._rows([TYPED])
        self.assertTrue(all(r.keep for r in rows))

    def test_a_link_that_reads_nothing_is_a_note_not_a_row(self):
        from core.facts.room import gather, unread_lines

        unread: list[str] = []
        rows = gather(
            TOPIC, "tapin", pasted_lines=[URL], read_url=lambda u: ([], {"title": "x"}),
            flag_off_topic=_off_topic, load_vault=lambda corpus: [], unread=unread,
        )  # fmt: skip
        self.assertEqual(rows, [])
        self.assertEqual(unread, [URL])
        self.assertIn("paste the article text", "\n".join(unread_lines(unread)))


class KeepTests(GatherTests):
    def test_kept_rows_split_by_tier(self):
        from core.facts.room import kept

        rows = self._rows([TYPED, URL])
        picked = [r.id for r in rows if "sneakers" not in r.line]
        result = kept(rows, picked)
        self.assertEqual(result.manual, [TYPED])
        self.assertEqual(result.link, [PAGE[0]])
        self.assertEqual(result.link_provenance, [(PAGE[0], URL, None)])
        self.assertEqual(result.sources, [{"url": URL, "title": "ESPN: Topuria stops Holloway"}])
        self.assertEqual(result.vault_claims, {VAULT.claim})

    def test_the_table(self):
        from core.facts.room import table_lines

        text = "\n".join(table_lines(self._rows([TYPED, URL])))
        self.assertIn("[x]", text)
        self.assertIn("[ ]", text)
        self.assertIn("off-topic", text)
        self.assertIn("conf", text)


class BridgeTests(unittest.TestCase):
    def test_ask_room_round_trip(self):
        from core.ask_bridge import AskBridge

        bridge = AskBridge()
        got: list = []
        worker = threading.Thread(target=lambda: got.append(bridge.ask_room(["row"])))
        worker.start()
        req = bridge.wait_request(timeout=2.0)
        self.assertEqual(req.kind, "facts_room")
        self.assertEqual(req.payload, ["row"])
        bridge.submit([2, 3])
        worker.join(2.0)
        self.assertEqual(got, [[2, 3]])

    def test_take_fact_lines_empties_the_queue(self):
        from core.ask_bridge import AskBridge

        bridge = AskBridge()
        bridge.set_fact_lines([TYPED, URL])
        self.assertEqual(bridge.take_fact_lines(), [TYPED, URL])
        self.assertEqual(bridge.take_fact_lines(), [])


class PromptTests(unittest.TestCase):
    """The room inside `prompt_key_facts_result`, with a window attached."""

    def _run(self, *, env=None, answer=None):
        from core import ui
        from core.ask_bridge import AskBridge, set_current_bridge

        bridge = AskBridge()
        bridge.set_fact_lines([TYPED, URL])
        captured: dict = {}

        done = threading.Event()

        def window():
            while not done.is_set():
                req = bridge.wait_request(timeout=0.05)
                if req is None:
                    continue
                if req.kind == "facts_room":
                    captured["rows"] = req.payload
                    ids = answer(req.payload) if answer else [r.id for r in req.payload if r.keep]
                    bridge.submit(ids)
                else:
                    captured.setdefault("prompts", []).append(req.prompt)
                    bridge.submit("")

        thread = threading.Thread(target=window, daemon=True)
        saved: list = []
        with (
            patch.dict(os.environ, {"FACTS_ROOM": "true", **(env or {})}),
            patch("core.link_facts.extract_facts_from_url", side_effect=lambda u: list(PAGE)),
            patch(
                "core.link_facts.extract_facts_with_report",
                side_effect=lambda u: (list(PAGE), {"title": "ESPN: Topuria stops Holloway"}),
            ),
            patch(
                "core.link_facts.last_extract_report",
                return_value={"title": "ESPN: Topuria stops Holloway", "found": 2, "kept": 2},
            ),
            patch("core.facts.selection.flag_off_topic", side_effect=_off_topic),
            patch("core.obsidian_facts.load_fact_records", return_value=[VAULT]),
            patch(
                "core.operator_facts.capture_facts_to_vault",
                side_effect=lambda c, t, facts, **kw: saved.append((list(facts), kw)) or True,
            ),
            patch("core.source_capture.capture_sources", return_value=True),
            patch("core.event_research.research_enabled", return_value=False),
        ):
            set_current_bridge(bridge)
            thread.start()
            try:
                result = ui.prompt_key_facts_result(
                    TOPIC, "tapin", print_fn=lambda *_a: None, input_fn=bridge.ask_text
                )
            finally:
                done.set()
                set_current_bridge(None)
                bridge.cancel()
                thread.join(2.0)
        return result, captured, saved

    def test_one_room_replaces_the_line_by_line_prompts(self):
        result, captured, _saved = self._run()
        self.assertIn("rows", captured)
        self.assertNotIn("prompts", captured)
        joined = " ".join(result.facts)
        self.assertIn("featherweight champion", joined)
        self.assertIn("knocked out Holloway", joined)
        self.assertNotIn("sneakers", joined)
        self.assertIn(URL, result.source_urls)

    def test_tiers_survive_the_room(self):
        _result, _captured, saved = self._run()
        tiers = {kw.get("tier", "operator"): facts for facts, kw in saved}
        self.assertEqual(tiers["operator"], [TYPED])
        self.assertEqual(tiers["link"], [PAGE[0]])

    def test_unticking_drops_the_line(self):
        result, _c, _s = self._run(
            answer=lambda rows: [r.id for r in rows if r.keep and r.kind != "typed"]
        )
        self.assertNotIn(TYPED, result.facts)

    def test_off_means_the_old_prompt(self):
        _result, captured, _saved = self._run(env={"FACTS_ROOM": "false"})
        self.assertNotIn("rows", captured)

    def test_the_terminal_never_opens_it(self):
        from core import ui

        with patch("core.facts.room.gather") as gather:
            ui.prompt_key_facts_result(
                TOPIC, "tapin", print_fn=lambda *_a: None, input_fn=lambda *_a: ""
            )
        gather.assert_not_called()


class OpsTests(unittest.TestCase):
    def test_the_verb_prints_the_table(self):
        from scripts.ops import COMMANDS

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "facts.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"{TYPED}\n{URL}\n")
            buf = io.StringIO()
            with (
                patch("core.link_facts.extract_facts_from_url", side_effect=lambda u: list(PAGE)),
                patch(
                    "core.link_facts.extract_facts_with_report",
                    side_effect=lambda u: (list(PAGE), {"title": "ESPN: Topuria stops Holloway"}),
                ),
                patch(
                    "core.link_facts.last_extract_report",
                    return_value={"title": "ESPN: Topuria stops Holloway"},
                ),
                patch("core.facts.selection.flag_off_topic", side_effect=_off_topic),
                patch("core.obsidian_facts.load_fact_records", return_value=[]),
                redirect_stdout(buf),
            ):
                code = COMMANDS["facts-room"][1](
                    Namespace(channel="tapin", topic=TOPIC, target=None, facts_file=path)
                )
        self.assertEqual(code, 0)
        text = buf.getvalue()
        self.assertIn("Facts room", text)
        self.assertIn("ESPN: Topuria stops Holloway", text)


class PanelTests(unittest.TestCase):
    def test_the_panel_model_needs_no_display(self):
        from core.facts.room import gather
        from desktop.facts_room import table_model

        rows = gather(
            TOPIC, "tapin", pasted_lines=[URL], read_url=_reader,
            flag_off_topic=_off_topic, load_vault=lambda corpus: [],
        )  # fmt: skip
        model = table_model(rows)
        junk = next(m for m in model if "sneakers" in m["line"])
        self.assertFalse(junk["checked"])
        self.assertTrue(junk["greyed"])
        self.assertEqual(model[0]["id"], rows[0].id)


if __name__ == "__main__":
    unittest.main()
