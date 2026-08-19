"""Shared testdata/contracts — Python must match Go/Terraform SigV1 vectors."""

from __future__ import annotations

import json
from pathlib import Path

from homecloud_core.signing import build_string_to_sign, compute_signature

ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "testdata" / "contracts" / "sigv1_vectors.json"


def test_shared_sigv1_vectors() -> None:
    data = json.loads(VECTORS.read_text(encoding="utf-8"))
    assert data, "expected sigv1 vectors"
    for row in data:
        got = build_string_to_sign(
            method=row["method"],
            path=row["path"],
            timestamp=row["timestamp"],
            account_id=row["account_id"],
        )
        assert got == row["string_to_sign"], row["name"]
        assert compute_signature(secret=row["secret"], string_to_sign=got) == row["signature"], row["name"]
