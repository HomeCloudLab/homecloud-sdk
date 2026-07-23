# @homecloud-platform/sdk (Node.js)

Part of the **homecloud-sdk** monorepo — Python at repo root; Node in `js/`.

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

## Usage

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

## Publish (GitHub Actions only)

Tags for Node are **separate** from Python PyPI (`v*`):

| Registry | Tag | Example |
|----------|-----|---------|
| PyPI `homecloud-sdk` | `v*` | `v0.4.9` |
| npm `@homecloud-platform/sdk` | `js-v*` | `js-v0.1.0` |

```bash
# bump version in js/package.json if you like, then:
git tag js-v0.1.0
git push origin js-v0.1.0
```

Workflow: `.github/workflows/publish-npm.yml` (Trusted Publishing / OIDC, environment `npm`).

### One-time npm setup

1. Create org **homecloud-platform** on npm (done).
2. **First publish** (once, from a trusted machine after `npm login`):
   ```bash
   cd js
   npm publish --access public
   ```
3. On https://www.npmjs.com/package/@homecloud-platform/sdk → **Settings → Trusted Publisher**:
   - Provider: GitHub Actions
   - Organization: `HomeCloudLab`
   - Repository: `homecloud-sdk`
   - Workflow filename: `publish-npm.yml` (filename only)
   - Environment: `npm`
4. In GitHub repo **Settings → Environments**, create environment **`npm`** (optional protection rules).
5. Later releases: only push `js-v*` tags — no local publish, no npm token in secrets.
