"""#374: the premium tier is for the hook only.

The whole script, description and tags go out on one premium call. The first two
sentences are what the retention cliff is, so those stay premium and the rest of
the script is a cheap call. SCRIPT_BODY_TIER=premium is the old single call.
"""

from __future__ import annotations

import logging
import os
import unittest
from unittest.mock import patch

HOOK = "He lost the belt. Nobody expected it."
BODY = f"{HOOK} The division changed after that one loss and the rest of the card moved on."


class HookTierTests(unittest.TestCase):
    def _generate(self, fake, *, body_tier: str | None = None):
        from core import content_engine as ce

        env = {
            "GROUNDING_REGEN_ENABLED": "false",
            "HOOK_REGEN_ENABLED": "false",
            "INSIGHT_INJECTION_ENABLED": "false",
            "CLAIM_REGEN_ENABLED": "false",
            "READ_ALOUD_REWRITE": "false",
        }
        if body_tier is not None:
            env["SCRIPT_BODY_TIER"] = body_tier
        warnings: list[str] = []

        class _Grab(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                if record.levelno >= logging.WARNING:
                    warnings.append(record.getMessage())

        handler = _Grab()
        logger = logging.getLogger("content_machine.core.content_engine")
        logger.addHandler(handler)
        try:
            with (
                patch.dict(os.environ, env, clear=False),
                patch.object(ce, "complete_json", side_effect=fake),
                patch.object(ce, "enrich_facts", return_value=""),
                patch.object(ce, "find_ungrounded_entities", return_value=[]),
                patch("core.claim_verifier.verify_claims", return_value=None),
                patch("core.title_generator.generate_title", return_value="The belt"),
            ):
                package = ce.generate_content_package(
                    "UFC title fight",
                    {},
                    (8, 200),
                    "2026-10-10",
                    channel_id="tapin",
                    length_choice="1",
                )
        finally:
            logger.removeHandler(handler)
        return package, warnings

    def test_the_hook_is_premium_and_the_body_is_cheap(self):
        tiers: list[str] = []

        def fake(*_args, **kwargs):
            tiers.append(str(kwargs.get("tier")))
            stage = kwargs.get("stage")
            if stage == "script_hook":
                return {"hook": HOOK}
            if stage == "script_body":
                return {"script": BODY, "description": "d", "tags": ["ufc"]}
            return {"script": BODY, "description": "d", "tags": ["ufc"]}

        package, warnings = self._generate(fake)
        self.assertEqual(tiers[:2], ["premium", "cheap"])
        self.assertTrue(package["script"].startswith(HOOK))
        self.assertFalse(any("Premium hook was empty" in line for line in warnings))

    def test_premium_body_tier_is_one_call(self):
        tiers: list[str] = []

        def fake(*_args, **kwargs):
            tiers.append(str(kwargs.get("tier")))
            return {
                "script": "One premium call wrote the whole script here. Second sentence.",
                "description": "d",
                "tags": ["ufc"],
            }

        package, _warnings = self._generate(fake, body_tier="premium")
        self.assertEqual(tiers, ["premium"])
        self.assertTrue(package["script"].startswith("One premium call"))

    def test_an_empty_hook_warns_and_falls_back(self):
        tiers: list[str] = []

        def fake(*_args, **kwargs):
            tiers.append(str(kwargs.get("tier")))
            if kwargs.get("stage") == "script_hook":
                return {"hook": ""}
            return {
                "script": "The fallback premium script starts here. It has two sentences.",
                "description": "d",
                "tags": ["ufc"],
            }

        package, warnings = self._generate(fake)
        self.assertEqual(tiers, ["premium", "premium"])
        self.assertTrue(any("Premium hook was empty" in line for line in warnings))
        self.assertTrue(package["script"].startswith("The fallback premium script"))


if __name__ == "__main__":
    unittest.main()
