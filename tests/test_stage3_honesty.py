"""Honesty leftovers from review 3: #681 #682 #674 #680 #679.

Fail-then-fix on HEAD dbbd582: pipeline assigns craft features twice, decisions
§4 still says 4500, traces keep vault paths, CTA strip is silent, contact-sheet
HTML and llm_tells.json have no unique consumer.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestDuplicateFeatureAssignment(unittest.TestCase):
    def test_pipeline_copies_cta_and_rhythm_once(self):
        src = Path("core/pipeline.py").read_text(encoding="utf-8")
        self.assertEqual(
            src.count('result.features["cta_summary"]'),
            1,
            "#681: the same two assignments were pasted twice in _finalize_run",
        )
        self.assertEqual(src.count('result.features["sentence_rhythm"]'), 1)


class TestFactBudgetDecisionMatchesCode(unittest.TestCase):
    def test_section_four_cites_the_live_12000_default(self):
        from core.operator_facts import operator_key_fact_char_budget

        with patch.dict(os.environ, {"OPERATOR_KEY_FACT_CHAR_BUDGET": ""}, clear=False):
            os.environ.pop("OPERATOR_KEY_FACT_CHAR_BUDGET", None)
            self.assertEqual(operator_key_fact_char_budget(), 12000)
        decisions = Path("docs/decisions.md").read_text(encoding="utf-8")
        section = decisions.split("### 4.")[1].split("### 4b.")[0]
        self.assertNotIn("4500", section)
        self.assertIn("12000", section)


class TestTracePathRedaction(unittest.TestCase):
    def test_ffmpeg_command_does_not_echo_vault_or_home(self):
        """Rule 18: the username on this box must not make the assertion pass."""
        from core import run_trace

        vault = "/home/ciuser/VaultName"
        home = "/home/ciuser"
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(run_trace, "TRACES_DIR", tmp),
                patch("core.chrome.Path.home", return_value=Path(home)),
                patch.dict(
                    os.environ,
                    {
                        "OBSIDIAN_VAULT_PATH": vault,
                        "USERNAME": "ciuser",
                        "USER": "ciuser",
                    },
                    clear=False,
                ),
            ):
                path = run_trace.write_run_trace(
                    run_id=4242,
                    channel_id="tapin",
                    input_topic="t",
                    selected_topic="t",
                    status="drafted",
                    quality={
                        "ffmpeg_command": f"ffmpeg -i {vault}/clip.mp4 {home}/out.mp4",
                        "script": f"Wrote {vault}/_runs/71.md",
                    },
                )
                self.assertIsNotNone(path)
                blob = Path(path).read_text(encoding="utf-8")
        self.assertNotIn("VaultName", blob)
        self.assertNotIn("ciuser", blob)
        self.assertIn("[vault]", blob)


class TestCtaStripIsVisibleAndGated(unittest.TestCase):
    def test_gate_off_keeps_in_summary_and_report_shows_counts_when_on(self):
        from core.script_craft import apply_script_craft
        from core.ui import display_fact_engine_report

        script = (
            "Ilia Topuria kept the belt in June. The take is that the division is stuck.\n\n"
            "In summary, Topuria is still champion and the division is stuck.\n\n"
            "Like and subscribe for the next card."
        )
        with patch.dict(os.environ, {"CTA_SUMMARY_STRIP": "false"}, clear=False):
            kept, report, _rhythm = apply_script_craft(script)
        self.assertIn("In summary", kept)
        self.assertFalse(report["stripped"])

        with patch.dict(os.environ, {"CTA_SUMMARY_STRIP": "true"}, clear=False):
            cleaned, on_report, rhythm = apply_script_craft(script)
        self.assertNotIn("In summary", cleaned)
        self.assertTrue(on_report["stripped"])
        lines: list[str] = []
        display_fact_engine_report(
            {"cta_summary": on_report, "sentence_rhythm": rhythm},
            print_fn=lines.append,
        )
        joined = "\n".join(lines)
        # Not assertIn("3") — a bare digit matches any number anywhere in the report,
        # so that guard passed with the counts printed wrong or not at all (rule 17).
        self.assertIn("(3 -> 2 paragraphs)", joined, joined)

    def test_the_rhythm_flag_reaches_the_report_from_a_real_script(self):
        """The gate test above fed `rhythm or [...]` into the report, so it proved
        nothing about #540: the fallback fired because a varied script flags nothing.
        This drives the flag from a script that genuinely trips it."""
        from core.script_craft import apply_script_craft
        from core.ui import display_fact_engine_report

        uniform = " ".join(["The champion looked sharp all night."] * 6)
        _clean, _report, rhythm = apply_script_craft(uniform)
        self.assertEqual(rhythm, ["uniform sentence length"], rhythm)

        lines: list[str] = []
        display_fact_engine_report({"sentence_rhythm": rhythm}, print_fn=lines.append)
        joined = "\n".join(lines)
        self.assertIn("Sentence rhythm: uniform sentence length", joined, joined)


class TestContactSheetHtmlHasACaller(unittest.TestCase):
    def test_render_writes_html_next_to_the_png(self):
        from PIL import Image

        from core.contact_sheet import render_contact_sheet

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "thumbs"
            folder.mkdir()
            Image.new("RGB", (32, 32), (255, 0, 0)).save(folder / "a.png")
            dest = Path(tmp) / "sheet.png"
            result = render_contact_sheet(str(dest), thumbs_dir=str(folder), channel_id="tapin")
            html = Path(result.html_path)
            self.assertTrue(html.is_file(), "ops contact-sheet must write the print HTML")
            text = html.read_text(encoding="utf-8")
        self.assertIn("sheet.png", text)
        self.assertIn("@media print", text)


class TestLlmTellsJsonCarriesAPhraseTheTupleLacks(unittest.TestCase):
    def test_json_only_phrase_flags_and_vanishes_without_the_file(self):
        import json as json_mod

        from core.persona_lint import _FILLER_PHRASES, lint_persona_script

        data = json_mod.loads(Path("config/llm_tells.json").read_text(encoding="utf-8"))
        extras = {
            str(p).lower()
            for p in (data.get("shared") or [])
            if str(p).lower() not in {x.lower() for x in _FILLER_PHRASES}
        }
        self.assertTrue(extras, "llm_tells.json must add a phrase the hardcoded tuple lacks")
        phrase = sorted(extras)[0]
        hits = lint_persona_script(f"Yes, {phrase}, the purse doubled.", channel_id="tapin")
        self.assertTrue(any(phrase in h.lower() for h in hits))
        with tempfile.TemporaryDirectory() as tmp:
            with patch("config.paths.ROOT_DIR", tmp):
                missing = lint_persona_script(
                    f"Yes, {phrase}, the purse doubled.",
                    channel_id="tapin",
                )
        self.assertFalse(
            any(phrase in h.lower() for h in missing),
            "deleting llm_tells.json must drop the JSON-only phrase (rule 17)",
        )
