"""#607 deferred ElevenLabs import and #335 source-diversity floor.

Fail-then-fix: core.tts currently imports elevenlabs.client at module load;
one-outlet news URLs still count as verified facts.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


class TestElevenLabsImportIsDeferred(unittest.TestCase):
    def test_importing_core_tts_does_not_need_the_sdk(self):
        root = Path(__file__).resolve().parents[1]
        code = (
            "import sys, types\n"
            "sys.modules['elevenlabs'] = types.ModuleType('elevenlabs')\n"
            "sys.modules.pop('elevenlabs.client', None)\n"
            "sys.modules.pop('core.tts', None)\n"
            "import core.tts as tts\n"
            "assert hasattr(tts, 'generate_audio')\n"
            "print('ok')\n"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(root),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("ok", proc.stdout)

    def test_elevenlabs_client_is_constructed_only_from_the_factory(self):
        from core.tts import _elevenlabs_client

        src = Path("core/tts.py").read_text(encoding="utf-8")
        self.assertNotIn("from elevenlabs.client import ElevenLabs\n", src.split("def ")[0])
        self.assertIn("def _elevenlabs_client", src)
        self.assertTrue(callable(_elevenlabs_client))
        self.assertIn("client = _elevenlabs_client(eleven_key)", src)


class TestSourceDiversityFloor(unittest.TestCase):
    def test_two_paths_on_espn_are_one_outlet(self):
        from core.source_diversity import source_diversity_ok, unique_domains

        urls = [
            "https://www.espn.com/mma/story/_/id/1/ufc-318",
            "https://espn.com/mma/story/_/id/2/results",
        ]
        self.assertEqual(unique_domains(urls), frozenset({"espn.com"}))
        self.assertFalse(
            source_diversity_ok(
                urls,
                topic="UFC 318 results Saturday as of June 2026",
            )
        )

    def test_espn_plus_mmafighting_passes(self):
        from core.source_diversity import source_diversity_ok

        self.assertTrue(
            source_diversity_ok(
                [
                    "https://www.espn.com/mma/story/_/id/1/ufc-318",
                    "https://www.mmafighting.com/2026/6/7/ufc-318",
                ],
                topic="UFC 318 results Saturday as of June 2026",
            )
        )

    def test_evergreen_explainer_does_not_fire(self):
        from core.source_diversity import source_diversity_ok

        self.assertTrue(
            source_diversity_ok(
                ["https://www.espn.com/soccer/offside"],
                topic="how does the offside rule actually work",
            )
        )

    def test_single_outlet_news_is_demoted_from_verified(self):
        from core.source_diversity import demote_single_outlet_news

        verified = (
            "News — ESPN: https://www.espn.com/mma/story/_/id/1/ufc-318 "
            "Ilia Topuria kept the belt Saturday."
        )
        kept, context, verdict = demote_single_outlet_news(
            verified,
            urls=["https://www.espn.com/mma/story/_/id/1/ufc-318"],
            topic="UFC 318 results Saturday",
        )
        self.assertEqual(verdict["status"], "single_outlet")
        self.assertIn("espn.com", verdict["domain"])
        self.assertFalse(kept.strip())
        self.assertIn("Ilia Topuria", context)

    def test_build_prompts_on_tapin_demotes_espn_only_news(self):
        from core.content_engine import _build_prompts

        facts = (
            "News — ESPN: https://www.espn.com/mma/story/_/id/1/ufc-318 "
            "Ilia Topuria kept the belt Saturday."
        )
        with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": ""}, clear=False):
            _system, user = _build_prompts(
                topic="UFC 318 results Saturday",
                signals={},
                min_words=60,
                max_words=90,
                today="2026-06-17",
                channel_id="tapin",
                script_brief="Be punchy.",
                seo_block="",
                signal_facts=facts,
                signal_summary="",
                brief_block="",
                length_choice="1",
                key_facts=[],
            )
        verified_part = user.split("VERIFIED FACTS", 1)[1].split("CONTEXT SIGNALS", 1)[0]
        self.assertIn("no verified game data available", verified_part.lower())
        self.assertIn("CONTEXT SIGNALS", user)
        self.assertIn("Ilia Topuria", user.split("CONTEXT SIGNALS", 1)[1])
