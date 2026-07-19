"""Async public entry point for HomeCloud SDK consumers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homecloud_core.async_context import AsyncCoreContext
from homecloud_core.env import env_access_key_id, env_account_id, env_apex, env_profile, env_secret_access_key
from homecloud_sdk.async_services import (
    AsyncAccountsAPI,
    AsyncAppsAPI,
    AsyncMqAPI,
    AsyncQueuesAPI,
    AsyncSecretsAPI,
    AsyncSoAPI,
)


class AsyncHomeCloudClient:
    """
    Async HomeCloud SDK client (``httpx.AsyncClient``).

    Prefer Access Keys for automation. Interactive MFA prompts are not supported;
    pass ``mfa_code`` to ``login`` if needed, or obtain a JWT outside the loop.
    """

    def __init__(
        self,
        profile: str | None = None,
        *,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        account_id: str | None = None,
        apex: str | None = None,
    ) -> None:
        key_id = access_key_id or access_key
        secret = secret_access_key or secret_key
        self._ctx = AsyncCoreContext(
            profile,
            access_key_id=key_id,
            secret_access_key=secret,
            account_id=account_id,
            apex=apex,
        )

    @classmethod
    def from_env(cls, **kwargs: Any) -> AsyncHomeCloudClient:
        return cls(
            profile=kwargs.pop("profile", None) or env_profile(),
            access_key_id=kwargs.pop("access_key_id", None) or env_access_key_id(),
            secret_access_key=kwargs.pop("secret_access_key", None) or env_secret_access_key(),
            account_id=kwargs.pop("account_id", None) or env_account_id(),
            apex=kwargs.pop("apex", None) or env_apex(),
            **kwargs,
        )

    @classmethod
    def from_credentials(
        cls,
        access_key_id: str,
        secret_access_key: str,
        *,
        account_id: str | None = None,
        apex: str | None = None,
        profile: str | None = None,
    ) -> AsyncHomeCloudClient:
        return cls(
            profile=profile,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            account_id=account_id,
            apex=apex,
        )

    @classmethod
    def from_profile(cls, profile: str, **kwargs: Any) -> AsyncHomeCloudClient:
        return cls(profile=profile, **kwargs)

    async def aclose(self) -> None:
        await self._ctx.aclose()

    async def __aenter__(self) -> AsyncHomeCloudClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    @property
    def accounts(self) -> AsyncAccountsAPI:
        return AsyncAccountsAPI(self._ctx)

    @property
    def apps(self) -> AsyncAppsAPI:
        return AsyncAppsAPI(self._ctx)

    @property
    def queues(self) -> AsyncQueuesAPI:
        return AsyncQueuesAPI(self._ctx)

    @property
    def mq(self) -> AsyncMqAPI:
        return AsyncMqAPI(self._ctx)

    @property
    def so(self) -> AsyncSoAPI:
        return AsyncSoAPI(self._ctx)

    @property
    def storage(self) -> AsyncSoAPI:
        return self.so

    @property
    def secrets(self) -> AsyncSecretsAPI:
        return AsyncSecretsAPI(self._ctx)

    async def login(self, username: str, password: str, *, mfa_code: str | None = None) -> None:
        await self._ctx.login(username, password, mfa_code=mfa_code)

    async def login_browser(
        self,
        *,
        open_browser: bool = True,
        on_waiting: Callable[[str], None] | None = None,
    ) -> None:
        await self._ctx.login_browser(open_browser=open_browser, on_waiting=on_waiting)

    def configure(
        self,
        *,
        access_key_id: str,
        secret_access_key: str,
        default_account_id: str | None = None,
    ) -> None:
        AsyncCoreContext.configure_profile(
            profile_name=self._ctx.profile_name,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            default_account_id=default_account_id,
        )

    def import_credentials(self, raw: dict[str, Any]) -> None:
        AsyncCoreContext.import_credentials_file(raw, profile_name=self._ctx.profile_name)

    def config_summary(self) -> dict[str, Any]:
        return self._ctx.config_summary()

    async def account_id(self) -> str:
        return await self._ctx.account_id()


AsyncHomeCloud = AsyncHomeCloudClient
