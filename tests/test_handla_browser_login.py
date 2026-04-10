"""Tests for Playwright cookie header helper."""

from ica_cli.handla_browser_login import playwright_cookies_to_header


def test_playwright_cookies_to_header_filters_host() -> None:
    cookies = [
        {"name": "a", "value": "1", "domain": ".handlaprivatkund.ica.se"},
        {"name": "b", "value": "2", "domain": "other.example.com"},
    ]
    h = playwright_cookies_to_header(cookies)
    assert "a=1" in h
    assert "b=2" not in h
