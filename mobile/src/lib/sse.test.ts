import assert from "node:assert/strict";
import { test } from "node:test";

import { parseBlock, readSse } from "./sse.ts";

function streamOf(...chunks: Uint8Array[]): ReadableStream<Uint8Array> {
  return new ReadableStream({ start(c) { chunks.forEach((x) => c.enqueue(x)); c.close(); } });
}

test("parses one event block", () => {
  assert.deepEqual(parseBlock('event: token\ndata: {"t":"x"}'), { event: "token", data: '{"t":"x"}' });
  assert.equal(parseBlock(": keep-alive"), null);
});

test("reassembles events and Arabic characters split across chunks", async () => {
  const bytes = new TextEncoder().encode('event: token\ndata: {"t":"المادة"}\n\nevent: done\ndata: {}\n\n');
  const cut = 22; // inside the Arabic word: a character's bytes land in two chunks
  const events = [];
  for await (const e of readSse(streamOf(bytes.slice(0, cut), bytes.slice(cut)))) events.push(e);
  assert.deepEqual(events.map((e) => e.event), ["token", "done"]);
  assert.equal(JSON.parse(events[0].data).t, "المادة");
});
