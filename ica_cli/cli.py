"""Typer CLI: JSON-first for agents."""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from typing import Annotated, Any

import requests
import typer

from ica_cli import exit_codes
from ica_cli.auth_store import (
    clear_auth_state,
    load_auth_state,
    save_auth_state,
)
from ica_cli.credentials_util import load_credentials, save_username
from ica_cli.errors import (
    exit_with_error,
    print_json_error,
    success_payload,
)
from ica_cli.handla_browser_login import run_handla_browser_login
from ica_cli.handla_cart import (
    HandlaCsrfError,
    HandlaResponseFormatError,
    HandlaWebCartClient,
    handla_http_error_details,
    handla_search_products,
    load_handla_store_id,
)
from ica_cli.handla_web_store import (
    clear_handla_web_state,
    load_handla_cookie_header,
    save_handla_web_state,
)
from ica_cli.ica_api import (
    IcaAPI,
    build_create_row,
    build_sync_changed,
    build_sync_created,
    build_sync_deleted,
)
from ica_cli.icatypes import AuthCredentials, IcaShoppingListEntry
from ica_cli.parse_summary import parse_summary
from ica_cli.recipe_util import (
    json_safe_recipe,
    recipe_to_markdown,
    resolve_recipe_id,
)

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Unofficial ICA shopping list and recipe CLI.",
)

_LOGIN_EXPLAINED = (
    "ICA uses two separate sign-ins:\n\n"
    "  account    Personal ID + PIN → API access for shopping lists and "
    "recipes.\n"
    "  elevated   Browser session on Handla (handlaprivatkund.ica.se) → "
    "needed for `ica cart`.\n\n"
    "Run one or both subcommands below.\n"
)


def _emit(
    payload: dict[str, Any],
    fmt: str,
    text_renderer: Any | None = None,
) -> None:
    if fmt == "json":
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    elif text_renderer:
        sys.stdout.write(text_renderer(payload))
    else:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _api(creds: AuthCredentials, refresh: bool | None = None) -> IcaAPI:
    state = load_auth_state()
    client = IcaAPI(creds, state)
    try:
        client.ensure_login(refresh=refresh)
    except requests.ConnectionError as e:
        exit_with_error(
            exit_codes.NETWORK,
            str(e),
            err_code="network_error",
        )
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else None
        body = e.response.text[:2000] if e.response else ""
        exit_with_error(
            exit_codes.UPSTREAM,
            f"HTTP error: {e}",
            err_code="upstream_http",
            http_status=status,
            details={"body_preview": body},
        )
    except RuntimeError as e:
        exit_with_error(
            exit_codes.AUTH,
            str(e),
            err_code="auth_failed",
        )
    st = client.auth_state()
    if st:
        merged = dict(st)
        if creds.get("username"):
            merged["ica_cli_saved_username"] = creds["username"]
        save_auth_state(merged)
    return client


def _require_creds() -> AuthCredentials:
    c = load_credentials()
    if not c:
        exit_with_error(
            exit_codes.AUTH,
            "Not signed in (account): run `ica login account`, or set "
            "ICA_CLI_PERSONAL_ID (and ICA_CLI_PIN for first sign-in / "
            "re-login only).",
            err_code="missing_credentials",
        )
    return c


def _resolve_handla_store_id(store_id: str | None) -> str:
    if store_id and str(store_id).strip():
        return str(store_id).strip()
    env_id = load_handla_store_id()
    if env_id:
        return env_id
    exit_with_error(
        exit_codes.USAGE,
        "Set ICA_CLI_HANDLA_STORE_ID or pass --store-id "
        "(numeric store id from Handla URL).",
        err_code="missing_handla_store_id",
    )
    raise RuntimeError("unreachable")


def _perform_handla_browser_login_and_save(store_id: str) -> None:
    try:
        header = run_handla_browser_login(store_id)
    except RuntimeError as e:
        exit_with_error(
            exit_codes.USAGE,
            str(e),
            err_code="handla_browser_login_failed",
        )
    save_handla_web_state({"cookie_header": header})


@app.callback()
def main(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Log debug to stderr"),
    ] = False,
) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")


login_app = typer.Typer(
    help=(
        "Sign in: `account` (lists/recipes) and/or `elevated` (Handla cart)."
    ),
    invoke_without_command=True,
)


@login_app.callback(invoke_without_command=True)
def login_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    typer.echo(_LOGIN_EXPLAINED)
    typer.echo(ctx.get_help())
    raise typer.Exit(0)


@login_app.command("account")
def login_account(
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    """Personal ID + PIN; persists API OAuth state (lists and recipes)."""
    user = typer.prompt("Personal ID (personnummer)")
    pw = typer.prompt("PIN", hide_input=True)
    save_username(user)
    creds = AuthCredentials(username=user.strip(), password=pw)
    _ = _api(creds, refresh=False)
    payload = success_payload({"message": "Account sign-in OK; auth saved."})
    _emit(payload, fmt)


@login_app.command("elevated")
def login_elevated(
    store_id: Annotated[
        str | None,
        typer.Option("--store-id"),
    ] = None,
) -> None:
    """Open Handla in a browser; save cookies for cart (Playwright extra)."""
    sid = _resolve_handla_store_id(store_id)
    _perform_handla_browser_login_and_save(sid)
    _emit(success_payload({"saved": True}), "json")


app.add_typer(login_app, name="login")


logout_app = typer.Typer(
    help="Clear `account` and/or `elevated` saved sessions.",
    invoke_without_command=True,
)


@logout_app.callback(invoke_without_command=True)
def logout_callback(
    ctx: typer.Context,
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    clear_auth_state()
    clear_handla_web_state()
    msg = (
        "Signed out: account (API) and elevated (Handla) sessions removed."
    )
    _emit(success_payload({"message": msg}), fmt)


@logout_app.command("account")
def logout_account(
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    """Remove saved account (API / OAuth) state only."""
    clear_auth_state()
    _emit(
        success_payload({"message": "Account session removed."}),
        fmt,
    )


@logout_app.command("elevated")
def logout_elevated_cmd(
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    """Remove saved Handla (elevated) web cookie state only."""
    clear_handla_web_state()
    _emit(
        success_payload({"message": "Elevated (Handla) session removed."}),
        fmt,
    )


app.add_typer(logout_app, name="logout")


def _list_all_shopping_lists(fmt: str) -> None:
    api = _api(_require_creds())
    try:
        data = api.get_shopping_lists()
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else None
        exit_with_error(
            exit_codes.UPSTREAM,
            str(e),
            err_code="upstream_http",
            http_status=status,
        )
    payload = success_payload(data)

    def textify(p: dict[str, Any]) -> str:
        rows = p.get("data") or []
        lines = ["offlineId\ttitle"]
        for row in rows:
            lines.append(
                f"{row.get('offlineId', '')}\t{row.get('title', '')}"
            )
        return "\n".join(lines) + "\n"

    _emit(payload, fmt, textify if fmt == "text" else None)


def _list_show_shopping_list(list_id: str, fmt: str) -> None:
    api = _api(_require_creds())
    try:
        data = api.get_shopping_list(list_id)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else None
        exit_with_error(
            exit_codes.UPSTREAM,
            str(e),
            err_code="upstream_http",
            http_status=status,
        )
    payload = success_payload(data)

    def textify(p: dict[str, Any]) -> str:
        lst = p.get("data") or {}
        lines = [f"List: {lst.get('title')} ({lst.get('offlineId')})", ""]
        for r in lst.get("rows") or []:
            chk = "x" if r.get("isStrikedOver") else " "
            lines.append(
                f"  [{chk}] {r.get('offlineId')}\t{r.get('productName')}"
            )
        return "\n".join(lines) + "\n"

    _emit(payload, fmt, textify if fmt == "text" else None)


def _list_add_item(list_id: str, line: str, fmt: str) -> None:
    api = _api(_require_creds())
    articles = None
    try:
        articles = api.get_articles()
    except Exception:
        pass
    parsed = parse_summary(line, articles)
    if parsed.get("quantity") and isinstance(parsed["quantity"], str):
        parsed["quantity"] = float(parsed["quantity"].replace(",", "."))
    row = build_create_row(line, parsed)
    sync = build_sync_created(list_id, [row])
    try:
        updated = api.sync_shopping_list(sync)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else None
        exit_with_error(
            exit_codes.UPSTREAM,
            str(e),
            err_code="upstream_http",
            http_status=status,
        )
    _emit(success_payload(updated), fmt)


def _normalize_created_list(data: Any, fallback_title: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"title": fallback_title}
    out: dict[str, Any] = {"title": data.get("name") or fallback_title}
    if data.get("id") is not None:
        out["id"] = data["id"]
    if data.get("shoppingListId") is not None:
        out["shoppingListId"] = data["shoppingListId"]
    if data.get("offlineId") is not None:
        out["offlineId"] = data["offlineId"]
    out["raw"] = data
    return out


def _list_create(title: str, fmt: str) -> None:
    api = _api(_require_creds())
    try:
        created = api.create_shopping_list(title)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else None
        exit_with_error(
            exit_codes.UPSTREAM,
            str(e),
            err_code="upstream_http",
            http_status=status,
        )
    payload = success_payload(_normalize_created_list(created, title))

    def textify(p: dict[str, Any]) -> str:
        row = p.get("data") or {}
        lines = [
            f"title: {row.get('title', '')}",
            f"id: {row.get('id', '')}",
            f"shoppingListId: {row.get('shoppingListId', '')}",
            f"offlineId: {row.get('offlineId', '')}",
        ]
        return "\n".join(lines) + "\n"

    _emit(payload, fmt, textify if fmt == "text" else None)


def _list_delete(list_id: str, fmt: str) -> None:
    api = _api(_require_creds())
    try:
        deleted = api.delete_shopping_list(list_id)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else None
        exit_with_error(
            exit_codes.UPSTREAM,
            str(e),
            err_code="upstream_http",
            http_status=status,
        )
    _emit(success_payload({"deleted": bool(deleted), "listId": list_id}), fmt)


def _row_by_id(api: IcaAPI, list_id: str, row_id: str) -> dict[str, Any]:
    lst = api.get_shopping_list(list_id)
    for r in lst.get("rows") or []:
        if str(r.get("offlineId")) == row_id:
            return r
    exit_with_error(
        exit_codes.USAGE,
        f"No row {row_id!r} in list {list_id!r}",
        err_code="row_not_found",
    )
    raise RuntimeError("unreachable")


def _list_check_row(list_id: str, row_id: str, fmt: str) -> None:
    api = _api(_require_creds())
    row = _row_by_id(api, list_id, row_id)
    entry: IcaShoppingListEntry = {
        "offlineId": row_id,
        "isStrikedOver": True,
        "productName": row.get("productName") or "",
    }
    sync = build_sync_changed(list_id, [entry])
    try:
        updated = api.sync_shopping_list(sync)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else None
        exit_with_error(
            exit_codes.UPSTREAM,
            str(e),
            err_code="upstream_http",
            http_status=status,
        )
    _emit(success_payload(updated), fmt)


def _list_uncheck_row(list_id: str, row_id: str, fmt: str) -> None:
    api = _api(_require_creds())
    row = _row_by_id(api, list_id, row_id)
    entry: IcaShoppingListEntry = {
        "offlineId": row_id,
        "isStrikedOver": False,
        "productName": row.get("productName") or "",
    }
    sync = build_sync_changed(list_id, [entry])
    try:
        updated = api.sync_shopping_list(sync)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else None
        exit_with_error(
            exit_codes.UPSTREAM,
            str(e),
            err_code="upstream_http",
            http_status=status,
        )
    _emit(success_payload(updated), fmt)


def _list_remove_row(list_id: str, row_id: str, fmt: str) -> None:
    api = _api(_require_creds())
    sync = build_sync_deleted(list_id, [row_id])
    try:
        updated = api.sync_shopping_list(sync)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else None
        exit_with_error(
            exit_codes.UPSTREAM,
            str(e),
            err_code="upstream_http",
            http_status=status,
        )
    _emit(success_payload(updated), fmt)


list_app = typer.Typer(
    help="Shopping lists (needs `ica login account`).",
    no_args_is_help=True,
)
app.add_typer(list_app, name="list")


@list_app.command("ls")
def list_ls(
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    """List all shopping lists."""
    _list_all_shopping_lists(fmt)


@list_app.command("show")
def list_show_cmd(
    list_id: Annotated[str, typer.Argument(help="List offlineId")],
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    """Show one shopping list with rows."""
    _list_show_shopping_list(list_id, fmt)


@list_app.command("create")
def list_create_cmd(
    title: Annotated[str, typer.Argument(help="List title")],
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    """Create a shopping list."""
    _list_create(title, fmt)


@list_app.command("add")
def list_add_cmd(
    list_id: Annotated[str, typer.Argument(help="List offlineId")],
    line: Annotated[str, typer.Argument(help='Item, e.g. 2 st mjölk')],
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    """Add an item to a shopping list."""
    _list_add_item(list_id, line, fmt)


@list_app.command("check")
def list_check_cmd(
    list_id: Annotated[str, typer.Argument()],
    row_id: Annotated[str, typer.Argument(help="Row offlineId")],
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    """Mark a row as bought (strikethrough)."""
    _list_check_row(list_id, row_id, fmt)


@list_app.command("uncheck")
def list_uncheck_cmd(
    list_id: Annotated[str, typer.Argument()],
    row_id: Annotated[str, typer.Argument(help="Row offlineId")],
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    """Mark a row as not bought."""
    _list_uncheck_row(list_id, row_id, fmt)


@list_app.command("remove")
def list_remove_cmd(
    list_id: Annotated[str, typer.Argument()],
    row_id: Annotated[str, typer.Argument(help="Row offlineId")],
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    """Remove a row from a list."""
    _list_remove_row(list_id, row_id, fmt)


@list_app.command("delete")
def list_delete_cmd(
    list_id: Annotated[str, typer.Argument(help="List offlineId")],
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    """Delete a list."""
    _list_delete(list_id, fmt)


recipe_app = typer.Typer(help="Recipes (needs `ica login account`).")
app.add_typer(recipe_app, name="recipe")


@recipe_app.command("get")
def recipe_get(
    spec: Annotated[str, typer.Argument(help="Numeric id, slug-id, or URL")],
    markdown: Annotated[
        bool,
        typer.Option("--markdown", "-m", help="Print Markdown to stdout"),
    ] = False,
    output: Annotated[
        str | None,
        typer.Option("--output", "-o", help="Write Markdown to file"),
    ] = None,
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    """Fetch a recipe by id or ica.se URL."""
    creds = _require_creds()
    try:
        rid = resolve_recipe_id(spec)
    except ValueError as e:
        exit_with_error(exit_codes.USAGE, str(e), err_code="bad_recipe_spec")
    api = _api(creds)
    try:
        rec = api.get_recipe(rid)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else None
        exit_with_error(
            exit_codes.UPSTREAM,
            str(e),
            err_code="upstream_http",
            http_status=status,
        )
    if rec is None:
        exit_with_error(
            exit_codes.UPSTREAM,
            f"Recipe not found: {rid}",
            err_code="recipe_not_found",
            http_status=404,
        )
    md = recipe_to_markdown(rec)
    if output:
        Path(output).write_text(md, encoding="utf-8")
    if markdown:
        sys.stdout.write(md)

    if markdown or output:
        if fmt == "json":
            meta: dict[str, Any] = {
                "id": rid,
                "markdown_stdout": bool(markdown),
                "markdown_file": output,
            }
            _emit(success_payload(meta), "json")
        elif output:
            sys.stdout.write(f"Wrote markdown to {output}\n")
        return

    payload = success_payload(json_safe_recipe(rec))
    _emit(payload, fmt)


@recipe_app.command("favorites")
def recipe_favorites(
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    """List favorite recipes (account API)."""
    api = _api(_require_creds())
    try:
        data = api.get_recipe_favorites()
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else None
        exit_with_error(
            exit_codes.UPSTREAM,
            str(e),
            err_code="upstream_http",
            http_status=status,
        )
    _emit(success_payload(data), fmt)


def _require_handla_cookie() -> str:
    c = load_handla_cookie_header()
    if not c:
        exit_with_error(
            exit_codes.AUTH,
            "Elevated (Handla) session missing: run `ica login elevated`, "
            "or set ICA_CLI_HANDLA_COOKIE (Cookie header from browser "
            "DevTools for handlaprivatkund.ica.se).",
            err_code="missing_handla_web_session",
        )
    return c


def _handla_web_client(store_id: str) -> HandlaWebCartClient:
    return HandlaWebCartClient(store_id, _require_handla_cookie())


def _extract_unit_of_measure(product: dict[str, Any]) -> str | None:
    unit_price = product.get("unitPrice")
    if isinstance(unit_price, dict):
        unit = unit_price.get("unit")
        if isinstance(unit, str) and unit.strip():
            m = re.search(r"per\.([A-Za-z]+)$", unit.strip())
            if m:
                return m.group(1).lower()

    pack = product.get("packSizeDescription")
    if isinstance(pack, str) and pack.strip():
        m = re.search(r"([A-Za-z]+)\s*$", pack.strip())
        if m:
            return m.group(1).lower()

    return None


def _compact_search_products(data: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    if not isinstance(data, dict):
        return out

    product_groups = data.get("productGroups")
    if not isinstance(product_groups, list):
        return out

    for group in product_groups:
        if not isinstance(group, dict):
            continue
        products = group.get("decoratedProducts")
        if not isinstance(products, list):
            continue
        for product in products:
            if not isinstance(product, dict):
                continue
            name = product.get("name")
            product_id = product.get("productId")
            if not isinstance(name, str):
                continue
            pid = str(product_id).strip()
            if not pid or pid in seen:
                continue

            item: dict[str, Any] = {"name": name, "productId": pid}
            unit = _extract_unit_of_measure(product)
            if unit:
                item["unitOfMeasure"] = unit
            out.append(item)
            seen.add(pid)

    return out


cart_app = typer.Typer(
    help=(
        "Handla cart after `ica login elevated`. Cookie + CSRF on "
        "handlaprivatkund.ica.se. "
        "Set ICA_CLI_HANDLA_STORE_ID or --store-id."
    ),
)
app.add_typer(cart_app, name="cart")


@cart_app.command("show")
def cart_show(
    store_id: Annotated[
        str | None,
        typer.Option("--store-id"),
    ] = None,
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    """GET active cart (Handla web session cookie)."""
    sid = _resolve_handla_store_id(store_id)
    client = _handla_web_client(sid)
    try:
        data = client.get_active_cart()
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else None
        exit_with_error(
            exit_codes.UPSTREAM,
            str(e),
            err_code="handla_cart_http",
            http_status=status,
            details=handla_http_error_details(e),
        )
    _emit(success_payload(data), fmt)


@cart_app.command("keepalive")
def cart_keepalive(
    store_id: Annotated[
        str | None,
        typer.Option("--store-id"),
    ] = None,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="No stdout on success (for cron); still errors to stderr.",
        ),
    ] = False,
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    """
    GET active cart to refresh Handla cookies and server idle session.

    Pair with a periodic job (e.g. every 2 minutes) if elevated login expires
    often. Does not replace WAF token renewal from a real browser.
    """
    sid = _resolve_handla_store_id(store_id)
    client = _handla_web_client(sid)
    try:
        data = client.get_active_cart()
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else None
        exit_with_error(
            exit_codes.UPSTREAM,
            str(e),
            err_code="handla_cart_http",
            http_status=status,
            details=handla_http_error_details(e),
        )
    if quiet:
        return
    _emit(success_payload({"keepalive": True, "cart": data}), fmt)


def _handla_apply_or_exit(
    sid: str,
    updates: list[dict[str, Any]],
    fmt: str,
) -> None:
    client = _handla_web_client(sid)
    try:
        data = client.apply_quantity(updates)
    except HandlaCsrfError as e:
        exit_with_error(
            exit_codes.UPSTREAM,
            str(e),
            err_code="handla_csrf_failed",
        )
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else None
        exit_with_error(
            exit_codes.UPSTREAM,
            str(e),
            err_code="handla_cart_http",
            http_status=status,
            details=handla_http_error_details(e),
        )
    _emit(success_payload(data), fmt)


@cart_app.command("add")
def cart_add(
    product_id: Annotated[str, typer.Argument(help="Product UUID")],
    delta: Annotated[
        int,
        typer.Option("--delta", "-d", help="Quantity delta (default +1)"),
    ] = 1,
    store_id: Annotated[str | None, typer.Option("--store-id")] = None,
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    """POST apply-quantity with positive delta."""
    sid = _resolve_handla_store_id(store_id)
    _handla_apply_or_exit(
        sid,
        [{"productId": product_id.strip(), "quantity": int(delta)}],
        fmt,
    )


@cart_app.command("remove")
def cart_remove(
    product_id: Annotated[str, typer.Argument(help="Product UUID")],
    store_id: Annotated[str | None, typer.Option("--store-id")] = None,
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    """Decrease quantity by 1 (delta -1). At 0 the line is removed."""
    sid = _resolve_handla_store_id(store_id)
    _handla_apply_or_exit(
        sid,
        [{"productId": product_id.strip(), "quantity": -1}],
        fmt,
    )


product_app = typer.Typer(
    help=(
        "Search products for a store. Anonymous Handla endpoint. "
        "Set ICA_CLI_HANDLA_STORE_ID or --store-id."
    ),
)
app.add_typer(product_app, name="product")


@product_app.command("search")
def product_search(
    query: Annotated[str, typer.Argument(help="Search term")],
    store_id: Annotated[str | None, typer.Option("--store-id")] = None,
    fmt: Annotated[str, typer.Option("--format", "-f")] = "json",
) -> None:
    """Search products; compact output for agent usage."""
    sid = _resolve_handla_store_id(store_id)
    retry_notices = 0

    def on_retry_wait(
        attempt: int,
        delay_seconds: float,
        elapsed_seconds: float,
        remaining_seconds: float,
    ) -> None:
        nonlocal retry_notices
        retry_notices += 1
        msg = (
            "Search is still processing (202). "
            f"Retry {attempt} in {delay_seconds:.1f}s "
            f"(elapsed {elapsed_seconds:.1f}s, "
            f"about {remaining_seconds:.1f}s left).\n"
        )
        sys.stderr.write(msg)
        sys.stderr.flush()

    try:
        data = handla_search_products(
            sid,
            query,
            retry_wait_callback=on_retry_wait,
        )
    except HandlaResponseFormatError as e:
        exit_with_error(
            exit_codes.UPSTREAM,
            str(e),
            err_code="handla_search_invalid_response",
            http_status=e.status_code,
            details=e.as_details(),
        )
    except requests.HTTPError as e:
        status = e.response.status_code if e.response else None
        if status == 202:
            exit_with_error(
                exit_codes.UPSTREAM,
                "Search is still processing after waiting 300 seconds.",
                err_code="handla_search_retry_timeout",
                http_status=status,
                details={
                    "retry_wait_seconds": 300,
                    "retry_count": retry_notices,
                },
            )
        exit_with_error(
            exit_codes.UPSTREAM,
            str(e),
            err_code="handla_search_http",
            http_status=status,
            details=handla_http_error_details(e),
        )
    _emit(success_payload(_compact_search_products(data)), fmt)


def main_cli() -> None:
    try:
        app()
    except typer.Exit as e:
        raise e
    except KeyboardInterrupt:
        print_json_error("Interrupted", code="keyboard_interrupt")
        raise SystemExit(exit_codes.USAGE) from None
