"""#956: the privacy / terms / data-deletion site the platform apps link to (operator, 2026-10-04).

TikTok's app registration wants a Privacy Policy URL and a Terms of Service URL, both linked
from the website itself rather than behind a menu, and the site must describe the app. Meta's
Instagram app wants a privacy policy and data-deletion instructions, and Google's OAuth consent
screen a home page and a privacy policy. One static site serves all three.

The pages are templates: the operator's shown name and contact address are filled in only when
`ops policy-site` builds them into a folder, so no name or address is ever committed here.
"""

from __future__ import annotations

import io
import os
import re
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout

PAGES = ("index.html", "privacy.html", "terms.html", "data-deletion.html")


def _build(out, **kw):
    from publishing.policy_site import build_policy_site

    values = {"name": "Test Operator", "email": "ops@example.com", "updated": "2026-10-04"}
    values.update(kw)
    return build_policy_site(out, **values)


def _read(out, page):
    with open(os.path.join(out, page), encoding="utf-8") as f:
        return f.read()


class TestPolicySiteBuild(unittest.TestCase):
    def test_writes_the_four_pages(self):
        with tempfile.TemporaryDirectory() as out:
            written = _build(out)
            self.assertEqual(sorted(os.path.basename(p) for p in written), sorted(PAGES))
            for page in PAGES:
                self.assertTrue(os.path.isfile(os.path.join(out, page)), page)

    def test_refuses_without_a_name_or_an_address(self):
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaises(ValueError):
                _build(out, name="")
            with self.assertRaises(ValueError):
                _build(out, email="")
            with self.assertRaises(ValueError):
                _build(out, email="not an address")
            self.assertEqual(os.listdir(out), [])

    def test_every_placeholder_is_filled_and_values_are_escaped(self):
        with tempfile.TemporaryDirectory() as out:
            _build(out, name="A & B <Studio>")
            for page in PAGES:
                text = _read(out, page)
                self.assertNotIn("{{", text, page)
                self.assertNotIn("<Studio>", text, page)
            index = _read(out, "index.html")
            self.assertIn("A &amp; B &lt;Studio&gt;", index)
            self.assertIn('href="mailto:ops@example.com"', index)

    def test_the_home_page_links_each_policy_directly(self):
        """TikTok: the links must be visible on the site without opening a menu."""
        with tempfile.TemporaryDirectory() as out:
            _build(out)
            index = _read(out, "index.html")
            for page in ("privacy.html", "terms.html", "data-deletion.html"):
                self.assertIn(f'href="{page}"', index)
            self.assertNotIn("<details", index)
            self.assertNotIn("display:none", index.replace(" ", ""))
            self.assertNotIn("hidden", index)

    def test_the_privacy_policy_covers_what_the_platforms_ask_for(self):
        with tempfile.TemporaryDirectory() as out:
            _build(out)
            text = re.sub(r"\s+", " ", _read(out, "privacy.html"))
            for needed in (
                "YouTube",
                "TikTok",
                "Instagram",
                "How the information is used",
                "Where it is stored",
                "Sharing",
                "AI",
                "Retention",
                "Deleting your data",
                "Children",
                "Changes",
                "Contact",
                "2026-10-04",
                "https://www.youtube.com/t/terms",
                "https://policies.google.com/privacy",
                "https://security.google.com/settings/security/permissions",
                "data-deletion.html",
            ):
                self.assertIn(needed, text, needed)

    def test_the_policy_names_what_reaches_an_ai_provider(self):
        """Checked against the code: the script prompt carries viewers' comment questions
        (`core/signal_facts`) and the channel's own titles with their views
        (`core/success/winners.winners_block`), so the page must say so."""
        with tempfile.TemporaryDirectory() as out:
            _build(out)
            text = re.sub(r"\s+", " ", _read(out, "privacy.html")).lower()
            self.assertIn("questions", text)
            self.assertIn("titles and view counts", text)
            self.assertIn("never include sign-in tokens", text)

    def test_the_deletion_page_gives_steps_and_a_deadline(self):
        with tempfile.TemporaryDirectory() as out:
            _build(out)
            text = re.sub(r"\s+", " ", _read(out, "data-deletion.html"))
            self.assertIn("mailto:ops@example.com", text)
            self.assertIn("30 days", text)
            self.assertIn("<ol>", text)

    def test_terms_name_the_platform_terms(self):
        with tempfile.TemporaryDirectory() as out:
            _build(out)
            text = _read(out, "terms.html")
            for needed in ("TikTok", "Instagram", "YouTube", "warranty", "Contact"):
                self.assertIn(needed, text, needed)


class TestTemplatesHoldNothingPersonal(unittest.TestCase):
    def test_no_address_or_name_is_committed(self):
        from publishing.policy_site import TEMPLATE_DIR

        names = sorted(os.listdir(TEMPLATE_DIR))
        self.assertEqual(sorted(n for n in names if n.endswith(".html")), sorted(PAGES))
        for name in names:
            with open(os.path.join(TEMPLATE_DIR, name), encoding="utf-8") as f:
                text = f.read()
            self.assertIsNone(
                re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text), f"{name} holds an address"
            )
            self.assertNotIn("gmail", text.lower(), name)


class TestPolicySiteCommand(unittest.TestCase):
    def _args(self, **kw):
        values = {"channel": "tapin", "name": "", "email": "", "output_dir": ""}
        values.update(kw)
        return Namespace(**values)

    def test_the_command_refuses_without_values(self):
        from scripts.ops import COMMANDS

        self.assertIn("policy-site", COMMANDS)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = COMMANDS["policy-site"][1](self._args())
        self.assertNotEqual(code, 0)
        self.assertIn("--name", buf.getvalue())

    def test_the_command_builds_into_the_folder(self):
        from scripts.ops import COMMANDS

        with tempfile.TemporaryDirectory() as out:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = COMMANDS["policy-site"][1](
                    self._args(name="Test Operator", email="ops@example.com", output_dir=out)
                )
            self.assertEqual(code, 0)
            self.assertEqual(sorted(os.listdir(out)), sorted(PAGES))
            self.assertIn("index.html", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
