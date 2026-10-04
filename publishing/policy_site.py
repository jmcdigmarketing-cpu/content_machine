"""The privacy / terms / data-deletion site the platform apps link to (#956).

TikTok's app registration asks for a Privacy Policy URL and a Terms of Service URL, linked
from the website itself rather than behind a menu, on a site that describes the app. Meta's
Instagram app asks for a privacy policy and data-deletion instructions, and Google's OAuth
consent screen for a home page and a privacy policy. One static site serves all three.

`policy_pages/` holds the four pages as templates. `build_policy_site` fills in the
operator's shown name and contact address and writes the pages to a folder ready to upload
(GitHub Pages from a separate public repository, Cloudflare Pages or Netlify -
docs/platform_publish_setup.md). The name and address exist only in the built folder:
nothing personal is committed here.
"""

from __future__ import annotations

import html
import os
import re
from datetime import date

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "policy_pages")
PAGES = ("index.html", "privacy.html", "terms.html", "data-deletion.html")
DEFAULT_APP_NAME = "Content OS"

_EMAIL_RE = re.compile(r"^[^@\s<>\"']+@[^@\s<>\"']+\.[^@\s<>\"']+$")


def build_policy_site(
    out_dir: str,
    *,
    name: str,
    email: str,
    app_name: str = DEFAULT_APP_NAME,
    updated: str | None = None,
) -> list[str]:
    """Write the four pages into `out_dir`; the paths written.

    Raises ValueError, before writing anything, without a name or a usable address.
    """
    name = (name or "").strip()
    email = (email or "").strip()
    if not name:
        raise ValueError("a name to show on the pages is required (--name)")
    if not _EMAIL_RE.match(email):
        raise ValueError("a contact email address is required (--email)")
    stamp = (updated or date.today().isoformat()).strip()
    values = {
        "{{APP}}": html.escape((app_name or "").strip() or DEFAULT_APP_NAME),
        "{{NAME}}": html.escape(name),
        "{{EMAIL}}": html.escape(email),
        "{{UPDATED}}": html.escape(stamp),
        "{{YEAR}}": html.escape(stamp[:4]),
    }
    pages: dict[str, str] = {}
    for page in PAGES:
        with open(os.path.join(TEMPLATE_DIR, page), encoding="utf-8") as f:
            text = f.read()
        for key, value in values.items():
            text = text.replace(key, value)
        if "{{" in text:
            raise ValueError(f"{page}: a placeholder was left unfilled")
        pages[page] = text
    os.makedirs(out_dir, exist_ok=True)
    written: list[str] = []
    for page, text in pages.items():
        path = os.path.join(out_dir, page)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        written.append(path)
    return written
