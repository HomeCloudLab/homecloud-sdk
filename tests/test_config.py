from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from homecloud_core.config import (
    CredentialsFile,
    ProfileConfig,
    load_credentials,
    save_credentials,
    upsert_profile,
)
from homecloud_core.session import load_session, session_path, set_access_token


def test_load_flat_ui_format(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cred_file = tmp_path / "credentials"
    cred_file.write_text(
        json.dumps(
            {
                "version": 1,
                "access_key_id": "HCAKTEST",
                "secret_access_key": "secret",
                "default_account_id": "acc-1",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HOMECLOUD_CREDENTIALS_FILE", str(cred_file))

    profile = load_credentials().get_profile()
    assert profile.access_key_id == "HCAKTEST"
    assert profile.default_account_id == "acc-1"


def test_credentials_exclude_jwt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cred_file = tmp_path / "credentials"
    monkeypatch.setenv("HOMECLOUD_CREDENTIALS_FILE", str(cred_file))

    upsert_profile(
        ProfileConfig(
            name="default",
            default_account_id="acc-1",
            access_key_id="HCAK1",
            secret_access_key="secret",
        )
    )

    raw = json.loads(cred_file.read_text(encoding="utf-8"))
    assert "access_token" not in json.dumps(raw)


def test_session_stores_jwt_separately(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))

    set_access_token("default", "eyJ.test.token")
    session = load_session()
    assert session.get("default").access_token == "eyJ.test.token"
    assert session_path().exists()


def test_save_credentials_permissions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cred_file = tmp_path / "credentials"
    monkeypatch.setenv("HOMECLOUD_CREDENTIALS_FILE", str(cred_file))

    save_credentials(
        CredentialsFile(
            version=2,
            default_profile="prod",
            profiles={
                "prod": ProfileConfig(
                    name="prod",
                    default_account_id="acc-prod",
                    access_key_id="HCAKPROD",
                    secret_access_key="secret-prod",
                )
            },
        )
    )

    if sys.platform != "win32":
        assert cred_file.stat().st_mode & 0o777 == 0o600
