"""Typed shapes for auth and API payloads (subset of ha-ica-todo)."""

from __future__ import annotations

from typing import Any, TypedDict


class AuthCredentials(TypedDict):
    username: str
    password: str


class OAuthClient(TypedDict):
    client_id: str
    client_secret: str
    scope: str


class OAuthToken(TypedDict, total=False):
    id_token: str | None
    token_type: str
    access_token: str
    refresh_token: str
    scope: str
    expires_in: int
    expiry: str


class JwtUserInfo(TypedDict, total=False):
    given_name: str
    family_name: str
    person_name: str


class AuthState(TypedDict, total=False):
    client: OAuthClient | None
    token: OAuthToken | None
    user: JwtUserInfo | None


class IcaShoppingListEntry(TypedDict, total=False):
    id: int | None
    offlineId: str | None
    productName: str
    quantity: float | None
    unit: str | None
    recipes: list[dict[str, Any]] | None
    recipeId: str | None
    offerId: str | None
    productEan: str | None
    isStrikedOver: bool
    internalOrder: int | None
    articleGroupId: int | None
    articleGroupIdExtended: int | None
    latestChange: str | None
    sourceId: int | None
    isSmartItem: bool | None


class IcaShoppingList(TypedDict, total=False):
    id: int | None
    offlineId: str | None
    title: str | None
    commentText: str | None
    sortingStore: int | None
    rows: list[IcaShoppingListEntry]
    latestChange: str | None
    isPrivate: bool | None
    isSmartList: bool | None


class IcaShoppingListSync(TypedDict, total=False):
    offlineId: str
    changedShoppingListProperties: dict[str, Any] | None
    createdRows: list[IcaShoppingListEntry] | None
    changedRows: list[IcaShoppingListEntry] | None
    deletedRows: list[str] | None


class IcaIngredientGroup(TypedDict, total=False):
    GroupName: str | None
    Ingredients: str | None


class IcaRecipe(TypedDict, total=False):
    Id: int | None
    Title: str | None
    ImageId: int | None
    YouTubeId: str | None
    IngredientGroups: list[IcaIngredientGroup]
    PreambleHTML: str | None
    CurrentUserRating: float | None
    AverageRating: float | None
    Difficulty: str | None
    CookingTime: str | None
    Portions: int | None
