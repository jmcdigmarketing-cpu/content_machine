"""#625. Compare live signatures to the doubles tests actually patch."""

from __future__ import annotations

import inspect
import re
from pathlib import Path


def audit_known_doubles() -> list[str]:
    issues: list[str] = []
    from apis.free_backends import _full_one

    params = list(inspect.signature(_full_one).parameters)
    if params != ["url", "log"]:
        issues.append(f"_full_one params {params} != ['url', 'log']")

    from tests.test_tts_edge import _FakeCommunicate

    fake = inspect.signature(_FakeCommunicate.__init__).parameters
    if "boundary" not in fake:
        issues.append("edge Communicate fake is missing boundary=")
    elif fake["boundary"].kind != inspect.Parameter.KEYWORD_ONLY:
        issues.append("edge Communicate fake boundary is not keyword-only")
    try:
        import edge_tts

        real = inspect.signature(edge_tts.Communicate.__init__).parameters
        if "boundary" not in real:
            issues.append("live edge_tts.Communicate has no boundary=")
    except ImportError:
        pass

    root = Path(__file__).resolve().parent
    triple = re.compile(r'"{3}(.*?)"{3}|\'{3}(.*?)\'{3}', re.S)
    for path in root.glob("test_*.py"):
        text = path.read_text(encoding="utf-8")
        for match in triple.finditer(text):
            blob = match.group(1) or match.group(2) or ""
            compact = blob.replace(" ", "")
            if "tags:" not in blob or "[facts]" not in compact:
                continue
            dated = "verified_at:" in blob or "expires:" in blob or "date:" in blob
            if not dated:
                issues.append(f"undated vault fixture in {path.name}")
    return issues
