"""List create/delete CLI tests."""

from unittest.mock import MagicMock

import requests
from typer.testing import CliRunner

from ica_cli import exit_codes
from ica_cli.cli import app


def _mock_http_error(status_code: int) -> requests.HTTPError:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = "upstream error"
    return requests.HTTPError("boom", response=resp)


def test_list_create_success_json(monkeypatch) -> None:
    runner = CliRunner()
    api = MagicMock()
    api.create_shopping_list.return_value = {
        "id": "abc",
        "shoppingListId": 123,
        "name": "Ny lista",
    }
    monkeypatch.setattr("ica_cli.cli._require_creds", lambda: {})
    monkeypatch.setattr("ica_cli.cli._api", lambda _creds: api)

    result = runner.invoke(
        app,
        ["list", "create", "Ny lista", "--format", "json"],
    )
    assert result.exit_code == 0
    assert '"ok": true' in result.stdout
    assert '"title": "Ny lista"' in result.stdout
    assert '"id": "abc"' in result.stdout
    assert '"shoppingListId": 123' in result.stdout


def test_list_create_http_error(monkeypatch) -> None:
    runner = CliRunner()
    api = MagicMock()
    api.create_shopping_list.side_effect = _mock_http_error(500)
    monkeypatch.setattr("ica_cli.cli._require_creds", lambda: {})
    monkeypatch.setattr("ica_cli.cli._api", lambda _creds: api)

    result = runner.invoke(app, ["list", "create", "X"])
    assert result.exit_code == exit_codes.UPSTREAM
    assert '"code": "upstream_http"' in result.output
    assert '"http_status": 500' in result.output


def test_list_delete_success_json(monkeypatch) -> None:
    runner = CliRunner()
    api = MagicMock()
    api.delete_shopping_list.return_value = True
    monkeypatch.setattr("ica_cli.cli._require_creds", lambda: {})
    monkeypatch.setattr("ica_cli.cli._api", lambda _creds: api)

    result = runner.invoke(
        app,
        ["list", "delete", "list-offline-id", "--format", "json"],
    )
    assert result.exit_code == 0
    assert '"ok": true' in result.stdout
    assert '"deleted": true' in result.stdout
    assert '"listId": "list-offline-id"' in result.stdout


def test_list_delete_http_error(monkeypatch) -> None:
    runner = CliRunner()
    api = MagicMock()
    api.delete_shopping_list.side_effect = _mock_http_error(404)
    monkeypatch.setattr("ica_cli.cli._require_creds", lambda: {})
    monkeypatch.setattr("ica_cli.cli._api", lambda _creds: api)

    result = runner.invoke(app, ["list", "delete", "missing"])
    assert result.exit_code == exit_codes.UPSTREAM
    assert '"code": "upstream_http"' in result.output
    assert '"http_status": 404' in result.output
