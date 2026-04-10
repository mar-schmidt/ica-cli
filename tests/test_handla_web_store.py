"""Tests for Handla web cookie persistence."""

from pathlib import Path

from ica_cli.handla_web_store import (
    load_handla_cookie_header,
    load_handla_web_state,
    save_handla_web_state,
)


def test_save_and_load_roundtrip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ICA_CLI_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("ICA_CLI_HANDLA_COOKIE", raising=False)
    save_handla_web_state({"cookie_header": "a=b; c=d"})
    st = load_handla_web_state()
    assert st is not None
    assert st.get("cookie_header") == "a=b; c=d"
    assert load_handla_cookie_header() == "a=b; c=d"


def test_env_overrides_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ICA_CLI_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("ICA_CLI_HANDLA_COOKIE", "from-env=1")
    save_handla_web_state({"cookie_header": "file=only"})
    assert load_handla_cookie_header() == "from-env=1"
