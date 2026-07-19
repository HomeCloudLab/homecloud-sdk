"""Central MFA challenge handling for console API calls."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homecloud_core.errors import HomeCloudError

PromptFn = Callable[[str], str]
MfaMethodChooser = Callable[[list[str], list[dict] | None], str]


class PreferBrowserLogin(Exception):
    """User chose passkey/browser to finish authentication.

    When ``mfa_token`` is set, password was already verified — browser should
    resume MFA only (no second password prompt).
    """

    def __init__(
        self,
        *,
        mfa_token: str | None = None,
        methods: list[str] | None = None,
        passkeys: list[dict] | None = None,
    ) -> None:
        super().__init__("Prefer browser login")
        self.mfa_token = mfa_token
        self.methods = methods or []
        self.passkeys = passkeys or []


def is_mfa_required(exc: HomeCloudError) -> bool:
    return exc.status_code == 403 and exc.error_code == "MFA_REQUIRED"


def prompt_verification_code(prompt: PromptFn | None = None) -> str:
    """Prompt for TOTP or backup code. Never cache the result."""
    ask = prompt or (lambda msg: input(f"{msg}: ").strip())
    code = ask("Verification code")
    if not code:
        raise HomeCloudError("Verification code is required")
    return code.strip()


class MfaResolver:
    """
    Completes MFA_REQUIRED challenges for console requests.

    - Login challenge (``mfa_token`` in details): POST auth/login with mfa_token + mfa_code
    - Step-up (no mfa_token): retry original JSON body with mfa_code injected

    Passkeys raise PreferBrowserLogin so the CLI can open browser login.
    """

    def __init__(
        self,
        *,
        mfa_code: str | None = None,
        prompt: PromptFn | None = None,
        interactive: bool = True,
        choose_method: MfaMethodChooser | None = None,
    ) -> None:
        self._mfa_code = mfa_code
        self._prompt = prompt
        self._interactive = interactive
        self._choose_method = choose_method

    def obtain_code(
        self,
        *,
        methods: list[str] | None = None,
        passkeys: list[dict] | None = None,
        allow_browser_switch: bool = True,
        mfa_token: str | None = None,
    ) -> str:
        if self._mfa_code:
            code = self._mfa_code
            self._mfa_code = None  # one-shot — never reuse across challenges
            return code
        if not self._interactive:
            raise HomeCloudError(
                "MFA required. Re-run with --mfa-code, or use: homecloud login --browser"
            )

        methods = methods or []
        choice = "totp"
        if self._choose_method and methods:
            choice = self._choose_method(methods, passkeys)
        elif methods and "totp" not in methods and "passkey" in methods:
            choice = "browser"

        if choice == "browser":
            if not allow_browser_switch:
                raise HomeCloudError(
                    "Passkey confirmation is only available in the Console UI for this action."
                )
            raise PreferBrowserLogin(
                mfa_token=mfa_token,
                methods=methods,
                passkeys=passkeys,
            )

        return prompt_verification_code(self._prompt)

    def resolve(
        self,
        exc: HomeCloudError,
        *,
        method: str,
        path: str,
        json_body: Any | None,
        retry: Callable[..., Any],
    ) -> Any:
        details = exc.error_details
        mfa_token = details.get("mfa_token")
        methods_raw = details.get("methods") if isinstance(details.get("methods"), list) else None
        methods = [str(m) for m in methods_raw] if methods_raw else None
        passkeys_raw = details.get("passkeys")
        passkeys = passkeys_raw if isinstance(passkeys_raw, list) else None
        # Login challenge can switch to browser; step-up cannot.
        allow_browser = bool(mfa_token) or path.rstrip("/").endswith("auth/login")
        code = self.obtain_code(
            methods=methods,
            passkeys=[p for p in passkeys if isinstance(p, dict)] if passkeys else None,
            allow_browser_switch=allow_browser,
            mfa_token=str(mfa_token) if mfa_token else None,
        )

        if mfa_token:
            return retry(
                "POST",
                "auth/login",
                json={"mfa_token": mfa_token, "mfa_code": code},
                require_auth=False,
                _skip_mfa=True,
            )

        body = dict(json_body) if isinstance(json_body, dict) else {}
        body["mfa_code"] = code
        return retry(method, path, json=body, _skip_mfa=True)
