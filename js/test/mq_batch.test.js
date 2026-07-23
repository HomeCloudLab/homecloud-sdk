"use strict";

const { test } = require("node:test");
const assert = require("node:assert/strict");
const { buildMqBatchEntries } = require("../src/mq.js");

test("buildMqBatchEntries normalizes payloads", () => {
  const entries = buildMqBatchEntries([{ a: 1 }, "plain"]);
  assert.deepEqual(entries[0], { id: "0", body: '{"a":1}' });
  assert.deepEqual(entries[1], { id: "1", body: "plain" });
});

test("buildMqBatchEntries rejects over limit", () => {
  assert.throws(
    () => buildMqBatchEntries(Array.from({ length: 11 }, (_, i) => ({ i }))),
    /1–10/
  );
});
