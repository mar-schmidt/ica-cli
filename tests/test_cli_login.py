"""Login overview and Handla state clearing."""

from typer.testing import CliRunner

from ica_cli.cli import app
from ica_cli.handla_web_store import clear_handla_web_state, save_handla_web_state
from ica_cli.paths import handla_web_state_path


def test_login_no_subcommand_lists_account_and_elevated() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["login"])
    assert result.exit_code == 0
    out = result.stdout
    assert "account" in out
    assert "elevated" in out


def test_clear_handla_web_state_removes_file(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ICA_CLI_CONFIG_DIR", str(tmp_path))
    save_handla_web_state({"cookie_header": "a=b"})
    path = handla_web_state_path()
    assert path.is_file()
    clear_handla_web_state()
    assert not path.is_file()
