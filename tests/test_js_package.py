"""HomeCloud SDK — Node.js packaging smoke (pytest).

Ensures the monorepo ``js/`` package stays loadable and SigV1 helpers match
Python expectations.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "js"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
def test_js_package_npm_test() -> None:
    assert (JS / "package.json").is_file()
    assert (JS / "src" / "index.js").is_file()
    proc = subprocess.run(
        ["node", "--test", str(JS / "test" / "signing.test.js")],
        cwd=str(JS),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
def test_js_sign_matches_python_hmac_length() -> None:
    from homecloud_core.signing import sign_request_headers

    py = sign_request_headers(
        access_key_id="HCAKTEST",
        secret="secret",
        method="GET",
        path="/acct/bucket/objects",
        account_id="acct",
    )
    script = (
        "const { signRequestHeaders } = require('./src/index.js');"
        "const h = signRequestHeaders({"
        "  accessKeyId: 'HCAKTEST',"
        "  secret: 'secret',"
        "  method: 'GET',"
        "  path: '/acct/bucket/objects',"
        "  accountId: 'acct',"
        "});"
        "process.stdout.write(JSON.stringify({"
        "  sigLen: h['X-Homecloud-Signature'].length,"
        "  key: h['X-Homecloud-Access-Key-Id'],"
        "}));"
    )
    proc = subprocess.run(
        ["node", "-e", script],
        cwd=str(JS),
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(proc.stdout)
    assert data["key"] == "HCAKTEST"
    assert data["sigLen"] == 64
    assert len(py["X-Homecloud-Signature"]) == 64
