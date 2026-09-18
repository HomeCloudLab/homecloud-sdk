"""Unit tests for secrets key helpers and put payload resolution."""

from __future__ import annotations

import pytest

from homecloud_core.errors import HomeCloudError
from homecloud_sdk.secret_formats import parse_secret_format, serialize_secret_format
from homecloud_sdk.services import _resolve_put_payload, _secrets_keys_params


def test_secrets_keys_params_normalizes():
    assert _secrets_keys_params(None) is None
    assert _secrets_keys_params([]) is None
    assert _secrets_keys_params("API_KEY") == {"keys": ["API_KEY"]}
    assert _secrets_keys_params(["A", "B,C", "A"]) == {"keys": ["A", "B", "C"]}


def test_resolve_put_payload_fields_and_string():
    assert _resolve_put_payload(None, format=None, fields={"API_KEY": "test"}) == {"API_KEY": "test"}
    assert _resolve_put_payload("API_KEY=x", format="env", fields={}) == {"API_KEY": "x"}
    assert _resolve_put_payload("API_KEY=x", format=None, fields={}) == {"API_KEY": "x"}
    assert _resolve_put_payload({"API_KEY": "x"}, format=None, fields={}) == {"API_KEY": "x"}


def test_resolve_put_payload_rejects_mixed():
    with pytest.raises(HomeCloudError, match="not both"):
        _resolve_put_payload({"A": "1"}, format=None, fields={"B": "2"})
    with pytest.raises(HomeCloudError, match="format applies"):
        _resolve_put_payload(None, format="env", fields={"API_KEY": "x"})


def test_format_roundtrip_env():
    values = {"API_KEY": "x", "DB_HOST": "db"}
    text = serialize_secret_format("env", values)
    assert parse_secret_format("env", text) == values
    assert not text.endswith("\n")
