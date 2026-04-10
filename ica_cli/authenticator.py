"""OAuth2 + PKCE login for ICA mobile (ported from ha-ica-todo, no HA deps)."""

from __future__ import annotations

import base64
import datetime
import hashlib
import logging
import re
from os import urandom
from typing import Any

import jwt
import requests

from ica_cli.const import API
from ica_cli.icatypes import (
    AuthCredentials,
    AuthState,
    JwtUserInfo,
    OAuthClient,
    OAuthToken,
)

_LOGGER = logging.getLogger(__name__)


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _parse_expiry(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    try:
        dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except ValueError:
        return None


class IcaAuthenticator:
    """Handle ICA ims.icagruppen.se authentication."""

    def __init__(
        self,
        credentials: AuthCredentials,
        state: AuthState | None,
        session: requests.Session | None = None,
    ) -> None:
        self._session = session or requests.Session()
        self._auth_state = state
        self._credentials = credentials

    def get_rest_url(self, endpoint: str) -> str:
        return "/".join([API.URLs.BASE_URL, endpoint])

    def invoke_get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
        allow_redirects: bool = True,
    ) -> requests.Response:
        response = self._session.get(
            url,
            params=params,
            data=data,
            headers=headers,
            timeout=timeout,
            allow_redirects=allow_redirects,
        )
        response.raise_for_status()
        return response

    def invoke_post(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        data: Any = None,
        json_data: Any = None,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
        allow_redirects: bool = True,
    ) -> requests.Response:
        response = self._session.post(
            url,
            params=params,
            data=data,
            json=json_data,
            headers=headers,
            timeout=timeout,
            allow_redirects=allow_redirects,
        )
        response.raise_for_status()
        return response

    def get_token_for_app_registration(self) -> str:
        url = self.get_rest_url(API.URLs.OAUTH2_TOKEN_ENDPOINT)
        d = {
            "client_id": API.AppRegistration.CLIENT_ID,
            "client_secret": API.AppRegistration.CLIENT_SECRET,
            "grant_type": "client_credentials",
            "scope": "dcr",
            "response_type": "token",
        }
        response = self.invoke_post(url, data=d)
        return response.json()["access_token"]

    def register_app(self) -> OAuthClient:
        token = self.get_token_for_app_registration()
        url = self.get_rest_url(API.AppRegistration.APP_REGISTRATION_ENDPOINT)
        j = {"software_id": "dcr-ica-app-template"}
        h = {"Authorization": f"Bearer {token}"}
        response = self.invoke_post(url, json_data=j, headers=h)
        return OAuthClient(response.json())

    def init_oauth(
        self,
        registered_app: OAuthClient,
        code_challenge: str,
    ) -> str:
        url = self.get_rest_url(API.URLs.OAUTH2_AUTHORIZE_ENDPOINT)
        p = {
            "client_id": registered_app["client_id"],
            "scope": registered_app["scope"],
            "redirect_uri": "icacurity://app",
            "response_type": "code",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "prompt": "login",
            "acr": "urn:se:curity:authentication:html-form:IcaCustomers",
        }
        response = self.invoke_get(url, params=p, allow_redirects=False)
        location = response.headers["Location"]
        m = re.search(r"&state=(\w*)", location)
        if not m:
            raise ValueError("No state in authorize redirect")
        state = m.group(1)
        self.invoke_get(location)
        return state

    def init_login(self, credentials: AuthCredentials, state: str) -> str:
        url = self.get_rest_url(API.URLs.LOGIN_ENDPOINT)
        d = {
            "userName": credentials["username"],
            "password": credentials["password"],
        }
        response = self.invoke_post(url, data=d)
        if response.status_code == 400:
            raise RuntimeError("Login failed (check personal ID and PIN).")
        response.raise_for_status()
        m_state = re.search(
            r'<input type="hidden" name="state" value="(\w*)',
            response.text,
        )
        m_token = re.search(
            r'<input type="hidden" name="token" value="(\w*)',
            response.text,
        )
        if not m_state or not m_token:
            raise RuntimeError(
                "Could not parse login form (ICA HTML changed?)."
            )
        api_state = m_state.group(1)
        token = m_token.group(1)
        if api_state != state:
            _LOGGER.warning(
                "OAuth state mismatch client=%s server=%s",
                state,
                api_state,
            )
        return token

    def get_access_token(
        self,
        registered_app: OAuthClient,
        state: str,
        token: str,
        code_verifier: str,
    ) -> OAuthToken:
        url = self.get_rest_url(API.URLs.OAUTH2_AUTHORIZE_ENDPOINT)
        p = {
            "client_id": registered_app["client_id"],
            "forceAuthN": "true",
            "acr": "urn:se:curity:authentication:html-form:IcaCustomers",
        }
        d = {"token": token, "state": state}
        response = self.invoke_post(
            url,
            params=p,
            data=d,
            allow_redirects=False,
        )
        location = response.headers["Location"]
        m = re.search(r"&code=(\w*)", location)
        if not m:
            raise ValueError("No code in post-login redirect")
        code = m.group(1)
        url_tok = self.get_rest_url(API.URLs.OAUTH2_TOKEN_ENDPOINT)
        d2 = {
            "code": code,
            "client_id": registered_app["client_id"],
            "client_secret": registered_app["client_secret"],
            "grant_type": "authorization_code",
            "scope": registered_app["scope"],
            "response_type": "token",
            "code_verifier": code_verifier,
            "redirect_uri": "icacurity://app",
        }
        response = self.invoke_post(url_tok, data=d2)
        return OAuthToken(response.json())

    def get_refresh_token(
        self,
        registered_app: OAuthClient,
        auth_token: OAuthToken,
    ) -> OAuthToken:
        url = self.get_rest_url(API.URLs.OAUTH2_TOKEN_ENDPOINT)
        basic = IcaAuthenticator.generate_basic_auth(registered_app)
        h = {"Authorization": f"Basic {basic}"}
        d = {
            "grant_type": "refresh_token",
            "refresh_token": auth_token["refresh_token"],
        }
        response = self.invoke_post(url, data=d, headers=h)
        return OAuthToken(response.json())

    @staticmethod
    def generate_basic_auth(registered_app: OAuthClient) -> str:
        raw = f"{registered_app['client_id']}:{registered_app['client_secret']}"
        return base64.b64encode(raw.encode("utf-8")).decode("ascii")

    @staticmethod
    def generate_code_challenge() -> tuple[str, str]:
        code_verifier = base64.urlsafe_b64encode(urandom(40)).decode("utf-8")
        code_verifier = re.sub(r"[^a-zA-Z0-9]+", "", code_verifier)
        digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        b64 = base64.urlsafe_b64encode(digest).decode("utf-8")
        code_challenge = b64.replace("=", "")
        return code_challenge, code_verifier

    def ensure_login(self, refresh: bool | None = None) -> AuthState:
        state: AuthState = dict(self._auth_state or {})
        self._auth_state = self._handle_login(
            self._credentials, state, refresh=refresh
        )
        return self._auth_state

    def _handle_login(
        self,
        credentials: AuthCredentials,
        auth_state: AuthState,
        refresh: bool | None = None,
        retry: int = 0,
    ) -> AuthState:
        now = _utcnow()
        if not auth_state.get("client"):
            auth_state["client"] = self.register_app()

        current_token = auth_state.get("token")
        exp_raw = current_token.get("expiry") if current_token else None
        expiry = _parse_expiry(exp_raw)

        if not current_token:
            auth_state = self._handle_new_login(credentials, auth_state)
            return auth_state

        try:
            if expiry and expiry < now:
                _LOGGER.info("Access token expired; refreshing.")
                auth_state = self._handle_refresh_login(auth_state)
            elif refresh:
                _LOGGER.info("Forced token refresh.")
                auth_state = self._handle_refresh_login(auth_state)
        except requests.HTTPError as err:
            if err.response is not None and err.response.status_code == 400:
                if retry > 2:
                    raise
                _LOGGER.info("Refresh failed; re-login.")
                auth_state = dict(auth_state)
                auth_state.pop("token", None)
                return self._handle_login(
                    credentials, auth_state, refresh=False, retry=retry + 1
                )
            raise
        return auth_state

    def _handle_new_login(
        self,
        credentials: AuthCredentials,
        auth_state: AuthState,
    ) -> AuthState:
        now = _utcnow()
        code_challenge, code_verifier = self.generate_code_challenge()
        state = self.init_oauth(auth_state["client"], code_challenge)
        form_token = self.init_login(credentials, state)
        access_token = self.get_access_token(
            auth_state["client"], state, form_token, code_verifier
        )
        auth_state["token"] = access_token
        sec = access_token.get("expires_in", 2592000)
        delta = datetime.timedelta(seconds=sec)
        auth_state["token"]["expiry"] = (now + delta).isoformat()
        id_tok = access_token.get("id_token")
        if id_tok:
            decoded = jwt.decode(id_tok, options={"verify_signature": False})
            auth_state["user"] = JwtUserInfo(
                given_name=decoded.get("given_name", ""),
                family_name=decoded.get("family_name", ""),
                person_name=(
                    f"{decoded.get('given_name', '')} "
                    f"{decoded.get('family_name', '')}"
                ).strip(),
            )
        return auth_state

    def _handle_refresh_login(self, auth_state: AuthState) -> AuthState:
        now = _utcnow()
        client = auth_state.get("client")
        tok = auth_state.get("token")
        if not client or not tok:
            raise RuntimeError("Cannot refresh without client and token.")
        new_tok = self.get_refresh_token(client, tok)
        merged: dict[str, Any] = dict(tok)
        merged.update(dict(new_tok))
        sec = int(merged.get("expires_in", 2592000))
        merged["expiry"] = (now + datetime.timedelta(seconds=sec)).isoformat()
        auth_state["token"] = merged  # type: ignore[assignment]
        return auth_state
