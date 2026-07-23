# @homecloud-platform/sdk (Node.js)

Part of the **homecloud-sdk** monorepo — Python at repo root; Node in `js/`.

**Expectation:** Node supports the **same product surface** as Python (`homecloud-sdk`), released under the **same** `v*` version. See [PARITY.md](./PARITY.md).

Shipped as of **0.5.0**: SO / MQ / Secrets / Mail / Functions / Apps / Accounts / Queues, typed errors, `fromEnv` / `fromProfile` / `fromCredentials` / `fromSts` / `fromFunctionContext`, console login helpers.

## Install

```bash
npm install @homecloud-platform/sdk
```

From a local checkout (lab / layers):

```json
{
  "dependencies": {
    "@homecloud-platform/sdk": "file:../../../homecloud-sdk/js"
  }
}
```

## Usage (MVP — STS + SO)

```js
const { HomeCloud } = require("@homecloud-platform/sdk");

exports.handler = async (event, context) => {
  const client = HomeCloud.fromSts(context.sts.archive, {
    accountId: context.account_id,
  });
  await client.so.putJson("my-bucket", "proof/ok.json", { ok: true });
  return { ok: true };
};
```

## Unified release (Python + Node)

One tag publishes **both** registries with the **same** version:

```bash
./scripts/bump-version.sh 0.5.0
git add pyproject.toml js/package.json
git commit -m "Release 0.5.0"
git push origin HEAD
git tag v0.5.0
git push origin v0.5.0
```

| Registry | Package | Trigger |
|----------|---------|---------|
| PyPI | `homecloud-sdk` | tag `v0.5.0` |
| npm | `@homecloud-platform/sdk` | same tag `v0.5.0` |

Workflows sync the version from the tag before publish (Trusted Publishing / OIDC).

Optional npm-only hotfix (no PyPI): `js-v0.5.1`.

### One-time npm setup

1. Org **homecloud-platform** on npm.
2. First publish once locally: `cd js && npm publish --access public`
3. Package → **Trusted Publisher** → GitHub Actions:
   - Org `HomeCloudLab`, repo `homecloud-sdk`
   - Workflow: `publish-npm.yml`
   - Environment: `npm`
4. GitHub → Environments → create **`npm`** (and **`pypi`** already for Python).
