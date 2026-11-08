import { test } from "node:test";
import assert from "node:assert/strict";
import { answerHtml } from "./export-answer.ts";
import { mergeConversations } from "./account.ts";

const labels = { title: "T", question: "Q", answer: "A", sources: "S", article: "Art.", page: "p.", exported: "E" };
const hit = (n: string) => ({
  law_slug: "x", law_title: "قانون", law_title_fr: "Loi", group_slug: "x", domain: "family", language: "fr" as const,
  article_number: n, article_id: Number(n), page: 3, text: `texte ${n}`, score: 1,
});

test("answer export escapes HTML and lists only cited sources", () => {
  const html = answerHtml({
    question: "<script>alert(1)</script>", answer: "Oui [2]", sources: [hit("1"), hit("2")], cited: [1], locale: "fr", labels,
  });
  assert.ok(!html.includes("<script>alert"));
  assert.ok(html.includes("&lt;script&gt;"));
  assert.ok(html.includes('<li value="2">') && !html.includes('<li value="1">'));
  assert.ok(html.includes('dir="ltr"'));
});

test("conversation merge keeps the newer copy and sorts newest first", () => {
  const c = (id: string, updatedAt: number, title = id) => ({ id, title, updatedAt, messages: [] });
  const merged = mergeConversations([c("a", 5, "local"), c("b", 1)], [c("a", 3, "remote"), c("z", 9)]);
  assert.deepEqual(merged.map((x) => [x.id, x.title]), [["z", "z"], ["a", "local"], ["b", "b"]]);
});
