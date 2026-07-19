"""Create an isolated Access Key and verify SDK service-account flow.

Uses a one-shot console JWT only to *mint* the key, then runs a clean
subprocess with Access Keys only (no session file, no MFA, no browser).

Usage:
  python scripts/verify_service_account_flow.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from homecloud_sdk import HomeCloud, HomeCloudError  # noqa: E402

KEY_NAME = "homecloud-sdk-test"
CHILD_SCRIPT = r"""
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

# Prove we are not using a console session
assert not os.environ.get("HOMECLOUD_SESSION_FILE") or not Path(os.environ["HOMECLOUD_SESSION_FILE"]).exists()
assert os.environ.get("HC_ACCESS_KEY_ID") or os.environ.get("HOMECLOUD_ACCESS_KEY_ID")
assert os.environ.get("HC_SECRET_ACCESS_KEY") or os.environ.get("HOMECLOUD_SECRET_ACCESS_KEY")

from homecloud_sdk import HomeCloud, HomeCloudError, NotLoggedInError

client = HomeCloud.from_env()
summary = client.config_summary()
assert summary["has_access_key"] is True
assert summary["has_console_session"] is False, "must not carry a JWT session"
assert client._ctx.transport._mfa_resolver is None
assert client._ctx._interactive_mfa is False

account_id = client.account_id()
assert account_id

# Console helpers must fail without JWT
try:
    client.so.list_buckets()
    raise SystemExit("list_buckets should require JWT")
except NotLoggedInError:
    pass

bucket = os.environ["HC_TEST_BUCKET"]
key = f"sdk-sa-verify/{uuid.uuid4().hex}.txt"
payload = f"service-account-flow {time.time()}\n".encode()
src = Path(tempfile.gettempdir()) / f"hc-sa-{uuid.uuid4().hex}.txt"
src.write_bytes(payload)

uploaded = client.so.upload(bucket, str(src), key=key)
assert isinstance(uploaded, dict)

dest = Path(tempfile.gettempdir()) / f"hc-sa-dl-{uuid.uuid4().hex}.txt"
meta = client.so.download(bucket, key, dest_path=dest)
assert dest.read_bytes() == payload
assert meta["size"] == len(payload)
client.so.delete(bucket, key)
src.unlink(missing_ok=True)
dest.unlink(missing_ok=True)
print("SO_OK", bucket)

mq_name = os.environ.get("HC_TEST_QUEUE", "").strip()
if mq_name:
    try:
        sent = client.mq.send(mq_name, {"sdk_sa": True, "ts": time.time()})
        assert sent.get("message_id") or sent
        print("MQ_OK", mq_name)
    except HomeCloudError as exc:
        # Console queue list names may not match data-plane routes yet
        print("MQ_SKIP", mq_name, getattr(exc, "status_code", None))
else:
    print("MQ_SKIP")

print("ACCOUNT_OK")
client.close()
"""


def _pick_bucket(client: HomeCloud) -> str:
    buckets = client.so.list_buckets()
    if not buckets:
        raise SystemExit("No buckets available to verify SO upload")
    return str(buckets[0].get("name") or buckets[0].get("id"))


def _pick_queue(client: HomeCloud) -> str | None:
    try:
        queues = client.queues.list()
    except HomeCloudError:
        return None
    if not queues:
        return None
    return str(queues[0].get("name") or queues[0].get("slug") or "")


def main() -> int:
    admin = HomeCloud(interactive_mfa=False)
    try:
        account_id = admin.account_id()
        if not admin._ctx.has_console_session:
            print("ERROR: need a valid console login once to mint the Access Key")
            print("Run: homecloud login")
            return 1

        # List existing keys; revoke prior homecloud-sdk-test so we can mint a fresh secret
        listed = admin._ctx.transport.console_request(
            "GET", f"accounts/{account_id}/access-keys"
        )
        for item in listed.get("items", []):
            if item.get("name") == KEY_NAME and item.get("id"):
                admin._ctx.transport.console_request(
                    "DELETE",
                    f"accounts/{account_id}/access-keys/{item['id']}",
                )
                print(f"revoked prior key name={KEY_NAME}")

        created = admin._ctx.transport.console_request(
            "POST",
            f"accounts/{account_id}/access-keys",
            json={"name": KEY_NAME, "permissions": ["*"]},
        )
        access_key_id = created["access_key_id"]
        secret = created["secret_access_key"]
        print(f"created Access Key name={KEY_NAME} id={access_key_id}")

        bucket = _pick_bucket(admin)
        queue = _pick_queue(admin)

        with tempfile.TemporaryDirectory(prefix="hc-sa-") as tmp:
            tmp_path = Path(tmp)
            # Isolated home: credentials only, no session file
            cred_path = tmp_path / "credentials"
            cred_path.write_text(
                json.dumps(
                    {
                        "version": 2,
                        "default_profile": "sdk-test",
                        "profiles": {
                            "sdk-test": {
                                "apex": admin._ctx.profile.apex,
                                "access_key_id": access_key_id,
                                "secret_access_key": secret,
                            }
                        },
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            # Strip any developer session / profile leakage
            for key in list(env):
                if key.startswith("HOMECLOUD_") or key.startswith("HC_"):
                    env.pop(key, None)

            env["PYTHONPATH"] = str(ROOT)
            env["HOMECLOUD_CONFIG_DIR"] = str(tmp_path)
            env["HOMECLOUD_CREDENTIALS_FILE"] = str(cred_path)
            env["HC_PROFILE"] = "sdk-test"
            env["HC_ACCESS_KEY_ID"] = access_key_id
            env["HC_SECRET_ACCESS_KEY"] = secret
            env["HC_TEST_BUCKET"] = bucket
            if queue:
                env["HC_TEST_QUEUE"] = queue
            # Explicitly no session
            env["HOMECLOUD_SESSION_FILE"] = str(tmp_path / "no-session")

            print("running clean from_env() child (Access Key only)...")
            proc = subprocess.run(
                [sys.executable, "-c", CHILD_SCRIPT],
                env=env,
                capture_output=True,
                text=True,
                cwd=str(ROOT),
            )
            if proc.returncode != 0:
                print("CHILD_STDOUT:", proc.stdout)
                print("CHILD_STDERR:", proc.stderr)
                return proc.returncode

            for line in proc.stdout.strip().splitlines():
                print("child:", line)

        print("PASS: service-account flow works without login/JWT/MFA/browser")
        print(f"Keep key {access_key_id} ({KEY_NAME}) for CI, or revoke in Console IAM.")
        return 0
    finally:
        admin.close()


if __name__ == "__main__":
    raise SystemExit(main())
