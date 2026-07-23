"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const {
  signRequestHeaders,
  HomeCloud,
  HomeCloudError,
  soUrl,
  mailApiUrl,
} = require("../src/index.js");

test("signRequestHeaders produces SigV1 headers", () => {
  const h = signRequestHeaders({
    accessKeyId: "HCAKTEST",
    secret: "secret",
    method: "GET",
    path: "/acct/bucket/objects",
    accountId: "acct",
  });
  assert.equal(h["X-Homecloud-Access-Key-Id"], "HCAKTEST");
  assert.ok(h["X-Homecloud-Date"]);
  assert.equal(h["X-Homecloud-Signature"].length, 64);
});

test("fromSts rewrites console mail to mailapi", () => {
  const c = HomeCloud.fromSts(
    {
      access_key_id: "k",
      secret_access_key: "s",
      resource_type: "mail",
      base_url: "https://console.holab.abrdns.com/api/v1",
    },
    { accountId: "a", apex: "holab.abrdns.com" }
  );
  assert.equal(c.baseUrl("mail"), "https://mailapi.holab.abrdns.com");
});

test("fromSts keeps so base_url and derives apex", () => {
  const c = HomeCloud.fromSts(
    {
      access_key_id: "k",
      secret_access_key: "s",
      resource_type: "so",
      base_url: "https://so.holab.abrdns.com",
      resource_name: "my-bucket",
    },
    { accountId: "acct-1" }
  );
  assert.equal(c.accountId, "acct-1");
  assert.equal(c.baseUrl("so"), "https://so.holab.abrdns.com");
  assert.equal(c.apex, "holab.abrdns.com");
});

test("fromFunctionContext reads binding from context.sts", () => {
  const c = HomeCloud.fromFunctionContext(
    {
      account_id: "acct",
      sts: {
        archive: {
          access_key_id: "k",
          secret_access_key: "s",
          resource_type: "so",
          base_url: "https://so.example.com",
        },
      },
    },
    { binding: "archive" }
  );
  assert.equal(c.baseUrl("so"), "https://so.example.com");
});

test("fromFunctionContext missing binding throws", () => {
  assert.throws(
    () => HomeCloud.fromFunctionContext({ sts: {} }, { binding: "missing" }),
    (err) => err instanceof HomeCloudError
  );
});

test("default endpoint helpers", () => {
  assert.equal(soUrl("holab.abrdns.com"), "https://so.holab.abrdns.com");
  assert.equal(mailApiUrl("holab.abrdns.com"), "https://mailapi.holab.abrdns.com");
});
