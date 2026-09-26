"""The agent mailbox stays wired at BOTH ends.

The failure this guards against is not a wrong hand-off — it is a hand-off that was
never reachable. A mailbox can exist, be referenced from the router, and still be
invisible to the agent that needed it, because the file that agent *actually* auto-loads
never named it. Two passes were then spent writing "the other agent still hasn't
replied" into an address that had never been published. The empty slot was evidence
about the wiring, not about the other agent.

So each test below asserts a ONE-HOP path: the file an agent loads without being told
to names `docs/handoff.md` itself, rather than pointing at a file that points at it.

Deliberately NOT tested: whether the slots are fresh, or true. A staleness gate reddens
because nobody worked the weekend, and a gate that cries wolf gets ignored — the same
failure as any always-on warning (decisions §24). These tests can only stop the channel
going one-way again.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAILBOX = ROOT / "docs" / "handoff.md"

# The file each agent loads on its own, with no instruction to do so.
CURSOR_ALWAYS_ON = ROOT / ".cursor" / "rules" / "content-machine.mdc"
CLAUDE_ALWAYS_ON = ROOT / "CLAUDE.md"
ROUTER = ROOT / "AGENTS.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestMailboxExists(unittest.TestCase):
    def test_both_slots_are_present(self):
        body = _read(MAILBOX)
        self.assertIn("## Slot — Claude Code", body)
        self.assertIn("## Slot — Cursor", body)

    def test_it_tells_you_to_verify_against_git(self):
        """The prose must be a summary of something checkable, not the only record."""
        body = _read(MAILBOX)
        self.assertIn("git log", body)
        self.assertIn("git status", body)

    def test_it_stays_a_mailbox_not_a_second_archive(self):
        """handoff_synopsis.md is 900+ lines; nobody reads that at the start of a
        session. A mailbox that grows into an archive stops being read at all."""
        lines = _read(MAILBOX).splitlines()
        self.assertLess(len(lines), 120, f"handoff.md is {len(lines)} lines — trim it")


class TestBothEndsAreWiredInOneHop(unittest.TestCase):
    def test_cursor_always_on_rule_names_the_mailbox_itself(self):
        """`.cursor/rules/*.mdc` with alwaysApply is what Cursor actually loads. A
        mailbox reachable only via AGENTS.md is two hops and was never read."""
        body = _read(CURSOR_ALWAYS_ON)
        self.assertIn("alwaysApply: true", body)
        self.assertIn("docs/handoff.md", body)

    def test_claude_always_on_file_names_the_mailbox_itself(self):
        self.assertIn("docs/handoff.md", _read(CLAUDE_ALWAYS_ON))

    def test_the_router_lists_it_too(self):
        self.assertIn("docs/handoff.md", _read(ROUTER))

    def test_the_mailbox_is_named_before_the_rest_of_the_rules(self):
        """Buried on line 400 is the same as absent. It must come before the body."""
        for path in (CURSOR_ALWAYS_ON, CLAUDE_ALWAYS_ON):
            with self.subTest(file=path.name):
                lines = _read(path).splitlines()
                hit = next(i for i, ln in enumerate(lines) if "docs/handoff.md" in ln)
                self.assertLess(hit, 40, f"{path.name} mentions the mailbox at line {hit}")


class TestWritingTheSlotIsPartOfDone(unittest.TestCase):
    """A checklist Cursor follows that has no 'write your slot' step is why the slot
    stayed empty. The instruction has to travel with the definition of done."""

    def test_done_requires_writing_the_slot(self):
        body = _read(CURSOR_ALWAYS_ON)
        done = body[body.index("## Definition of done") :]
        self.assertIn("handoff.md", done)

    def test_done_requires_committing_your_own_work(self):
        """Four waves have arrived as uncommitted files for someone else to find, so
        CI and a fresh clone saw nothing."""
        body = _read(CURSOR_ALWAYS_ON)
        done = body[body.index("## Definition of done") :]
        self.assertIn("committed", done.lower())


class TestNoSecondTestCommand(unittest.TestCase):
    """A second, divergent test command is how a stale count survives: the agent runs
    the one that hides the summary and reports a number nobody can reproduce. CI runs
    `python -m unittest discover -s tests -t .` and the `-t .` is load-bearing."""

    AGENT_FACING = (
        "CLAUDE.md",
        "AGENTS.md",
        "tests/CLAUDE.md",
        "apis/CLAUDE.md",
        ".cursor/rules/content-machine.mdc",
        "docs/handoff.md",
    )

    def test_no_agent_facing_file_offers_a_quiet_pytest_run(self):
        offenders = []
        for rel in self.AGENT_FACING:
            path = ROOT / rel
            if not path.exists():
                continue
            for n, line in enumerate(_read(path).splitlines(), 1):
                if re.search(r"pytest\s+(-\S*q|--quiet)", line):
                    offenders.append(f"{rel}:{n}: {line.strip()}")
        self.assertEqual(offenders, [], "; ".join(offenders))

    def test_the_canonical_command_keeps_its_load_bearing_flag(self):
        body = _read(ROOT / "CLAUDE.md")
        self.assertIn("python -m unittest discover -s tests -t .", body)


class TestAgentCommsReport(unittest.TestCase):
    """`ops agents` is the one command that reads both provenance channels. It must
    survive a repo with no git, and must not lie when a slot is empty."""

    def test_render_names_both_agents_and_the_mailbox(self):
        from core.agent_comms import render

        body = render()
        self.assertIn("Claude", body)
        self.assertIn("Cursor", body)
        self.assertIn("docs/handoff.md", body)

    def test_it_survives_git_being_unavailable(self):
        from unittest.mock import patch

        from core import agent_comms

        with patch.object(agent_comms, "_git", return_value=""):
            body = agent_comms.render()
        self.assertIn("Agent hand-off", body)

    def test_an_unwritten_slot_reports_never_written(self):
        from core.agent_comms import slots

        found = {s["agent"]: s for s in slots()}
        self.assertIn("Cursor", found)
        self.assertIn("Claude Code", found)

    def test_the_verb_is_registered(self):
        from scripts.ops import COMMANDS

        self.assertIn("agents", COMMANDS)

    def test_the_report_is_cp1252_safe(self):
        """Candidate 250: operator dumps must encode on a Windows console."""
        from core.agent_comms import render

        render().encode("cp1252")

    def test_a_commit_subject_with_a_glyph_cannot_break_the_report(self):
        """Wave 32 found main's HEAD subject carried a U+2192 arrow, which reached
        the report verbatim through `git log` and failed the encode above. Git
        output is not this module's to keep ASCII; the report must be."""
        from unittest.mock import patch

        from core import agent_comms

        def _git(*args):
            if args[0] == "log" and "-1" in args:
                return "abc1234 Grand audit: the before\u2192after snapshot \u2014 done"
            return ""

        with patch.object(agent_comms, "_git", side_effect=_git):
            text = agent_comms.render()
        text.encode("cp1252")
        self.assertIn("before->after", text)


if __name__ == "__main__":
    unittest.main()
