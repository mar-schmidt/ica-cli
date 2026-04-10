"""Resolve personal ID and PIN (env + optional saved username)."""

from __future__ import annotations

import os
from pathlib import Path

from ica_cli.auth_store import load_auth_state
from ica_cli.icatypes import AuthCredentials
from ica_cli.paths import config_dir, ensure_config_dir


def _username_file() -> Path:
    return config_dir() / "username.txt"


def save_username(username: str) -> None:
    ensure_config_dir()
    _username_file().write_text(username.strip(), encoding="utf-8")
    try:
        os.chmod(_username_file(), 0o600)
    except OSError:
        pass


def load_saved_username() -> str | None:
    p = _username_file()
    if not p.is_file():
        return None
    return p.read_text(encoding="utf-8").strip() or None


def _has_access_token(state: dict | None) -> bool:
    if not state:
        return False
    tok = state.get("token")
    return bool(tok and tok.get("access_token"))


def load_credentials() -> AuthCredentials | None:
    """
    Return credentials for IcaAPI.

    If ICA_CLI_PIN is not set, a saved OAuth session (access token) is enough
    for normal calls; PIN is only needed again for full login after refresh
    fails or tokens are removed.
    """
    state = load_auth_state()
    user = (
        os.environ.get("ICA_CLI_PERSONAL_ID")
        or load_saved_username()
        or (state or {}).get("ica_cli_saved_username")
    )
    pw = os.environ.get("ICA_CLI_PIN")

    if user and pw:
        return AuthCredentials(username=user, password=pw)

    if user and _has_access_token(state):
        return AuthCredentials(username=user, password="")

    if pw and not user:
        return None

    return None
