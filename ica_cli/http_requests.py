"""HTTP helpers for apimgw (Bearer JSON)."""

from __future__ import annotations

import json
import logging
from typing import Any

from requests import Session

_LOGGER = logging.getLogger(__name__)

CONTENT_TYPE_JSON = "application/json; charset=utf-8"


def create_headers(
    auth_key: str | None = None,
    with_content: bool = False,
    request_id: str | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if auth_key:
        headers["Authorization"] = f"Bearer {auth_key}"
    if with_content:
        headers["Content-Type"] = CONTENT_TYPE_JSON
    if request_id:
        headers["X-Request-Id"] = request_id
    return headers


def get(
    session: Session,
    url: str,
    auth_key: str | None = None,
    params: dict[str, Any] | None = None,
    return_none_when_404: bool = False,
) -> Any:
    _LOGGER.info(
        "HTTP [GET] %s%s",
        url,
        f" | Params: {params}" if params else "",
    )
    response = session.get(
        url,
        params=params,
        headers=create_headers(auth_key=auth_key),
        timeout=60,
    )
    if response.status_code == 200:
        return response.json()
    if response.status_code == 404 and return_none_when_404:
        return None
    try:
        response.raise_for_status()
    except Exception:
        _LOGGER.error(
            "HTTP [GET] %s -> %s %s",
            url,
            response.status_code,
            response.text[:500],
        )
        raise
    return response.json()


def post(
    session: Session,
    url: str,
    auth_key: str | None = None,
    data: dict[str, Any] | None = None,
    json_data: Any | None = None,
) -> Any:
    req_data = dict(data) if data else None
    request_id = None
    if req_data and "request_id" in req_data:
        request_id = req_data.pop("request_id", None)

    headers = create_headers(
        auth_key=auth_key,
        with_content=bool(req_data),
        request_id=request_id,
    )
    _LOGGER.info("HTTP [POST] %s", url)
    response = session.post(
        url,
        headers=headers,
        data=json.dumps(req_data) if req_data else None,
        json=json_data,
        timeout=60,
    )
    if response.status_code == 200:
        return response.json()
    try:
        response.raise_for_status()
    except Exception:
        _LOGGER.error(
            "HTTP [POST] %s -> %s %s",
            url,
            response.status_code,
            response.text[:500],
        )
        raise
    return response.json()


def delete(
    session: Session,
    url: str,
    auth_key: str | None = None,
    args: dict[str, Any] | None = None,
) -> bool:
    a = dict(args) if args else {}
    request_id = a.pop("request_id", None)
    headers = create_headers(auth_key=auth_key, request_id=request_id)
    _LOGGER.info("HTTP [DELETE] %s", url)
    response = session.delete(url, headers=headers, timeout=60)
    try:
        response.raise_for_status()
    except Exception:
        _LOGGER.error(
            "HTTP [DELETE] %s -> %s %s",
            url,
            response.status_code,
            response.text[:500],
        )
        raise
    return bool(response.ok)
