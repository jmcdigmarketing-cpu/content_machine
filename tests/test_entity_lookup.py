"""#963: the people, teams and games a topic names are looked up on every run.

Operator, 2026-10-05: "i shouldnt have to fact intake such a known topic" - what team LeBron
is on. Nothing looked them up: event research (#899) reads Wikipedia only when the topic
names an event no fact covers, the key-facts prompt still asked the operator for "Who holds
what NOW (champion, ranking, roster, CEO)", and the script prompt forbids specifics that are
not in VERIFIED FACTS - so the current team was pasted by hand or left out. Overnight and
batch drafts never get a paste at all.

`core/facts/entity_lookup` resolves each name on Wikidata (aliases too: "Wemby"), reads the
claims that go stale - current team, position held, head coach, a game's release date,
developer and platforms - and the Wikipedia intro. Wikidata lines ride at signal tier
(structured data, like Tapology or RAWG), Wikipedia lines at web tier. No network here:
every response is a fixture.
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from apis.signal_contract import make_signal

TODAY = "2026-10-05"


def _claim(value_id, *, ended=False, rank="normal"):
    claim = {
        "rank": rank,
        "mainsnak": {"datavalue": {"value": {"id": value_id}, "type": "wikibase-entityid"}},
    }
    if ended:
        claim["qualifiers"] = {
            "P582": [{"datavalue": {"value": {"time": "+2018-07-01T00:00:00Z"}}}]
        }
    return claim


def _time_claim(iso):
    return {"rank": "normal", "mainsnak": {"datavalue": {"value": {"time": iso}, "type": "time"}}}


SEARCH = {
    "LeBron James": [
        {"id": "Q36159", "label": "LeBron James", "description": "American basketball player",
         "match": {"type": "label", "text": "LeBron James"}},
    ],
    "Wemby": [
        {"id": "Q1", "label": "Wemby", "description": "Wikimedia disambiguation page",
         "match": {"type": "label", "text": "Wemby"}},
        {"id": "Q100", "label": "Victor Wembanyama", "description": "French basketball player",
         "match": {"type": "alias", "text": "Wemby"}},
    ],
    "Ghost of Yotei": [
        {"id": "Q500", "label": "Ghost of Yōtei", "description": "2025 video game",
         "match": {"type": "label", "text": "Ghost of Yotei"}},
    ],
}  # fmt: skip
ENTITIES = {
    "Q36159": {
        "labels": {"en": {"value": "LeBron James"}},
        "descriptions": {"en": {"value": "American basketball player"}},
        "sitelinks": {"enwiki": {"title": "LeBron James"}},
        "claims": {"P54": [_claim("Q162990", ended=True), _claim("Q121783")]},
    },
    "Q100": {
        "labels": {"en": {"value": "Victor Wembanyama"}},
        "descriptions": {"en": {"value": "French basketball player"}},
        "sitelinks": {"enwiki": {"title": "Victor Wembanyama"}},
        "claims": {"P54": [_claim("Q159729")]},
    },
    "Q500": {
        "labels": {"en": {"value": "Ghost of Yōtei"}},
        "descriptions": {"en": {"value": "2025 video game"}},
        "sitelinks": {"enwiki": {"title": "Ghost of Yōtei"}},
        "claims": {
            "P577": [_time_claim("+2025-10-02T00:00:00Z")],
            "P178": [_claim("Q900")],
            "P400": [_claim("Q901")],
        },
    },
}
LABELS = {
    "Q162990": "Cleveland Cavaliers",
    "Q121783": "Los Angeles Lakers",
    "Q159729": "San Antonio Spurs",
    "Q900": "Sucker Punch Productions",
    "Q901": "PlayStation 5",
}
EXTRACTS = {
    "LeBron James": (
        "LeBron Raymone James Sr. is an American professional basketball player for the Los "
        "Angeles Lakers of the National Basketball Association. He is widely regarded as one of "
        "the greatest basketball players of all time."
    ),
    "Victor Wembanyama": (
        "Victor Wembanyama is a French professional basketball player for the San Antonio Spurs "
        "of the National Basketball Association."
    ),
    "Ghost of Yōtei": (
        "Ghost of Yōtei is a 2025 action-adventure game developed by Sucker Punch Productions."
    ),
}
CREATED = {"LeBron James": "2003-02-11T00:00:00Z", "Victor Wembanyama": "2019-06-01T00:00:00Z",
           "Ghost of Yōtei": "2024-09-24T00:00:00Z"}  # fmt: skip
CALLS: list[dict] = []


def _resp(payload):
    return SimpleNamespace(status_code=200, json=lambda: payload, text="")


def _fake_get(url, params=None, **_kw):
    params = dict(params or {})
    CALLS.append({"url": url, **params})
    if "wikidata.org" in url and params.get("action") == "wbsearchentities":
        return _resp({"search": SEARCH.get(params["search"], [])})
    if "wikidata.org" in url and params.get("action") == "wbgetentities":
        ids = params["ids"].split("|")
        if params.get("props") == "labels":
            return _resp({"entities": {i: {"labels": {"en": {"value": LABELS[i]}}} for i in ids}})
        return _resp({"entities": {i: ENTITIES[i] for i in ids}})
    if "wikipedia.org" in url and params.get("list") == "search":
        return _resp({"query": {"search": []}})
    if "wikipedia.org" in url and params.get("prop") == "extracts|revisions":
        title = params["titles"]
        page = {
            "title": title,
            "extract": EXTRACTS.get(title, ""),
            "revisions": [{"timestamp": CREATED[title]}] if title in CREATED else [],
        }
        return _resp({"query": {"pages": {"1": page}}})
    raise AssertionError(f"unexpected request {url} {params}")


class LookupCase(unittest.TestCase):
    def setUp(self) -> None:
        CALLS.clear()
        self._patches = [
            patch.dict(os.environ, {"ENTITY_RESEARCH_ENABLED": "true"}),
            patch("core.facts.entity_lookup.get_cached", return_value=None),
            patch("core.facts.entity_lookup.set_cache"),
            patch("core.facts.entity_lookup._today", return_value=TODAY),
            patch("core.facts.entity_lookup.requests.get", side_effect=_fake_get),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self) -> None:
        for p in reversed(self._patches):
            p.stop()


class NamesTests(unittest.TestCase):
    def test_the_names_in_a_topic_and_its_angle(self):
        from core.facts.entity_lookup import names_for

        names = names_for("Is LeBron James done with the Lakers?", angle="LeBron's last season")
        # #1002: a team is looked up by its full name, where it was typed.
        self.assertEqual(names[:2], ["LeBron James", "Los Angeles Lakers"])

    def test_a_lower_case_topic_still_finds_a_known_player(self):
        from core.facts.entity_lookup import names_for

        self.assertIn("wemby", [n.lower() for n in names_for("wemby's 40 point night")])

    def test_a_name_with_of_in_it_stays_whole(self):
        from core.facts.entity_lookup import names_for

        self.assertEqual(names_for("Ghost of Yotei first impressions"), ["Ghost of Yotei"])

    def test_at_most_four(self):
        from core.facts.entity_lookup import names_for

        names = names_for("Lakers vs Celtics vs Knicks vs Heat vs Bulls vs Spurs")
        self.assertLessEqual(len(names), 4)


class LookupTests(LookupCase):
    def test_the_current_team_not_the_old_one(self):
        from core.facts.entity_lookup import lookup_entity

        found = lookup_entity("LeBron James")
        text = "\n".join(found["wikidata_lines"])
        self.assertIn("current team: Los Angeles Lakers", text)
        self.assertNotIn("Cleveland", text)
        self.assertIn(TODAY, text)
        self.assertTrue(found["wikipedia_lines"][0].startswith("LeBron Raymone James Sr."))
        self.assertEqual(found["created"], "2003-02-11")

    def test_a_nickname_resolves_through_its_alias(self):
        from core.facts.entity_lookup import lookup_entity

        found = lookup_entity("Wemby")
        self.assertEqual(found["label"], "Victor Wembanyama")
        self.assertIn("current team: San Antonio Spurs", "\n".join(found["wikidata_lines"]))
        self.assertTrue(any("Spurs" in line for line in found["wikipedia_lines"]))

    def test_a_game_gives_its_release_date_developer_and_platforms(self):
        from core.facts.entity_lookup import lookup_entity

        found = lookup_entity("Ghost of Yotei")
        self.assertEqual(found["released"], "2025-10-02")
        text = "\n".join(found["wikidata_lines"])
        self.assertIn("released 2025-10-02", text)
        self.assertIn("Sucker Punch Productions", text)
        self.assertIn("PlayStation 5", text)

    def test_nothing_found_is_an_empty_result(self):
        from core.facts.entity_lookup import lookup_entity

        found = lookup_entity("Zzyzx Nobody")
        self.assertEqual(found["wikidata_lines"], [])
        self.assertEqual(found["wikipedia_lines"], [])
        self.assertFalse(found["has_article"])

    def test_a_failure_never_raises(self):
        from core.facts.entity_lookup import lookup_entity

        with patch("core.facts.entity_lookup.requests.get", side_effect=OSError("offline")):
            found = lookup_entity("LeBron James")
        self.assertEqual(found["wikidata_lines"], [])


NEWS_ONLY = {"news": make_signal(connected=True, active=True, score=40, data={"headlines": []})}


class SignalTests(LookupCase):
    SIGNALS = NEWS_ONLY

    def test_attached_as_a_signal_that_moves_no_score(self):
        from core.facts.entity_lookup import SIGNAL_NAME, attach_entity_research

        signals, report = attach_entity_research(
            self.SIGNALS, topic="Is LeBron James done with the Lakers?"
        )
        sig = signals[SIGNAL_NAME]
        self.assertEqual(sig["score"], 0)
        self.assertTrue(sig["active"])
        self.assertIn("LeBron James", report["names"])
        self.assertGreaterEqual(report["lines"], 2)
        self.assertIn("Wikidata", report["sources"])
        self.assertNotIn(SIGNAL_NAME, self.SIGNALS)  # a copy, never the caller's dict

    def test_wikidata_lines_are_structured_data_wikipedia_lines_are_web(self):
        from core.facts.entity_lookup import attach_entity_research
        from core.facts.store import TIER_SIGNAL, TIER_WEB
        from core.grounding_tiers import build_tiered_corpus
        from core.signal_facts import format_signal_facts

        signals, _ = attach_entity_research(self.SIGNALS, topic="LeBron James")
        corpus = build_tiered_corpus(signal_facts=format_signal_facts(signals))
        tiers = {line.strip(): tier for tier, line in corpus.lines if line.strip()}
        team = next(k for k in tiers if "current team: Los Angeles Lakers" in k)
        intro = next(k for k in tiers if k.lstrip("•- ").startswith("LeBron Raymone"))
        self.assertEqual(tiers[team], TIER_SIGNAL)
        self.assertEqual(tiers[intro], TIER_WEB)

    def test_the_lakers_line_reaches_verified_facts(self):
        from core.content_engine import _split_facts_block
        from core.facts.entity_lookup import attach_entity_research
        from core.signal_facts import format_signal_facts

        signals, _ = attach_entity_research(self.SIGNALS, topic="LeBron James")
        verified, _context = _split_facts_block(format_signal_facts(signals))
        self.assertIn("current team: Los Angeles Lakers", verified)

    def test_off_means_no_request(self):
        from core.facts.entity_lookup import attach_entity_research

        with patch.dict(os.environ, {"ENTITY_RESEARCH_ENABLED": "false"}):
            signals, report = attach_entity_research(self.SIGNALS, topic="LeBron James")
        self.assertIsNone(report)
        self.assertEqual(CALLS, [])
        self.assertEqual(set(signals), {"news"})

    def test_an_outage_leaves_the_signals_alone(self):
        from core.facts.entity_lookup import attach_entity_research

        with patch("core.facts.entity_lookup.requests.get", side_effect=OSError("offline")):
            signals, report = attach_entity_research(self.SIGNALS, topic="LeBron James")
        self.assertEqual(set(signals), {"news"})
        self.assertEqual(report["lines"], 0)

    def test_only_a_find_is_cached(self):
        from core.facts import entity_lookup

        with patch("core.facts.entity_lookup.set_cache") as cache:
            entity_lookup.lookup_entity("Zzyzx Nobody")
            cache.assert_not_called()
            entity_lookup.lookup_entity("LeBron James")
            cache.assert_called_once()


class PipelineTests(LookupCase):
    def test_the_pipeline_hands_the_lookup_to_the_script(self):
        from core.pipeline import DiscoveryResult, run_pipeline

        topic = "Is LeBron James done with the Lakers?"
        signals = NEWS_ONLY
        discovery = DiscoveryResult(
            input_topic=topic, base_signals=signals, evaluated=[(topic, 90.0, signals)],
            channel_id="tapin",
        )  # fmt: skip
        with (
            patch("core.pipeline.write_run_trace"),
            patch("core.pipeline.persist_quality"),
            patch("core.pipeline.build_quality", return_value={}),
            patch("core.pipeline.record_learning_outcome"),
            patch("core.pipeline.record_content_run", return_value=42),
            patch("core.pipeline.build_research_brief", return_value=MagicMock(version="v1")),
            patch("core.pipeline.generate_content_package") as content,
        ):
            content.return_value = {"title": "T", "script": "S", "description": "D", "tags": []}
            result = run_pipeline(
                topic, discovery=discovery, variant_index=0, proceed_video=False, channel_id="tapin"
            )
        sent = content.call_args.kwargs["signals"]
        self.assertIn("entity_research", sent)
        self.assertIn("LeBron James", result.features["entity_research"]["names"])


if __name__ == "__main__":
    unittest.main()
