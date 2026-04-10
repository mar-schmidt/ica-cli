"""Handla Online cart (web cookie + CSRF) and anonymous product search."""

from __future__ import annotations

import logging
import os
import random
import re
import time
from typing import Any, Callable
from urllib.parse import urlencode

import requests
from requests.cookies import RequestsCookieJar

from ica_cli.const import HANDLA_PRIVATKUND_HOST
from ica_cli.handla_web_store import (
    clear_cached_handla_csrf_file,
    handla_cookie_persist_enabled,
    load_cached_handla_csrf,
    persist_handla_web_derived,
)

_LOGGER = logging.getLogger(__name__)
_HANDLA_COOKIE_DOMAIN = ".handlaprivatkund.ica.se"
_SEARCH_RETRY_MAX_WAIT_SECONDS = 300.0
_SEARCH_RETRY_BASE_DELAY_SECONDS = 1.0
_SEARCH_RETRY_MAX_DELAY_SECONDS = 30.0

# Handla/WAF often returns 403 for default python-requests User-Agent.
_HANDLA_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Safari/605.1.15"
)

_CSRF_TOKEN_RE = re.compile(
    r'"csrf"\s*:\s*\{\s*"token"\s*:\s*"'
    r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"',
    re.IGNORECASE,
)


class HandlaCsrfError(RuntimeError):
    """Could not extract CSRF token from Handla store HTML."""


class HandlaResponseFormatError(RuntimeError):
    """Handla response body could not be decoded as JSON."""

    def __init__(
        self,
        *,
        status_code: int | None,
        content_type: str,
        body_preview: str,
    ) -> None:
        self.status_code = status_code
        self.content_type = content_type
        self.body_preview = body_preview
        super().__init__(
            "Handla response was not valid JSON "
            f"(status={status_code}, content_type={content_type or 'unknown'})."
        )

    def as_details(self) -> dict[str, Any]:
        details: dict[str, Any] = {}
        if self.content_type:
            details["content_type"] = self.content_type
        if self.body_preview:
            details["body_preview"] = self.body_preview
        return details


def handla_store_home_url(store_id: str) -> str:
    root = HANDLA_PRIVATKUND_HOST.rstrip("/")
    sid = store_id.strip().rstrip("/")
    return f"{root}/stores/{sid}/"


def _handla_store_origin_referer(store_id: str) -> tuple[str, str]:
    root = HANDLA_PRIVATKUND_HOST.rstrip("/")
    sid = store_id.strip().rstrip("/")
    return root, f"{root}/stores/{sid}/"


def _handla_public_get_headers(store_id: str) -> dict[str, str]:
    """Headers for catalog GETs (no Bearer). WAF often 403s python-requests."""
    _origin, referer = _handla_store_origin_referer(store_id)
    return {
        "Accept": "application/json",
        "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
        "Referer": referer,
        "User-Agent": _HANDLA_BROWSER_UA,
    }


def _handla_cart_post_headers(store_id: str) -> dict[str, str]:
    """Browser-like POST context for cart mutations."""
    origin, referer = _handla_store_origin_referer(store_id)
    return {
        "Origin": origin,
        "Referer": referer,
        "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
        "Content-Type": "application/json",
    }


def handla_store_base(store_id: str) -> str:
    sid = store_id.strip().rstrip("/")
    return f"{HANDLA_PRIVATKUND_HOST}/stores/{sid}/"


def load_handla_store_id() -> str | None:
    s = os.environ.get("ICA_CLI_HANDLA_STORE_ID", "").strip()
    return s or None


def handla_http_error_details(exc: requests.HTTPError) -> dict[str, Any]:
    """Response hints for CLI JSON (WAF HTML vs API JSON on 403)."""
    r = exc.response
    if r is None:
        return {}
    out: dict[str, Any] = {}
    ct = r.headers.get("Content-Type", "")
    if ct:
        out["content_type"] = ct.split(";")[0].strip()
    text = (r.text or "").strip()
    if text:
        out["body_preview"] = text[:800]
    return out


def _response_content_type(response: requests.Response) -> str:
    ct = response.headers.get("Content-Type", "")
    return ct.split(";")[0].strip() if ct else ""


def _parse_json_response(response: requests.Response) -> Any:
    response.raise_for_status()
    try:
        return response.json()
    except ValueError as exc:
        body_preview = (response.text or "").strip()[:800]
        raise HandlaResponseFormatError(
            status_code=response.status_code,
            content_type=_response_content_type(response),
            body_preview=body_preview,
        ) from exc


def _parse_retry_after_seconds(response: requests.Response) -> float | None:
    raw = (response.headers.get("Retry-After") or "").strip()
    if not raw:
        return None
    try:
        seconds = float(raw)
    except ValueError:
        return None
    if seconds <= 0:
        return None
    return seconds


def handla_active_cart_url(store_id: str) -> str:
    """GET active cart (no trailing slash)."""
    sid = store_id.strip().rstrip("/")
    root = HANDLA_PRIVATKUND_HOST.rstrip("/")
    return f"{root}/stores/{sid}/api/cart/v1/carts/active"


def parse_csrf_from_handla_html(html: str) -> str | None:
    m = _CSRF_TOKEN_RE.search(html)
    return m.group(1) if m else None


def apply_cookie_header_to_session(
    session: requests.Session,
    cookie_header: str,
) -> None:
    """Load a browser Cookie header string into the session jar."""
    session.cookies.clear()
    for part in cookie_header.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        session.cookies.set(
            name.strip(),
            value.strip(),
            domain=_HANDLA_COOKIE_DOMAIN,
            path="/",
        )


def cookie_header_from_session(session: requests.Session) -> str:
    """Serialize session cookies for handla_web.json (Set-Cookie merge)."""
    jar = session.cookies
    if not isinstance(jar, RequestsCookieJar):
        return ""
    return "; ".join(f"{c.name}={c.value}" for c in jar)


def _persist_handla_session_state(
    session: requests.Session,
    *,
    csrf_token: str | None = None,
    clear_csrf: bool = False,
) -> None:
    if not handla_cookie_persist_enabled():
        return
    hdr = cookie_header_from_session(session)
    if not hdr.strip():
        return
    persist_handla_web_derived(
        cookie_header=hdr,
        csrf_token=csrf_token,
        clear_csrf=clear_csrf,
    )


def handla_store_page_headers(cookie_header: str) -> dict[str, str]:
    """GET headers for Handla HTML pages (CSRF bootstrap)."""
    return {
        "Cookie": cookie_header.strip(),
        "User-Agent": _HANDLA_BROWSER_UA,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
    }


def _handla_html_bootstrap_headers() -> dict[str, str]:
    """GET store HTML (CSRF) without a separate Cookie header (use jar)."""
    return {
        "User-Agent": _HANDLA_BROWSER_UA,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
    }


def fetch_handla_csrf_for_session(
    session: requests.Session,
    store_id: str,
    *,
    timeout: int = 60,
) -> str:
    """GET store home HTML using session cookies; return CSRF token."""
    url = handla_store_home_url(store_id)
    headers = _handla_html_bootstrap_headers()
    _LOGGER.debug("GET %s for CSRF (session jar)", url)
    r = session.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    token = parse_csrf_from_handla_html(r.text)
    if not token:
        raise HandlaCsrfError(
            "Could not find CSRF token in Handla store HTML "
            "(session cookie may be invalid or page layout changed)."
        )
    return token


def fetch_handla_csrf(
    cookie_header: str,
    store_id: str,
    *,
    timeout: int = 60,
) -> str:
    """GET store home HTML; return session CSRF token."""
    url = handla_store_home_url(store_id)
    headers = handla_store_page_headers(cookie_header)
    _LOGGER.debug("GET %s for CSRF", url)
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    token = parse_csrf_from_handla_html(r.text)
    if not token:
        raise HandlaCsrfError(
            "Could not find CSRF token in Handla store HTML "
            "(session cookie may be invalid or page layout changed)."
        )
    return token


class HandlaWebCartClient:
    """
    Cart on handlaprivatkund.ica.se using browser session cookies.

    Mutations use X-CSRF-TOKEN (cached in handla_web.json; refreshed on
    miss or 403). Session cookie jar merges Set-Cookie (e.g. ALB stickiness).
    """

    def __init__(
        self,
        store_id: str,
        cookie_header: str,
        session: requests.Session | None = None,
    ) -> None:
        self._store_id = store_id.strip()
        self._base = handla_store_base(self._store_id)
        self._session = session or requests.Session()
        apply_cookie_header_to_session(
            self._session,
            cookie_header.strip(),
        )
        self._session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": _HANDLA_BROWSER_UA,
            }
        )

    def _url(self, path: str) -> str:
        p = path.lstrip("/")
        return f"{self._base}{p}"

    def _csrf_for_mutation(self) -> str:
        cached = load_cached_handla_csrf()
        if cached:
            return cached
        token = fetch_handla_csrf_for_session(self._session, self._store_id)
        _persist_handla_session_state(self._session, csrf_token=token)
        return token

    def get_active_cart(self) -> Any:
        url = self._url("api/cart/v1/carts/active")
        _LOGGER.debug("GET %s", url)
        r = self._session.get(url, timeout=60)
        try:
            return _parse_json_response(r)
        finally:
            _persist_handla_session_state(self._session)

    def apply_quantity(self, updates: list[dict[str, Any]]) -> Any:
        url = self._url("api/cart/v1/carts/active/apply-quantity")
        for attempt in range(2):
            csrf = self._csrf_for_mutation()
            hdrs = {
                **_handla_cart_post_headers(self._store_id),
                "X-CSRF-TOKEN": csrf,
            }
            _LOGGER.debug("POST %s items=%s", url, len(updates))
            r = self._session.post(
                url,
                json=updates,
                headers=hdrs,
                timeout=60,
            )
            if r.status_code == 403 and attempt == 0:
                _persist_handla_session_state(self._session)
                clear_cached_handla_csrf_file()
                continue
            out = _parse_json_response(r)
            _persist_handla_session_state(self._session, csrf_token=csrf)
            return out

    def search_products(
        self,
        query: str,
        *,
        max_page_size: int = 50,
        max_decorate: int = 50,
    ) -> Any:
        return handla_search_products(
            self._store_id,
            query,
            max_page_size=max_page_size,
            max_decorate=max_decorate,
        )


def handla_search_products(
    store_id: str,
    query: str,
    *,
    max_page_size: int = 50,
    max_decorate: int = 50,
    max_wait_seconds: float = _SEARCH_RETRY_MAX_WAIT_SECONDS,
    retry_wait_callback: Callable[[int, float, float, float], None]
    | None = None,
) -> Any:
    """Anonymous product search (no cookie)."""
    params = {
        "q": query,
        "includeAdditionalPageInfo": "true",
        "maxPageSize": str(max_page_size),
        "maxProductsToDecorate": str(max_decorate),
        "tag": "web",
    }
    path = (
        "api/webproductpagews/v6/product-pages/search?"
        f"{urlencode(params)}"
    )
    base = handla_store_base(store_id)
    url = f"{base}{path}"
    _LOGGER.debug("GET search %s", url[:120])
    headers = _handla_public_get_headers(store_id)
    started = time.monotonic()
    attempt = 1

    while True:
        r = requests.get(url, headers=headers, timeout=60)
        if r.status_code != 202:
            return _parse_json_response(r)

        elapsed = max(0.0, time.monotonic() - started)
        remaining = max(0.0, max_wait_seconds - elapsed)
        if remaining <= 0:
            raise requests.HTTPError(
                "Search remained in 202 Accepted state after retry budget.",
                response=r,
            )

        retry_after = _parse_retry_after_seconds(r)
        if retry_after is not None:
            delay = min(max(0.1, retry_after), _SEARCH_RETRY_MAX_DELAY_SECONDS)
        else:
            exp = _SEARCH_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            jitter = random.uniform(0.0, 0.3)
            delay = min(exp + jitter, _SEARCH_RETRY_MAX_DELAY_SECONDS)
        delay = min(delay, remaining)

        if retry_wait_callback is not None:
            retry_wait_callback(attempt, delay, elapsed, remaining)
        _LOGGER.debug(
            "Search returned 202, retrying in %.2fs (attempt=%s)",
            delay,
            attempt,
        )
        time.sleep(delay)
        attempt += 1
