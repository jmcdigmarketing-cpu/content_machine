"""#89 public-safe SKU/export redaction — persist pre/post when lines are stripped."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from core.intelligence_report import IntelligenceReport, to_sku_markdown
from core.public_redact import redact_for_public


class TestPublicRedact(unittest.TestCase):
    def test_strips_keys_operator_facts_and_unpublished_scripts(self):
        raw = "\n".join(
            [
                "Angle: GTA 6 leak",
                "OPERATOR KEY FACTS:",
                "- Take-Two filed subpoenas. Do not publish this dump.",
                "OPENAI_API_KEY=sk-secret-material-here",
                "Unpublished script:",
                "He lost $2 billion in one afternoon. Full unused VO.",
                "Competitor pulse is fine.",
            ]
        )
        redacted, stats = redact_for_public(raw)
        self.assertNotIn("sk-secret-material-here", redacted)
        self.assertNotIn("OPENAI_API_KEY=", redacted)
        self.assertNotIn("Take-Two filed subpoenas. Do not publish this dump.", redacted)
        self.assertNotIn("Full unused VO", redacted)
        self.assertIn("Competitor pulse is fine.", redacted)
        self.assertGreater(stats["pre_lines"], stats["post_lines"])
        self.assertTrue(stats["stripped"])

    def test_sku_markdown_does_not_leak_key_material(self):
        report = IntelligenceReport(
            generated_at="2026-08-26T12:00:00+00:00",
            channel_id="tapin",
            channel_name="TapIn",
            input_topic="UFC 250",
            selected_variant="Topuria preview",
            composite_score=70.0,
            domain="ufc",
            research_brief={
                "narrative": "OPENAI_API_KEY=sk-leaked and unpublished script: secret VO"
            },
        )
        md = to_sku_markdown(report)
        self.assertNotIn("sk-leaked", md)
        self.assertNotIn("secret VO", md)
        self.assertIn("redaction", md.lower())

    def test_unpublished_dossier_withholds_full_script(self):
        from core.vault_dossiers import _render_dossier

        record = SimpleNamespace(
            channel_id="tapin",
            status="drafted",
            title="GTA 6 leak",
            selected_topic="GTA 6 leak",
            input_topic="GTA 6 leak",
            composite_score=70.0,
            features_json="{}",
            quality_json="{}",
            script_preview="Unpublished full script that must not leak on export.",
        )
        text = _render_dossier(record, run_id=71, day="2026-08-26")
        self.assertNotIn("Unpublished full script that must not leak on export.", text)
        self.assertIn("pre_lines", text)
        self.assertIn("post_lines", text)


if __name__ == "__main__":
    unittest.main()
