# @homecloud/sdk (Node.js)

Part of the **homecloud-sdk** monorepo — Python lives at the repo root; Node lives in `js/`.

Minimal HomeCloud Functions SDK for `nodejs20` (ADR-025e / ADR-033).

## Install

From a function workspace / layer (path relative to your checkout):

```json
{
  "dependencies": {
    "@homecloud/sdk": "file:../../../homecloud-sdk/js"
  }
}
```

Or publish to npm later from this directory.

## Usage

```js
const { HomeCloud } = require("@homecloud/sdk");

exports.handler = async (event, context) => {
  const client = HomeCloud.fromSts(context.sts.archive, {
    accountId: context.account_id,
  });
  await client.so.putJson("my-bucket", "proof/ok.json", { ok: true });
  return { ok: true };
};
```

`fromSts` rewrites legacy console mail STS hosts to `mailapi.{apex}` (same as Python SDK ≥0.4.9).

## Develop / test

```bash
cd js
npm test
```
