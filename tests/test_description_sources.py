"""The public `Sources:` block must not cite notes the video is not about.

`DESCRIPTION_SOURCES` defaults on and appends a `Sources:` block to the YouTube
description, built from operator-pasted URLs plus vault `source_url`. Wave 4 collected
the vault half with the default loose relevance — the same gate that on live-run 71
attached four Marvel Rivals / SEGA bullets to a GTA 6 leak story, because "wolverine"
is a distinctive token that names two different subjects.

The description is a public artifact, so an off-topic citation is a visible error
rather than a bit of prompt noise. The vault half now requires a topic-distinctive
token; operator-pasted URLs are untouched, having been chosen for this run.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.description_extras import collect_source_urls, format_sources_block

ON_TOPIC = """---
tier: link
channel: tapin
source: https://example.com/gta6-subpoenas
verified_at: 2026-08-22
---

- Take-Two filed subpoenas against Microsoft and Discord over the Grand Theft Auto leak.
"""

OFF_TOPIC = """---
tier: link
channel: tapin
source: https://example.com/marvel-rivals-season-9
verified_at: 2026-08-20
---

- Marvel Rivals season 9 adds a Wolverine costume from the Horseman of Death era.
"""


class _Vault:
    """Temp vault with the two notes above, wired through OBSIDIAN_VAULT_PATH."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name) / "vault" / "tapin" / "_sources"
        root.mkdir(parents=True)
        (root / "gta6.md").write_text(ON_TOPIC, encoding="utf-8")
        (root / "rivals.md").write_text(OFF_TOPIC, encoding="utf-8")
        self.env = patch.dict(
            os.environ,
            {"OBSIDIAN_VAULT_PATH": str(Path(self.tmp.name) / "vault")},
            clear=False,
        )
        self.env.start()
        return self

    def __exit__(self, *exc):
        self.env.stop()
        self.tmp.cleanup()
        return False


TOPIC = "GTA 6 leak forces Take-Two to subpoena Microsoft and Discord"


class TestVaultRelevance(unittest.TestCase):
    def test_on_topic_source_is_collected(self):
        with _Vault():
            urls = collect_source_urls(channel_id="tapin", topic=TOPIC)
        self.assertIn("https://example.com/gta6-subpoenas", urls)

    def test_off_topic_source_is_not_published(self):
        with _Vault():
            urls = collect_source_urls(channel_id="tapin", topic=TOPIC)
        self.assertNotIn("https://example.com/marvel-rivals-season-9", urls)

    def test_competing_franchise_no_longer_attaches_to_gta_wolverine_topic(self):
        """Inverted 2026-08-26 when the competing-franchise gate landed.

        Run 71's angle shared 'Wolverine' with a Marvel Rivals vault bullet. The
        distinctiveness gate could not tell them apart; `anchor_families` now drops
        the Rivals note because the topic is GTA and the note names a different
        franchise. Remaining gap: a wolverine-only bullet with no franchise string
        — asserted in tests/test_vault_subject_relevance.py.
        """
        with _Vault():
            urls = collect_source_urls(
                channel_id="tapin",
                topic="GTA 6 Leak and Wolverine Rage Signal a Cultural Backlash",
            )
        self.assertNotIn("https://example.com/marvel-rivals-season-9", urls)


class TestOperatorUrlsAreUnaffected(unittest.TestCase):
    """A URL the operator pasted for this run is theirs to publish."""

    def test_pasted_url_is_kept(self):
        urls = collect_source_urls(
            key_facts=["See https://www.msn.com/en-us/money/take-two-subpoenas for detail."]
        )
        self.assertEqual(urls, ["https://www.msn.com/en-us/money/take-two-subpoenas"])

    def test_explicit_urls_win_without_a_vault(self):
        urls = collect_source_urls(extra_urls=["https://example.com/a"])
        self.assertEqual(urls, ["https://example.com/a"])

    def test_duplicates_collapse_case_insensitively(self):
        urls = collect_source_urls(
            extra_urls=["https://example.com/A", "https://EXAMPLE.com/A"],
        )
        self.assertEqual(len(urls), 1)

    def test_non_http_is_ignored(self):
        self.assertEqual(collect_source_urls(extra_urls=["ftp://x/y", "not a url"]), [])

    def test_cap_is_eight(self):
        urls = collect_source_urls(extra_urls=[f"https://example.com/{i}" for i in range(20)])
        self.assertEqual(len(urls), 8)


class TestBlockRendering(unittest.TestCase):
    def test_empty_renders_nothing(self):
        self.assertEqual(format_sources_block([]), "")
        self.assertEqual(format_sources_block(None), "")

    def test_block_is_labelled(self):
        block = format_sources_block(["https://example.com/a"])
        self.assertTrue(block.startswith("Sources:"))
        self.assertIn("https://example.com/a", block)


if __name__ == "__main__":
    unittest.main()
