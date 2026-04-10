"""Tests for Handla web cart client and search (mocked HTTP)."""

from unittest.mock import MagicMock, patch

import requests

from ica_cli.handla_cart import (
    HandlaCsrfError,
    HandlaResponseFormatError,
    HandlaWebCartClient,
    fetch_handla_csrf,
    handla_active_cart_url,
    handla_http_error_details,
    handla_search_products,
    handla_store_base,
    parse_csrf_from_handla_html,
)


def test_handla_store_base() -> None:
    b = handla_store_base("1004219")
    assert b.endswith("/stores/1004219/")
    assert b.startswith("https://")


def test_handla_active_cart_url() -> None:
    u = handla_active_cart_url("1004219")
    assert "handlaprivatkund.ica.se" in u
    assert "1004219" in u
    assert u.endswith("/carts/active")
    assert not u.endswith("/active/")


def test_parse_csrf_from_handla_html() -> None:
    tok = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    html = f'foo "csrf":{{"token":"{tok}"}} bar'
    assert parse_csrf_from_handla_html(html) == tok


def test_parse_csrf_from_handla_html_missing() -> None:
    assert parse_csrf_from_handla_html("<html></html>") is None


def test_web_client_loads_cookie_into_jar() -> None:
    sess = requests.Session()
    HandlaWebCartClient("1004219", cookie_header="a=b", session=sess)
    c = sess.cookies.get("a", domain=".handlaprivatkund.ica.se")
    assert c == "b"


def test_get_active_cart_parses_json() -> None:
    sess = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"cartId": "x", "items": []}
    sess.get.return_value = resp

    c = HandlaWebCartClient("1004219", cookie_header="x=1", session=sess)
    data = c.get_active_cart()
    assert data["cartId"] == "x"
    sess.get.assert_called_once()


def test_get_active_cart_non_json_raises_format_error() -> None:
    sess = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    resp.text = "<html>blocked</html>"
    resp.json.side_effect = ValueError("not json")
    sess.get.return_value = resp

    c = HandlaWebCartClient("1004219", cookie_header="x=1", session=sess)
    try:
        c.get_active_cart()
    except HandlaResponseFormatError as exc:
        assert exc.status_code == 200
        assert exc.content_type == "text/html"
        assert "blocked" in exc.body_preview
    else:
        raise AssertionError("expected HandlaResponseFormatError")


@patch("ica_cli.handla_cart.load_cached_handla_csrf", return_value=None)
@patch(
    "ica_cli.handla_cart.fetch_handla_csrf_for_session",
    return_value="csrf-uuid",
)
def test_apply_quantity_post_json(
    mock_fetch: MagicMock,
    _mock_cached: MagicMock,
) -> None:
    sess = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"basketUpdateResult": {}}
    sess.post.return_value = resp

    c = HandlaWebCartClient("42", cookie_header="c=d", session=sess)
    out = c.apply_quantity([{"productId": "p1", "quantity": 1}])
    assert "basketUpdateResult" in out
    mock_fetch.assert_called_once()
    assert mock_fetch.call_args[0][1] == "42"
    sess.post.assert_called_once()
    kwargs = sess.post.call_args.kwargs
    assert kwargs["json"] == [{"productId": "p1", "quantity": 1}]
    ph = kwargs["headers"]
    assert ph["Content-Type"] == "application/json"
    assert ph["X-CSRF-TOKEN"] == "csrf-uuid"
    assert "/stores/42/" in ph["Referer"]
    assert ph["Origin"].endswith("ica.se")


@patch("ica_cli.handla_cart.load_cached_handla_csrf", return_value=None)
@patch(
    "ica_cli.handla_cart.fetch_handla_csrf_for_session",
    return_value="csrf-uuid",
)
def test_apply_quantity_non_json_raises_format_error(
    _mock_fetch: MagicMock,
    _mock_cached: MagicMock,
) -> None:
    sess = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"Content-Type": "text/plain"}
    resp.text = "ok"
    resp.json.side_effect = ValueError("not json")
    sess.post.return_value = resp

    c = HandlaWebCartClient("42", cookie_header="c=d", session=sess)
    try:
        c.apply_quantity([{"productId": "p1", "quantity": 1}])
    except HandlaResponseFormatError as exc:
        assert exc.status_code == 200
        assert exc.content_type == "text/plain"
        assert exc.body_preview == "ok"
    else:
        raise AssertionError("expected HandlaResponseFormatError")


@patch("ica_cli.handla_cart.requests.get")
def test_search_builds_query(mock_get: MagicMock) -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"products": []}
    mock_get.return_value = resp

    handla_search_products("9", "mjölk")
    url = mock_get.call_args[0][0]
    assert "product-pages/search" in url
    assert "mj" in url or "mj%C3%B6lk" in url
    hdrs = mock_get.call_args.kwargs.get("headers", {})
    assert "Authorization" not in hdrs
    assert "/stores/9/" in hdrs.get("Referer", "")
    assert "Mozilla" in hdrs.get("User-Agent", "")


@patch("ica_cli.handla_cart.requests.get")
def test_search_non_json_raises_format_error(mock_get: MagicMock) -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"Content-Type": "text/html"}
    resp.text = "<html>challenge</html>"
    resp.json.side_effect = ValueError("not json")
    mock_get.return_value = resp

    try:
        handla_search_products("9", "mjolk")
    except HandlaResponseFormatError as exc:
        assert exc.status_code == 200
        assert exc.content_type == "text/html"
        assert "challenge" in exc.body_preview
    else:
        raise AssertionError("expected HandlaResponseFormatError")


@patch("ica_cli.handla_cart.requests.get")
def test_search_empty_body_raises_format_error(mock_get: MagicMock) -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"Content-Type": "application/json"}
    resp.text = ""
    resp.json.side_effect = ValueError("empty")
    mock_get.return_value = resp

    try:
        handla_search_products("9", "mjolk")
    except HandlaResponseFormatError as exc:
        assert exc.status_code == 200
        assert exc.content_type == "application/json"
        assert exc.body_preview == ""
    else:
        raise AssertionError("expected HandlaResponseFormatError")


@patch("ica_cli.handla_cart.random.uniform", return_value=0.0)
@patch("ica_cli.handla_cart.time.sleep")
@patch("ica_cli.handla_cart.time.monotonic")
@patch("ica_cli.handla_cart.requests.get")
def test_search_retries_202_then_success(
    mock_get: MagicMock,
    mock_monotonic: MagicMock,
    mock_sleep: MagicMock,
    mock_jitter: MagicMock,
) -> None:
    r202 = requests.Response()
    r202.status_code = 202
    r202._content = b""
    r200 = requests.Response()
    r200.status_code = 200
    r200._content = b'{"productGroups":[]}'
    r200.headers["Content-Type"] = "application/json"
    mock_get.side_effect = [r202, r200]
    mock_monotonic.side_effect = [0.0, 0.0, 1.0]
    calls: list[tuple[int, float, float, float]] = []

    data = handla_search_products(
        "9",
        "mjolk",
        retry_wait_callback=lambda a, d, e, r: calls.append((a, d, e, r)),
    )

    assert data == {"productGroups": []}
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once_with(1.0)
    assert calls == [(1, 1.0, 0.0, 300.0)]
    mock_jitter.assert_called_once()


@patch("ica_cli.handla_cart.random.uniform", return_value=0.0)
@patch("ica_cli.handla_cart.time.sleep")
@patch("ica_cli.handla_cart.time.monotonic")
@patch("ica_cli.handla_cart.requests.get")
def test_search_202_uses_retry_after_header(
    mock_get: MagicMock,
    mock_monotonic: MagicMock,
    mock_sleep: MagicMock,
    _mock_jitter: MagicMock,
) -> None:
    r202 = requests.Response()
    r202.status_code = 202
    r202.headers["Retry-After"] = "2.5"
    r202._content = b""
    r200 = requests.Response()
    r200.status_code = 200
    r200._content = b'{"productGroups":[]}'
    r200.headers["Content-Type"] = "application/json"
    mock_get.side_effect = [r202, r200]
    mock_monotonic.side_effect = [10.0, 10.0, 12.5]

    handla_search_products("9", "mjolk")

    mock_sleep.assert_called_once_with(2.5)


@patch("ica_cli.handla_cart.time.sleep")
@patch("ica_cli.handla_cart.time.monotonic")
@patch("ica_cli.handla_cart.requests.get")
def test_search_202_times_out_after_max_wait(
    mock_get: MagicMock,
    mock_monotonic: MagicMock,
    mock_sleep: MagicMock,
) -> None:
    r202 = requests.Response()
    r202.status_code = 202
    r202._content = b""
    mock_get.return_value = r202
    mock_monotonic.side_effect = [0.0, 301.0]

    try:
        handla_search_products("9", "mjolk")
    except requests.HTTPError as exc:
        assert exc.response is r202
    else:
        raise AssertionError("expected HTTPError")

    mock_sleep.assert_not_called()


def test_handla_http_error_details() -> None:
    r = requests.Response()
    r.status_code = 403
    r._content = b'{"reason":"no"}'
    r.headers["Content-Type"] = "application/json"
    exc = requests.HTTPError(response=r)
    d = handla_http_error_details(exc)
    assert d["content_type"] == "application/json"
    assert "reason" in d["body_preview"]


@patch("ica_cli.handla_cart.requests.get")
def test_fetch_handla_csrf_ok(mock_get: MagicMock) -> None:
    tok = "11111111-2222-3333-4444-555555555555"
    r = MagicMock()
    r.status_code = 200
    r.text = f'"csrf":{{"token":"{tok}"}}'
    mock_get.return_value = r
    out = fetch_handla_csrf("a=b", "1")
    assert out == tok


@patch("ica_cli.handla_cart.requests.get")
def test_fetch_handla_csrf_missing(mock_get: MagicMock) -> None:
    r = MagicMock()
    r.status_code = 200
    r.text = "<html></html>"
    mock_get.return_value = r
    try:
        fetch_handla_csrf("a=b", "1")
    except HandlaCsrfError:
        pass
    else:
        raise AssertionError("expected HandlaCsrfError")
