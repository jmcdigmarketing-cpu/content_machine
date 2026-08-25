"""Honesty + leave-the-terminal wave 4: playbook lint, sources, booth, tray."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core import (
    description_extras,
    fact_grounding,
    html_report,
    metrics_gate,
    obsidian_facts,
    postmortem,
    render_gate,
    review_booth,
    vault_dossiers,
    win_notify,
)
from core.video_grade import GradeComponent, VideoGrade
from scripts import ops


class TestPlaybookLint(unittest.TestCase):
    def setUp(self):
        from core import vault_index

        vault_index.clear_cache()

    def tearDown(self):
        from core import vault_index

        vault_index.clear_cache()

    def test_untagged_anchored_strategy_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "tapin").mkdir()
            (vault / "tapin" / "notes.md").write_text(
                "---\nchannel: tapin\ntags: [facts]\n---\n"
                "# Notes\n"
                "- underdog/upset angles outperform in 2026 rankings\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                hits = obsidian_facts.lint_playbook("tapin")
            self.assertTrue(hits)
            self.assertIn("ground truth", hits[0]["reason"])

    def test_tagged_strategy_note_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "tapin" / "strategy").mkdir(parents=True)
            (vault / "tapin" / "strategy" / "voice.md").write_text(
                "---\nchannel: tapin\ntags: [strategy]\n---\n"
                "# Voice\n"
                "- underdog/upset angles outperform\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                hits = obsidian_facts.lint_playbook("tapin")
            self.assertEqual(hits, [])

    def test_command_registered(self):
        self.assertIn("playbook-lint", ops.COMMANDS)


class TestDescriptionSources(unittest.TestCase):
    def test_sources_block_from_urls(self):
        with (
            patch.dict(
                os.environ, {"DESCRIPTION_SOURCES": "true", "AI_DISCLOSURE_ENABLED": "false"}
            ),
            patch("core.description_extras.get_seo_profile", return_value={}),
        ):
            out = description_extras.apply_description_extras(
                "Body.",
                "tapin",
                source_urls=["https://example.com/a"],
            )
        self.assertIn("Sources:", out)
        self.assertIn("https://example.com/a", out)

    def test_collects_http_from_key_facts(self):
        urls = description_extras.collect_source_urls(
            key_facts=["Take-Two sued. https://ign.com/gta (paywall)"]
        )
        self.assertEqual(urls, ["https://ign.com/gta"])

    def test_disabled_skips_block(self):
        with (
            patch.dict(
                os.environ, {"DESCRIPTION_SOURCES": "false", "AI_DISCLOSURE_ENABLED": "false"}
            ),
            patch("core.description_extras.get_seo_profile", return_value={}),
        ):
            out = description_extras.apply_description_extras(
                "Body.", "tapin", source_urls=["https://example.com/a"]
            )
        self.assertEqual(out, "Body.")


class TestNumericChipsAndSemantic(unittest.TestCase):
    def test_looks_like_numeric_claim(self):
        self.assertTrue(fact_grounding.looks_like_numeric_claim("24-3"))
        self.assertTrue(fact_grounding.looks_like_numeric_claim("$50,000"))
        self.assertTrue(fact_grounding.looks_like_numeric_claim("ranked #1"))
        self.assertFalse(fact_grounding.looks_like_numeric_claim("Islam Makhachev"))

    def test_booth_chips_and_bar(self):
        chips = review_booth.numeric_chips_html(["24-3", "$1 million"])
        self.assertIn("24-3", chips)
        self.assertIn("chip", chips)
        bar = review_booth.semantic_bar_html(0.12)
        self.assertIn("12%", bar)
        self.assertIn("role='meter'", bar)
        self.assertIn("width:12%", bar)


class TestBoothWave4(unittest.TestCase):
    def test_sticky_bars_breakdown_pills_and_copy(self):
        html = review_booth.booth_html(
            run_id=71,
            grade="B (80)",
            authenticity="ok",
            cost="tts $0.00",
            cost_share="tts $0.00 · 0% of this render",
            uploads_left="YouTube: ~6 uploads left this reset",
            elevenlabs_chars="ElevenLabs: 99,000 chars leftover",
            numeric_chips=review_booth.numeric_chips_html(["29-1"]),
            semantic_bar=review_booth.semantic_bar_html(0.2),
            grade_breakdown=review_booth.grade_breakdown_html(
                [GradeComponent(name="hook", score=70, weight=0.28)]
            ),
            tts_cache_pill=review_booth.tts_cache_pill_html(True),
            thumb_badge=review_booth.thumb_badge_html("pillow"),
            signal_dots=review_booth.signal_dots_html(
                {"rss": {"status": "ok"}, "tiktok_trends": {"status": "unavailable"}}
            ),
            feed_stale=review_booth.feed_stale_banner_html("RSS feed stale: MMA Weekly"),
            render_gate="Overnight will not render: report card C (need >= B)",
            rpm_deferred="Deferred: trailing RPM $0.10/1k views < fully-loaded $0.31/video",
            yesterday_unsynced="Yesterday unsynced: 1 upload(s) still have no views.",
            unlisted_url="https://youtu.be/abc123XYZ00",
            dossier_uri="obsidian://open?vault=os&file=tapin/_runs/71_gta.md",
            postmortem_md=postmortem.as_markdown(
                {"run_id": 71, "topic": "GTA 6", "status": "drafted", "ungrounded_count": 0}
            ),
        )
        self.assertIn("id='quotabar'", html)
        self.assertIn("id='costbar'", html)
        self.assertIn("position: sticky", html)
        self.assertIn("button, input, select, textarea { font-size: 16px; }", html)
        self.assertIn("29-1", html)
        self.assertIn("20%", html)
        self.assertIn("hook 70", html)
        self.assertIn("TTS cache hit", html)
        self.assertIn("Thumb: Pillow", html)
        self.assertIn("class='dot ok'", html)
        self.assertIn("Feed health:", html)
        self.assertIn("Overnight will not render", html)
        self.assertIn("Deferred:", html)
        self.assertIn("Yesterday unsynced", html)
        self.assertIn("https://youtu.be/abc123XYZ00", html)
        self.assertIn("obsidian://open", html)
        self.assertIn("# Postmortem run #71", html)
        self.assertIn("Copy last unlisted URL", html)

    def test_thumb_flux_badge(self):
        self.assertIn("Flux", review_booth.thumb_badge_html("flux"))
        self.assertIn("Pillow", review_booth.thumb_badge_html("", thumbnail_cost=0))

    def test_last_watch_url_prefers_unlisted(self):
        rows = [
            SimpleNamespace(id=1, youtube_video_id="oldpub", privacy_status="public"),
            SimpleNamespace(id=2, youtube_video_id="held", privacy_status="unlisted"),
        ]
        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = rows
        with patch(
            "storage.repositories.publish_log.get_publish_log_repository",
            return_value=repo,
        ):
            url = review_booth.last_watch_url("tapin")
        self.assertEqual(url, "https://youtu.be/held")


class TestDossierUri(unittest.TestCase):
    def test_obsidian_uri_from_vault_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "MyVault"
            dest = vault / "tapin" / "_runs"
            dest.mkdir(parents=True)
            (dest / "12_gta-leak.md").write_text("# dossier\n", encoding="utf-8")
            with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": str(vault)}, clear=False):
                uri = vault_dossiers.dossier_obsidian_uri(12, "tapin")
        self.assertTrue(uri.startswith("obsidian://open?"))
        self.assertIn("MyVault", uri)
        self.assertIn("12_gta-leak.md", uri)

    def test_empty_vault_is_blank(self):
        with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": ""}, clear=False):
            self.assertEqual(vault_dossiers.dossier_obsidian_uri(1, "tapin"), "")


class TestGatesPlainEnglish(unittest.TestCase):
    def test_overnight_plain_reason(self):
        why = render_gate.overnight_plain_reason(
            {
                "hook_score": 20,
                "authenticity_score": 20,
                "authenticity_verdict": "ok",
                "ungrounded_count": 0,
            }
        )
        self.assertTrue(why.startswith("Overnight will not render:"))

    def test_yesterday_unsynced_copy(self):
        published = datetime.now(timezone.utc) - timedelta(days=1)
        row = SimpleNamespace(published_at=published, metrics_json="{}")
        text = metrics_gate.yesterday_unsynced_copy("tapin", rows=[row])
        self.assertIn("Yesterday unsynced", text)
        self.assertIn("learning loop", text)


class TestPostmortemMarkdown(unittest.TestCase):
    def test_as_markdown(self):
        md = postmortem.as_markdown(
            postmortem.assemble(
                run_id=9,
                trace={"selected_topic": "UFC 317", "status": "drafted", "signals": {}},
                quality={"ungrounded_count": 0},
                cost={"total": 0.31},
            )
        )
        self.assertIn("# Postmortem run #9", md)
        self.assertIn("UFC 317", md)


class TestTrayDomainAndQuietToasts(unittest.TestCase):
    def test_domain_chip_gta_and_ufc(self):
        self.assertEqual(win_notify.domain_chip_text("GTA 6 leak", "gaming"), "GTA")
        self.assertEqual(win_notify.domain_chip_text("Topuria vs Oliveira", "ufc"), "UFC")
        self.assertEqual(win_notify.domain_chip_text("Lakers trade", "nba"), "NBA")

    def test_chip_includes_domain_when_enabled(self):
        snap = {
            "youtube": {"used": 0, "limit": 10000, "remaining": 10000},
            "elevenlabs": {"chars_used": 0},
            "apify": {"exhausted": False},
        }
        with (
            patch.dict(os.environ, {"CONTENT_TRAY_DOMAIN": "true"}),
            patch("core.win_notify.last_domain_label", return_value="UFC"),
            patch("core.win_notify.last_grade_letter", return_value=""),
            patch("apis.youtube_quota.uploads_remaining", return_value=6),
        ):
            blob = " | ".join(win_notify.quota_chip_lines(snap))
        self.assertIn("Domain: UFC", blob)

    def test_quiet_hours_mutes_toast(self):
        win_notify._toasted.clear()
        with (
            patch.dict(
                os.environ,
                {
                    "CONTENT_TOAST": "true",
                    "CONTENT_TOAST_FORCE": "true",
                    "CONTENT_TOAST_DND": "true",
                },
            ),
            patch("core.win_notify._toast_powershell", return_value=True) as ps,
            patch(
                "core.publish_windows.quiet_hours_reason",
                return_value="quiet hours: 01:00-08:00 America/New_York",
            ),
        ):
            self.assertFalse(win_notify.toast("t", "b", key="wave4-dnd"))
        ps.assert_not_called()


class TestHtmlMinTypeAndSticky(unittest.TestCase):
    def test_css_floor_and_sticky_header(self):
        page = html_report.themed_page("T", "<p>x</p>")
        self.assertIn("font-size: 16px", page)
        self.assertIn("button, input, select, textarea { font-size: 16px; }", page)
        self.assertIn("position: sticky", page)
        self.assertIn("#quotabar", page)
        self.assertIn("#costbar", page)


class TestGradeBreakdownHelper(unittest.TestCase):
    def test_video_grade_components_render(self):
        grade = VideoGrade(
            score=80,
            letter="B",
            components=[
                GradeComponent(name="hook", score=70, weight=0.4),
                GradeComponent(name="grounding", score=90, weight=0.3),
                GradeComponent(name="authenticity", score=80, weight=0.3),
            ],
        )
        html = review_booth.grade_breakdown_html(grade.components)
        self.assertIn("hook 70", html)
        self.assertIn("grounding 90", html)
        self.assertIn("authenticity 80", html)


if __name__ == "__main__":
    unittest.main()
