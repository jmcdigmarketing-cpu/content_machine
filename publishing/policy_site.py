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
from collections.abc import Callable
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


# #1440 (S14.5, wave 145): Google's consent screen names the home page and the privacy page; a
# dead link there is a reason the publish click is refused or the app is pulled later. Each page's
# heading, from its template, says the right page answered - not a host's 404 page.
PAGE_HEADINGS = {
    "index.html": "",
    "privacy.html": "Privacy Policy",
    "terms.html": "Terms of Service",
    "data-deletion.html": "Data deletion",
}


def _fetch(url: str) -> tuple[int, str]:
    from urllib.request import Request, urlopen

    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (Content OS policy check)"})
    with urlopen(request, timeout=10) as response:  # the operator's own address
        return int(response.status), response.read(200_000).decode("utf-8", "replace")


def check_policy_site(
    base_url: str, *, fetch: Callable[[str], tuple[int, str]] | None = None
) -> list[tuple[str, bool, str]]:
    """(page, ok, why) for each of the four pages under `base_url`; never raises."""
    base = (base_url or "").strip().rstrip("/")
    out: list[tuple[str, bool, str]] = []
    for page in PAGES:
        url = f"{base}/{page}"
        try:
            status, body = (fetch or _fetch)(url)
        except Exception as exc:
            out.append((page, False, f"unreachable ({type(exc).__name__}: {str(exc)[:60]})"))
            continue
        heading = PAGE_HEADINGS.get(page, "")
        if status != 200:
            out.append((page, False, f"HTTP {status}"))
        elif "{{" in body:
            out.append((page, False, "a placeholder was left unfilled"))
        elif heading and heading.lower() not in body.lower():
            out.append((page, False, f'answers, but not with its "{heading}" page'))
        else:
            out.append((page, True, "ok"))
    return out


def policy_site_lines(
    base_url: str | None = None, *, fetch: Callable[[str], tuple[int, str]] | None = None
) -> list[str]:
    """`ops check-youtube`'s policy lines: each page live, or what to set."""
    base = (base_url if base_url is not None else os.getenv("POLICY_SITE_URL", "")).strip()
    if not base:
        return [
            "Policy site: POLICY_SITE_URL is not set - the address the consent screen names "
            "(docs/platform_publish_setup.md); set it and run this again before publishing the app"
        ]
    results = check_policy_site(base, fetch=fetch)
    good = sum(1 for _page, ok, _why in results if ok)
    lines = [f"Policy site: {good} of {len(results)} pages answer at {base}"]
    lines += [f"  {page}: {why}" for page, ok, why in results if not ok]
    return lines
