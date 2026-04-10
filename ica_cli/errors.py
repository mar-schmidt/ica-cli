"""Structured errors for agents."""

from __future__ import annotations

import json
import sys
from typing import Any

def print_json_error(
    message: str,
    *,
    code: str,
    details: dict[str, Any] | None = None,
    http_status: int | None = None,
) -> None:
    """Emit one JSON object on stderr."""
    payload: dict[str, Any] = {
        "error": message,
        "code": code,
    }
    if http_status is not None:
        payload["http_status"] = http_status
    if details:
        payload["details"] = details
    sys.stderr.write(json.dumps(payload, ensure_ascii=False) + "\n")


def exit_with_error(
    exit_code: int,
    message: str,
    *,
    err_code: str,
    details: dict[str, Any] | None = None,
    http_status: int | None = None,
) -> None:
    print_json_error(
        message, code=err_code, details=details, http_status=http_status
    )
    raise SystemExit(exit_code)


def success_payload(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data}
