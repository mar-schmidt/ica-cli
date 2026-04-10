"""Synchronous ICA mobile API client."""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any

import requests

from ica_cli.authenticator import IcaAuthenticator
from ica_cli.const import (
    API,
    ARTICLEGROUPS_ENDPOINT,
    MY_LIST_CREATE_ENDPOINT,
    MY_LIST_ENDPOINT,
    MY_LIST_SYNC_ENDPOINT,
    MY_LISTS_ENDPOINT,
    MY_RECIPES_FAVORITES_ENDPOINT,
    RECIPE_ENDPOINT,
    RANDOM_RECIPES_ENDPOINT,
)
from ica_cli.http_requests import delete, get, post
from ica_cli.icatypes import (
    AuthCredentials,
    AuthState,
    IcaRecipe,
    IcaShoppingList,
    IcaShoppingListSync,
)

_LOGGER = logging.getLogger(__name__)


def query_url(endpoint: str) -> str:
    return "/".join([API.URLs.QUERY_BASE, endpoint])


class IcaAPI:
    """Shopping lists and recipes on apimgw-pub.ica.se."""

    def __init__(
        self,
        credentials: AuthCredentials,
        auth_state: AuthState | None,
        session: requests.Session | None = None,
    ) -> None:
        self._session = session or requests.Session()
        self._auth_state: AuthState | None = auth_state
        self._auth_key: str | None = None
        if auth_state and auth_state.get("token"):
            self._auth_key = auth_state["token"].get("access_token")
        self._authenticator = IcaAuthenticator(credentials, auth_state, session)

    def ensure_login(self, refresh: bool | None = None) -> AuthState:
        auth_state = self._authenticator.ensure_login(refresh=refresh)
        self._auth_state = auth_state
        tok = auth_state.get("token")
        self._auth_key = tok["access_token"] if tok else None
        return auth_state

    def auth_state(self) -> AuthState | None:
        return self._auth_state

    def access_token(self) -> str:
        if not self._auth_key:
            raise RuntimeError("Not logged in.")
        return self._auth_key

    def get_shopping_lists(self) -> list[IcaShoppingList]:
        url = query_url(MY_LISTS_ENDPOINT)
        return get(self._session, url, self._auth_key)

    def get_shopping_list(self, list_id: str) -> IcaShoppingList:
        url = query_url(MY_LIST_ENDPOINT.format(list_id))
        return get(self._session, url, self._auth_key)

    def create_shopping_list(self, title: str) -> dict[str, Any]:
        url = query_url(MY_LIST_CREATE_ENDPOINT)
        return post(
            self._session,
            url,
            self._auth_key,
            json_data={"name": title},
        )

    def sync_shopping_list(self, data: IcaShoppingListSync) -> IcaShoppingList:
        url = query_url(MY_LIST_SYNC_ENDPOINT.format(data["offlineId"]))
        if "deletedRows" in data:
            sync_data: dict[str, Any] = {"deletedRows": data["deletedRows"]}
        elif "changedRows" in data:
            sync_data = {"changedRows": data["changedRows"]}
        elif "createdRows" in data:
            sync_data = {"createdRows": data["createdRows"]}
        else:
            sync_data = dict(data)
        return post(self._session, url, self._auth_key, json_data=sync_data)

    def delete_shopping_list(self, offline_id: str) -> bool:
        url = query_url(MY_LIST_ENDPOINT.format(offline_id))
        return delete(self._session, url, self._auth_key)

    def get_recipe(self, recipe_id: int) -> IcaRecipe | None:
        url = query_url(RECIPE_ENDPOINT.format(recipe_id))
        return get(
            self._session,
            url,
            self._auth_key,
            return_none_when_404=True,
        )

    def get_recipe_favorites(self) -> Any:
        url = query_url(MY_RECIPES_FAVORITES_ENDPOINT)
        return get(self._session, url, self._auth_key)

    def get_random_recipes(self, n: int = 5) -> Any:
        if n < 1:
            return []
        url = query_url(RANDOM_RECIPES_ENDPOINT.format(n))
        return get(self._session, url, self._auth_key)

    def get_articles(self) -> list[dict[str, Any]] | None:
        url = query_url(API.URLs.ARTICLES_ENDPOINT)
        data = get(self._session, url, self._auth_key)
        if data and "articles" in data:
            return data["articles"]
        return None


def build_create_row(
    product_line: str,
    parsed: dict[str, Any],
) -> dict[str, Any]:
    """Build a new shopping list row (mobile API shape)."""
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    row: dict[str, Any] = {
        "productName": parsed.get("productName") or product_line,
        "isStrikedOver": False,
        "sourceId": -1,
        "offlineId": str(uuid.uuid4()),
        "latestChange": now.isoformat().replace("+00:00", "Z"),
    }
    if parsed.get("quantity") is not None:
        q = parsed["quantity"]
        row["quantity"] = float(q) if isinstance(q, str) else q
    if parsed.get("unit"):
        row["unit"] = parsed["unit"]
    gid = parsed.get("articleGroupId")
    if gid is not None:
        row["articleGroupId"] = gid
        row["articleGroupIdExtended"] = gid
    return row


def build_sync_created(
    offline_list_id: str,
    rows: list[dict[str, Any]],
) -> IcaShoppingListSync:
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    return IcaShoppingListSync(
        offlineId=offline_list_id,
        createdRows=rows,
        changedShoppingListProperties={
            "latestChange": now.isoformat().replace("+00:00", "Z"),
        },
    )


def build_sync_changed(
    offline_list_id: str,
    rows: list[dict[str, Any]],
) -> IcaShoppingListSync:
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    for r in rows:
        r.setdefault(
            "latestChange",
            now.isoformat().replace("+00:00", "Z"),
        )
    return IcaShoppingListSync(
        offlineId=offline_list_id,
        changedRows=rows,
        changedShoppingListProperties={
            "latestChange": now.isoformat().replace("+00:00", "Z"),
        },
    )


def build_sync_deleted(
    offline_list_id: str,
    row_offline_ids: list[str],
) -> IcaShoppingListSync:
    return IcaShoppingListSync(
        offlineId=offline_list_id,
        deletedRows=row_offline_ids,
    )
