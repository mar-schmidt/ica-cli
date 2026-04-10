"""Persist Handla web session cookie (separate from mobile OAuth)."""

from __future__ import annotations

import json
import os
from typing import Any

from ica_cli.paths import ensure_config_dir, handla_web_state_path


def load_handla_web_state() -> dict[str, Any] | None:
    path = handla_web_state_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def save_handla_web_state(state: dict[str, Any]) -> None:
    ensure_config_dir()
    path = handla_web_state_path()
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def clear_handla_web_state() -> None:
    """Remove persisted Handla web session file if present."""
    path = handla_web_state_path()
    if path.is_file():
        path.unlink()


def load_handla_cookie_header() -> str | None:
    """Env ICA_CLI_HANDLA_COOKIE overrides file."""
    env = os.environ.get("ICA_CLI_HANDLA_COOKIE", "").strip()
    if env:
        return env
    st = load_handla_web_state()
    if not st:
        return None
    ch = st.get("cookie_header")
    if isinstance(ch, str) and ch.strip():
        return ch.strip()
    return None


def handla_cookie_persist_enabled() -> bool:
    """False when cookie comes from env (do not write file)."""
    return not bool(os.environ.get("ICA_CLI_HANDLA_COOKIE", "").strip())


def load_cached_handla_csrf() -> str | None:
    """Session CSRF from file (stable until logout / new elevated login)."""
    if not handla_cookie_persist_enabled():
        return None
    st = load_handla_web_state()
    if not st:
        return None
    t = st.get("csrf_token")
    if isinstance(t, str) and t.strip():
        return t.strip()
    return None


def persist_handla_web_derived(
    *,
    cookie_header: str,
    csrf_token: str | None = None,
    clear_csrf: bool = False,
) -> None:
    """
    Merge cookie header (and optional CSRF) into handla_web.json.

    Skipped when ICA_CLI_HANDLA_COOKIE is set.
    """
    if not handla_cookie_persist_enabled():
        return
    st = dict(load_handla_web_state() or {})
    st["cookie_header"] = cookie_header.strip()
    if clear_csrf:
        st.pop("csrf_token", None)
    elif csrf_token is not None:
        st["csrf_token"] = csrf_token.strip()
    save_handla_web_state(st)


def clear_cached_handla_csrf_file() -> None:
    """Drop cached CSRF so the next mutation re-fetches from HTML."""
    if not handla_cookie_persist_enabled():
        return
    st = load_handla_web_state()
    if not st or "csrf_token" not in st:
        return
    st = dict(st)
    st.pop("csrf_token", None)
    save_handla_web_state(st)
