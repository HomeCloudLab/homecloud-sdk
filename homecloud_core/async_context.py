"""Async runtime context — credentials + AsyncTransport."""

from __future__ import annotations

import asyncio
import time
import webbrowser
from collections.abc import Callable
from typing import Any

from homecloud_core.account import remember_account, resolve_account_id
from homecloud_core.async_transport import AsyncTransport
from homecloud_core.config import ProfileConfig, load_credentials
from homecloud_core.context import CoreContext
from homecloud_core.defaults import DEFAULT_PROFILE
from homecloud_core.env import (
    env_access_key_id,
    env_account_id,
    env_apex,
    env_profile,
    env_secret_access_key,
)
from homecloud_core.errors import HomeCloudError, NotConfiguredError, NotLoggedInError
from homecloud_core.session import (
    get_access_token,
    load_session,
    set_access_token,
)


class AsyncCoreContext:
    """
    Async counterpart to :class:`CoreContext`.

    Interactive MFA prompts are not supported; use Access Keys or a JWT
    obtained outside the event loop.
    """

    def __init__(
        self,
        profile_name: str | None = None,
        *,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        account_id: str | None = None,
        apex: str | None = None,
    ) -> None:
        explicit = profile_name or env_profile()
        try:
            credentials = load_credentials()
            self.profile_name = explicit or credentials.default_profile or DEFAULT_PROFILE
            try:
                self.profile = credentials.get_profile(self.profile_name)
            except ValueError:
                self.profile = ProfileConfig(name=self.profile_name)
        except FileNotFoundError:
            self.profile_name = explicit or DEFAULT_PROFILE
            self.profile = ProfileConfig(name=self.profile_name)

        self._session = load_session().get(self.profile_name)
        self._apply_env_overrides()

        if access_key_id:
            self.profile.access_key_id = access_key_id
        if secret_access_key:
            self.profile.secret_access_key = secret_access_key
        if account_id:
            self.profile.default_account_id = account_id
            self._account_id = account_id
        else:
            self._account_id = None
        if apex:
            self.profile.apex = apex.strip().rstrip("/")

        self._transport = AsyncTransport(
            apex=self.profile.apex,
            access_key_id=self.profile.access_key_id,
            secret_access_key=self.profile.secret_access_key,
            access_token=self._session.access_token,
        )

    def _apply_env_overrides(self) -> None:
        if apex := env_apex():
            self.profile.apex = apex
        if account := env_account_id():
            self.profile.default_account_id = account
        if key_id := env_access_key_id():
            self.profile.access_key_id = key_id
        if secret := env_secret_access_key():
            self.profile.secret_access_key = secret

    @property
    def transport(self) -> AsyncTransport:
        return self._transport

    @property
    def has_access_key(self) -> bool:
        return bool(self.profile.access_key_id and self.profile.secret_access_key)

    @property
    def has_console_session(self) -> bool:
        return bool(self._transport.access_token)

    async def aclose(self) -> None:
        await self._transport.aclose()

    def require_access_key(self) -> None:
        if not self.has_access_key:
            raise NotConfiguredError(
                "Access Key not configured. Pass access_key_id/secret_access_key, "
                "set HOMECLOUD_ACCESS_KEY_ID / HC_ACCESS_KEY_ID, or run: homecloud configure"
            )

    def require_console_session(self) -> None:
        if not self.has_console_session:
            raise NotLoggedInError(
                "This operation needs a console JWT (human session). "
                "For automation use Access Key data-plane APIs instead. "
                "Interactive: await client.login(...) or homecloud login"
            )

    async def account_id(self) -> str:
        if self._account_id is not None:
            return self._account_id
        try:
            account_id = resolve_account_id(self.profile, self._session)
        except NotConfiguredError:
            self.require_access_key()
            account_id = await self._transport.resolve_access_key_account_id()
        remember_account(self.profile_name, account_id)
        self._account_id = account_id
        return account_id

    def _apply_access_token(self, token: str) -> None:
        set_access_token(self.profile_name, token)
        self._transport.access_token = token
        self._session = load_session().get(self.profile_name)

    async def login(self, username: str, password: str, *, mfa_code: str | None = None) -> None:
        """Console login without interactive MFA prompts (optional ``mfa_code``)."""
        body: dict[str, Any] = {"username": username, "password": password}
        if mfa_code:
            body["mfa_code"] = mfa_code

        data = await self._transport.console_request(
            "POST",
            "auth/login",
            json=body,
            require_auth=False,
        )
        token = data.get("access_token")
        if not token:
            raise HomeCloudError("Login failed")
        self._apply_access_token(str(token))
        await self._auto_select_account()

    async def login_browser(
        self,
        *,
        open_browser: bool = True,
        on_waiting: Callable[[str], None] | None = None,
    ) -> None:
        """Browser/passkey console login — polls asynchronously."""
        start = await self._transport.console_request(
            "POST",
            "auth/cli/session",
            require_auth=False,
        )
        session_id = start.get("session_id")
        verification_uri = start.get("verification_uri")
        if not session_id or not verification_uri:
            raise HomeCloudError("Failed to start browser login session")

        expires_in = int(start.get("expires_in") or 600)
        interval = max(1, int(start.get("interval") or 2))
        deadline = time.monotonic() + expires_in

        if open_browser:
            webbrowser.open(str(verification_uri))
        if on_waiting:
            on_waiting(str(verification_uri))

        while time.monotonic() < deadline:
            poll = await self._transport.console_request(
                "GET",
                f"auth/cli/session/{session_id}",
                require_auth=False,
            )
            status = str(poll.get("status") or "")
            if status == "complete":
                token = poll.get("access_token")
                if not token:
                    raise HomeCloudError("Browser login completed without access token")
                self._apply_access_token(str(token))
                await self._auto_select_account()
                return
            if status == "expired":
                raise HomeCloudError("Browser login session expired")
            await asyncio.sleep(interval)

        raise HomeCloudError("Browser login timed out")

    async def _auto_select_account(self) -> None:
        if self._session.active_account_id or self.profile.default_account_id:
            return
        accounts = await self.list_accounts()
        if len(accounts) == 1:
            remember_account(self.profile_name, str(accounts[0]["id"]))

    async def list_accounts(self) -> list[dict[str, Any]]:
        self.require_console_session()
        data = await self._transport.console_request("GET", "accounts")
        return data.get("items", data if isinstance(data, list) else [])

    async def switch_account(self, account_ref: str) -> None:
        accounts = await self.list_accounts()
        match = next(
            (
                account
                for account in accounts
                if str(account.get("id")) == account_ref
                or str(account.get("slug")) == account_ref
                or str(account.get("name")) == account_ref
            ),
            None,
        )
        if not match:
            raise HomeCloudError(f"Account not found: {account_ref}")
        remember_account(self.profile_name, str(match["id"]))
        self._account_id = str(match["id"])

    def config_summary(self) -> dict[str, Any]:
        from homecloud_core.config import credentials_path, load_credentials, mask_secret
        from homecloud_core.session import session_path

        try:
            load_credentials()
            configured = True
        except FileNotFoundError:
            configured = False

        return {
            "profile": self.profile_name,
            "apex": self.profile.apex,
            "credentials_file": str(credentials_path()),
            "session_file": str(session_path()),
            "configured": configured,
            "has_access_key": self.has_access_key,
            "has_console_session": self.has_console_session,
            "access_key_id": self.profile.access_key_id,
            "secret_access_key": mask_secret(self.profile.secret_access_key),
            "logged_in": bool(get_access_token(self.profile_name)),
            "has_account": bool(
                self._account_id
                or self._session.active_account_id
                or self.profile.default_account_id
            ),
        }

    # Re-use sync static helpers for credentials file writes.
    configure_profile = staticmethod(CoreContext.configure_profile)
    import_credentials_file = staticmethod(CoreContext.import_credentials_file)
