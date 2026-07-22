"""SDK Function URL helpers."""

from homecloud_core.defaults import function_url
from homecloud_core.signing import sign_request_headers


def test_function_url_builder():
    assert function_url("Hello", "holab.abrdns.com") == "https://hello.func.holab.abrdns.com"


def test_sign_headers_for_function_path():
    headers = sign_request_headers(
        access_key_id="HCAKTEST",
        secret="secret",
        method="POST",
        path="/",
        account_id="00000000-0000-0000-0000-000000000001",
    )
    assert "X-Homecloud-Access-Key-Id" in headers
    assert "X-Homecloud-Signature" in headers
    assert len(headers["X-Homecloud-Signature"]) == 64
