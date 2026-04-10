"""Optional Playwright flow to capture Handla web session cookies."""

from __future__ import annotations

import sys
from typing import Any


def playwright_cookies_to_header(cookies: list[dict[str, Any]]) -> str:
    """Build Cookie header from Playwright cookie list for Handla host."""
    parts: list[str] = []
    for c in cookies:
        dom = (c.get("domain") or "").lstrip(".").lower()
        if dom.endswith("handlaprivatkund.ica.se"):
            name = c.get("name", "")
            value = c.get("value", "")
            if name:
                parts.append(f"{name}={value}")
    return "; ".join(parts)


def run_handla_browser_login(store_id: str) -> str:
    """
    Open a headed browser for Handla; user logs in; return Cookie header
    string.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        py = sys.executable
        msg = (
            "Playwright is not installed for the Python that runs ica. "
            "The `playwright` shell command can work while this "
            "interpreter still lacks the package. "
            f"Run: {py} -m pip install playwright && "
            f"{py} -m playwright install chromium. "
            "If ica is from pipx: pipx inject ica-cli playwright"
        )
        raise RuntimeError(msg) from e

    from ica_cli.handla_cart import handla_store_home_url

    start_url = handla_store_home_url(store_id)
    sys.stderr.write(
        "Opening browser. Log in to Handla, then focus this terminal.\n"
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(start_url, wait_until="domcontentloaded", timeout=120_000)
        try:
            input("Press Enter after you see your store (logged in)… ")
        except EOFError as err:
            browser.close()
            raise RuntimeError(
                "stdin closed; cannot complete browser login"
            ) from err
        cookies = context.cookies()
        browser.close()

    header = playwright_cookies_to_header(cookies)
    if not header.strip():
        raise RuntimeError(
            "No handlaprivatkund.ica.se cookies captured. "
            "Finish login and wait until the store page loads."
        )
    return header
