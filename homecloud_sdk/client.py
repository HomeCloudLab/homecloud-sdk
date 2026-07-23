"""Single public entry point for CLI and SDK consumers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homecloud_core.context import CoreContext
from homecloud_core.env import env_access_key_id, env_account_id, env_apex, env_profile, env_secret_access_key
from homecloud_core.errors import HomeCloudError
from homecloud_sdk.services import (
    AccountsAPI,
    AppsAPI,
    FunctionsAPI,
    MailAPI,
    MqAPI,
    QueuesAPI,
    SecretsAPI,
    SoAPI,
)


class HomeCloudClient:
    """
    HomeCloud SDK client.

    **Primary (automation / servers):** Access Key credentials — no MFA, no JWT.

    ```python
    client = HomeCloudClient(
        access_key_id="HCAK...",
        secret_access_key="...",
    )
    # or
    client = HomeCloudClient.from_env()
    # or ~/.homecloud/credentials (+ HC_PROFILE)
    client = HomeCloudClient()
    ```

    **Interactive (CLI / tools only):** ``login`` / ``login_browser`` mint a console JWT
    for management-plane helpers (list buckets via console, apps, etc.). MFA may apply
    there; it never applies to data-plane Access Key requests.
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
        mfa_code: str | None = None,
        interactive_mfa: bool = False,
        mfa_prompt: Callable[[str], str] | None = None,
        mfa_choose_method: Callable[[list[str], list[dict] | None], str] | None = None,
        session_token: str | None = None,
        data_plane_bases: dict[str, str] | None = None,
        console_base_url: str | None = None,
    ) -> None:
        key_id = access_key_id or access_key
        secret = secret_access_key or secret_key
        self._ctx = CoreContext(
            profile,
            access_key_id=key_id,
            secret_access_key=secret,
            account_id=account_id,
            apex=apex,
            mfa_code=mfa_code,
            mfa_prompt=mfa_prompt,
            interactive_mfa=interactive_mfa,
            mfa_choose_method=mfa_choose_method,
            session_token=session_token,
            data_plane_bases=data_plane_bases,
            console_base_url=console_base_url,
        )

    @classmethod
    def from_env(cls, **kwargs: Any) -> HomeCloudClient:
        """Build from ``HOMECLOUD_*`` / ``HC_*`` env (falls back to credentials file)."""
        return cls(
            profile=kwargs.pop("profile", None) or env_profile(),
            access_key_id=kwargs.pop("access_key_id", None) or env_access_key_id(),
            secret_access_key=kwargs.pop("secret_access_key", None) or env_secret_access_key(),
            account_id=kwargs.pop("account_id", None) or env_account_id(),
            apex=kwargs.pop("apex", None) or env_apex(),
            interactive_mfa=kwargs.pop("interactive_mfa", False),
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
        session_token: str | None = None,
    ) -> HomeCloudClient:
        """Explicit Access Key client — preferred for CI and long-running services."""
        return cls(
            profile=profile,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            account_id=account_id,
            apex=apex,
            session_token=session_token,
            interactive_mfa=False,
        )

    @classmethod
    def from_sts(
        cls,
        sts: dict[str, Any],
        *,
        account_id: str | None = None,
        apex: str | None = None,
    ) -> HomeCloudClient:
        """Build from a function STS entry (``context["sts"][binding]`` / ``HC_STS_JSON``)."""
        import os
        from urllib.parse import urlparse

        aid = account_id or os.environ.get("HC_ACCOUNT_ID") or env_account_id()
        base = str(sts.get("base_url") or sts.get("mail_base_url") or "").rstrip("/")
        resource_type = str(sts.get("resource_type") or "").strip().lower()
        resolved_apex = apex or env_apex()
        console_base: str | None = None
        data_plane_bases: dict[str, str] = {}
        if base:
            host = urlparse(base).hostname or ""
            if resource_type == "mail":
                # Automation always uses mailapi (ADR-033). Rewrite legacy console STS.
                from homecloud_core.defaults import mail_api_url

                if host.startswith("console.") or "/api/v1" in base:
                    if host.startswith("console."):
                        resolved_apex = resolved_apex or host[len("console.") :]
                    if not resolved_apex:
                        from homecloud_core.defaults import DEFAULT_APEX

                        resolved_apex = DEFAULT_APEX
                    data_plane_bases["mail"] = mail_api_url(resolved_apex).rstrip("/")
                else:
                    data_plane_bases["mail"] = base
                    if host.startswith("mailapi."):
                        resolved_apex = resolved_apex or host[len("mailapi.") :]
            elif resource_type in {"so", "mq", "secrets"}:
                data_plane_bases[resource_type] = base
                prefix = f"{resource_type}."
                if host.startswith(prefix):
                    resolved_apex = resolved_apex or host[len(prefix) :]
        elif resource_type == "mail":
            from homecloud_core.defaults import DEFAULT_APEX, mail_api_url

            resolved_apex = resolved_apex or DEFAULT_APEX
            data_plane_bases["mail"] = mail_api_url(resolved_apex).rstrip("/")
        if not resolved_apex:
            from homecloud_core.defaults import DEFAULT_APEX

            resolved_apex = DEFAULT_APEX
        return cls(
            access_key_id=str(sts["access_key_id"]),
            secret_access_key=str(sts["secret_access_key"]),
            account_id=aid,
            apex=resolved_apex,
            session_token=str(sts["session_token"]) if sts.get("session_token") else None,
            data_plane_bases=data_plane_bases or None,
            console_base_url=console_base,
            interactive_mfa=False,
        )

    @classmethod
    def from_function_context(
        cls,
        context: dict[str, Any] | None,
        *,
        binding: str,
    ) -> HomeCloudClient:
        """Preferred in function handlers: STS from Bindings via ``context["sts"]``."""
        import json
        import os

        ctx = context or {}
        sts_map = dict(ctx.get("sts") or {})
        if not sts_map:
            raw = os.environ.get("HC_STS_JSON")
            if raw:
                try:
                    sts_map = json.loads(raw)
                except Exception:
                    sts_map = {}
        entry = sts_map.get(binding)
        if not entry or not isinstance(entry, dict):
            raise HomeCloudError(
                f"Missing STS for binding '{binding}'. "
                "Set Bindings + execution_role on the function (no manual Access Key ENV needed)."
            )
        account_id = str(ctx.get("account_id") or os.environ.get("HC_ACCOUNT_ID") or "") or None
        return cls.from_sts(entry, account_id=account_id)

    @classmethod
    def from_profile(cls, profile: str, **kwargs: Any) -> HomeCloudClient:
        return cls(profile=profile, **kwargs)

    def close(self) -> None:
        self._ctx.close()

    def __enter__(self) -> HomeCloudClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def accounts(self) -> AccountsAPI:
        return AccountsAPI(self._ctx)

    @property
    def apps(self) -> AppsAPI:
        return AppsAPI(self._ctx)

    @property
    def queues(self) -> QueuesAPI:
        return QueuesAPI(self._ctx)

    @property
    def mq(self) -> MqAPI:
        return MqAPI(self._ctx)

    @property
    def so(self) -> SoAPI:
        return SoAPI(self._ctx)

    @property
    def storage(self) -> SoAPI:
        """Alias for so — prefer client.so."""
        return self.so

    @property
    def secrets(self) -> SecretsAPI:
        return SecretsAPI(self._ctx)

    @property
    def mail(self) -> MailAPI:
        return MailAPI(self._ctx)

    @property
    def functions(self) -> FunctionsAPI:
        return FunctionsAPI(self._ctx)

    def login(self, username: str, password: str, *, mfa_code: str | None = None) -> None:
        """Interactive console JWT login (CLI/tools). Not for unattended automation."""
        self._ctx.login(username, password, mfa_code=mfa_code)

    def login_browser(
        self,
        *,
        open_browser: bool = True,
        on_waiting: Callable[[str], None] | None = None,
        mfa_token: str | None = None,
    ) -> None:
        """Interactive browser/passkey login (CLI/tools)."""
        self._ctx.login_browser(
            open_browser=open_browser,
            on_waiting=on_waiting,
            mfa_token=mfa_token,
        )

    def configure(
        self,
        *,
        access_key_id: str,
        secret_access_key: str,
        default_account_id: str | None = None,
    ) -> None:
        CoreContext.configure_profile(
            profile_name=self._ctx.profile_name,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            default_account_id=default_account_id,
        )

    def import_credentials(self, raw: dict[str, Any]) -> None:
        CoreContext.import_credentials_file(raw, profile_name=self._ctx.profile_name)

    def config_summary(self) -> dict[str, Any]:
        return self._ctx.config_summary()

    def account_id(self) -> str:
        return self._ctx.account_id()


# AWS-style short alias
HomeCloud = HomeCloudClient
