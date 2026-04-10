"""Config and auth state file locations."""

import os
from pathlib import Path


def config_dir() -> Path:
    """Return XDG config dir (or ICA_CLI_CONFIG_DIR)."""
    override = os.environ.get("ICA_CLI_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "ica-cli"
    return Path.home() / ".config" / "ica-cli"


def auth_state_path() -> Path:
    """Path to persisted OAuth auth state JSON."""
    p = os.environ.get("ICA_CLI_AUTH_STATE_PATH")
    if p:
        return Path(p).expanduser()
    return config_dir() / "auth_state.json"


def handla_web_state_path() -> Path:
    """Path to Handla web session (cookie header) JSON."""
    p = os.environ.get("ICA_CLI_HANDLA_WEB_STATE_PATH")
    if p:
        return Path(p).expanduser()
    return config_dir() / "handla_web.json"


def ensure_config_dir() -> Path:
    d = config_dir()
    d.mkdir(parents=0o700, exist_ok=True)
    return d
