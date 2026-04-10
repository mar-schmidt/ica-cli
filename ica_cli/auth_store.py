"""Load and save auth state JSON."""

from __future__ import annotations

import json
import os
from typing import Any

from ica_cli.icatypes import AuthState
from ica_cli.paths import auth_state_path, ensure_config_dir


def load_auth_state() -> AuthState | None:
    path = auth_state_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def save_auth_state(state: AuthState) -> None:
    ensure_config_dir()
    path = auth_state_path()
    text = json.dumps(state, indent=2)
    path.write_text(text, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def clear_auth_state() -> None:
    path = auth_state_path()
    if path.is_file():
        path.unlink()
