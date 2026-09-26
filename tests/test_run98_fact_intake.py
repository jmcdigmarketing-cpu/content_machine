"""Run 98: what the key-facts prompt took in, and what it should have.

The operator pasted six links for "Manchester City found guilty ... the prem". Four
intake defects, each with the run's own material:

- Every link added its page title as a fact ("Source: Premier League Top Scorers
  2026/27 ...") and its meta description ("View Premier League club and player
  stats ..."). On the JS-rendered stats page those two lines were ALL it got, and
  because the meta line counted as "body" the LINK_READER_PROXY retry never fired.
- Link-scraped lines were written to the vault as `tier: operator`, and a borrowed
  vault bullet kept that tier - so an old scraped "Marvel Rivals" line was pinned
  ahead of everything, like a line the operator typed.
- Nothing asked whether a pasted page was about the topic: 29 lines of a referee
  panel write-up (Konsa on Ballard, Awoniyi's red card) rode into the prompt for a
  story about financial charges.
- The link-line cap (40) was a literal the UI told the operator to "raise".
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core import link_facts as lf

RUN98 = "Manchester City ofund guilty, what does this mean for the prem"
ANGLE = "Premier League's future hinges on how City's violations are punished."

ON_TOPIC = [
    "An independent commission has reportedly found City guilty of 114 of the 115 charges.",
    "Several Premier League clubs had sought legal advice on compensation claims.",
    "Newcastle United narrowly avoided potential sanctions after selling players before a financial deadline.",
]
OFF_TOPIC = [
    "Incident: Penalty awarded. Challenge by Ezri Konsa on Dan Ballard (54 min)",
    "Marvel Rivals Season 4 adds Blade to the roster with a new team-up.",
]


def _page(title: str, meta: str, paragraphs: list[str]) -> str:
    body = "".join(f"<p>{p}</p>" for p in paragraphs)
    return (
        f'<html><head><title>{title}</title><meta name="description" content="{meta}">'
        f"</head><body><article>{body}</article></body></html>"
    )


def _fetch(html: str):
    return MagicMock(status_code=200, text=html, headers={})


@patch("core.link_facts._goose3_body_lines", return_value=[])
@patch("apis.youtube_api.extract_youtube_video_id", return_value=None)
class TestTheTitleIsNotAFact(unittest.TestCase):
    def test_title_goes_to_the_report_not_the_facts(self, _yt, _goose) -> None:
        html = _page(
            "Premier League clubs explore compensation claims",
            "Rival clubs may seek compensation after the Manchester City verdict.",
            [
                "Several Premier League clubs had already sought legal advice before Friday's verdict on compensation."
            ],
        )
        with patch("core.link_facts.requests.get", return_value=_fetch(html)):
            facts = lf.extract_facts_from_url("https://sports.example.com/city")
        self.assertFalse(any(f.lower().startswith("source:") for f in facts), facts)
        self.assertTrue(any("legal advice" in f for f in facts))
        self.assertEqual(
            lf.last_extract_report().get("title"),
            "Premier League clubs explore compensation claims",
        )

    def test_a_js_shell_page_retries_through_the_proxy(self, _yt, _goose) -> None:
        meta = (
            "View Premier League club and player stats, including goals scored, assists, "
            "total passes and clean sheets, on the official website of the Premier League."
        )
        html = _page("Premier League Top Scorers 2026/27", meta, [])
        recovered = "Erling Haaland leads the 2026/27 Premier League scoring chart with nine goals."
        with (
            patch("core.link_facts.requests.get", return_value=_fetch(html)),
            patch.dict(os.environ, {"LINK_READER_PROXY": "1"}, clear=False),
            patch("core.link_facts._reader_proxy_facts", return_value=[recovered]) as proxy,
        ):
            facts = lf.extract_facts_from_url("https://www.premierleague.com/en/stats")
        proxy.assert_called_once()
        self.assertIn(recovered, facts)
        self.assertFalse(any("official website" in f for f in facts), facts)

    def test_the_line_cap_is_an_env_setting(self, _yt, _goose) -> None:
        paragraphs = [
            f"Paragraph {i} about the Manchester City financial case carries a real detail number {i}."
            for i in range(10)
        ]
        html = _page(
            "City case", "A short summary sentence of the Manchester City case.", paragraphs
        )
        with (
            patch("core.link_facts.requests.get", return_value=_fetch(html)),
            patch.dict(os.environ, {"LINK_FACT_MAX_LINES": "6"}, clear=False),
        ):
            facts = lf.extract_facts_from_url("https://sports.example.com/case")
        self.assertEqual(len(facts), 6)
        self.assertEqual(lf.last_extract_report()["found"], 11)


class TestLinkLinesAreLinkTier(unittest.TestCase):
    def test_link_facts_are_written_as_link_tier(self) -> None:
        from core.fact_store import TIER_LINK, infer_tier_from_path
        from core.operator_facts import capture_facts_to_vault

        with tempfile.TemporaryDirectory() as tmp:
            with patch("core.obsidian_facts._vault_path", return_value=Path(tmp)):
                path = capture_facts_to_vault("tapin", RUN98, ON_TOPIC, tier="link")
            self.assertIsNotNone(path)
            text = Path(path).read_text(encoding="utf-8")
            rel = Path(path).relative_to(tmp)
        self.assertIn("_link_facts", rel.parts)
        self.assertIn("tier: link", text)
        self.assertEqual(infer_tier_from_path(rel), TIER_LINK)

    def test_a_borrowed_vault_line_is_not_pinned_like_a_typed_one(self) -> None:
        from core.fact_selection import select_facts_for_prompt
        from core.fact_store import TIER_OPERATOR, FactRecord

        borrowed = FactRecord(
            claim="Marvel Rivals Season 4 adds Blade to the roster with a new team-up mode.",
            tier=TIER_OPERATOR,
            note_path="tapin/_operator_facts/2026-07-01_marvel-rivals.md",
        )
        typed = FactRecord(claim=ON_TOPIC[0], tier=TIER_OPERATOR)
        chosen, _drops = select_facts_for_prompt(
            [borrowed, typed], topic=RUN98, corpus="", budget=len(ON_TOPIC[0]) + 10
        )
        self.assertEqual(chosen, [ON_TOPIC[0]])


class TestOffTopicLines(unittest.TestCase):
    CORPUS = (
        "Live web search (tavily):\n  • Man City found guilty of breaching financial rules - "
        "sanctions and a points deduction may follow"
    )

    def test_flag_only_lines_with_no_contact_with_the_topic(self) -> None:
        from core.fact_selection import flag_off_topic

        flagged = flag_off_topic(
            ON_TOPIC + OFF_TOPIC, reference=f"{ANGLE}\n{RUN98}", corpus=self.CORPUS
        )
        self.assertEqual(flagged, OFF_TOPIC)

    def _run(self, answer: str, printed: list):
        from core.ui import prompt_key_facts_result

        answers = iter(["https://example.com/city", "", answer])

        def _print(*args):
            printed.append(args[0] if args else "")

        with (
            patch("core.obsidian_facts.load_fact_records", return_value=[]),
            patch("core.operator_facts.capture_facts_to_vault", return_value=None),
            patch("core.console_input.input_pending", return_value=False),
            patch("core.console_input.read_pending_lines", return_value=[]),
            patch("core.link_facts.extract_facts_from_url", return_value=ON_TOPIC + OFF_TOPIC),
            patch(
                "core.link_facts.last_extract_report",
                return_value={"kept": 5, "found": 5, "published": None, "title": "City"},
            ),
            patch("core.source_capture.capture_sources", return_value=None),
        ):
            # Run 98 had six Tavily results; the evidence is what lets "Newcastle
            # avoided sanctions" count as context rather than off-topic.
            from apis.signal_contract import make_signal

            web = make_signal(
                connected=True,
                active=True,
                score=92,
                data={
                    "provider": "tavily",
                    "results": [
                        {
                            "title": "Man City found guilty of breaching financial rules",
                            "snippet": "sanctions and a points deduction may follow",
                        }
                    ],
                },
            )
            return prompt_key_facts_result(
                RUN98,
                "tapin",
                signals={"web_search": web},
                angle=ANGLE,
                print_fn=_print,
                input_fn=lambda *_a, **_k: next(answers, ""),
            )

    def test_enter_drops_the_flagged_lines(self) -> None:
        printed: list = []
        result = self._run("", printed)
        for line in OFF_TOPIC:
            self.assertNotIn(line, result.facts)
        for line in ON_TOPIC:
            self.assertIn(line, result.facts)
        self.assertTrue(any("off-topic" in str(p).lower() for p in printed), printed)

    def test_k_keeps_them(self) -> None:
        result = self._run("k", [])
        for line in OFF_TOPIC:
            self.assertIn(line, result.facts)


if __name__ == "__main__":
    unittest.main()
