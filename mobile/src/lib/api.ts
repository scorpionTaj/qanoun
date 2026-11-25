/** The Qanoun API (the same FastAPI the web app uses). */
import { fetch } from "expo/fetch";

import { API_URL } from "./config";
import { readSse } from "./sse";

export interface Source {
  law_slug: string;
  law_title: string;
  law_title_fr: string | null;
  language: "ar" | "fr";
  article_number: string | null;
  text: string;
}

export interface LawSummary {
  slug: string;
  title_ar: string;
  title_fr: string | null;
  law_number: string | null;
  year: number | null;
  domain: string;
  language: "ar" | "fr";
  article_count: number;
  parent_group: string | null;
}

export interface Article {
  id: number;
  number: string;
  text: string;
}

export interface LawDetail extends LawSummary {
  articles: Article[];
}

export interface Turn {
  role: "user" | "assistant";
  text: string;
}

/** What the answer stream reports, in order: stage → sources → tokens → done (or error). */
export type ChatUpdate =
  | { kind: "stage"; stage: string }
  | { kind: "meta"; rewritten: string; disclaimer: string }
  | { kind: "sources"; sources: Source[] }
  | { kind: "token"; text: string }
  | { kind: "done"; text: string; cited: number[]; abstained: boolean }
  | { kind: "error"; code: string; message: string };

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return (await response.json()) as T;
}

export const listLaws = () => getJson<LawSummary[]>("/api/laws");
export const getLaw = (slug: string) => getJson<LawDetail>(`/api/laws/${encodeURIComponent(slug)}`);

export async function* ask(
  question: string,
  history: Turn[],
  answerLanguage: "auto" | "ar" | "fr" | "en",
  signal?: AbortSignal,
): AsyncGenerator<ChatUpdate> {
  const response = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ question, history: history.slice(-6), answer_language: answerLanguage }),
    signal,
  });
  if (response.status === 429) {
    yield { kind: "error", code: "rate_limited", message: "" };
    return;
  }
  if (!response.ok || !response.body) {
    yield { kind: "error", code: "http", message: `HTTP ${response.status}` };
    return;
  }
  for await (const { event, data } of readSse(response.body)) {
    const payload = JSON.parse(data);
    if (event === "status") yield { kind: "stage", stage: payload.stage };
    else if (event === "meta") yield { kind: "meta", rewritten: payload.rewritten, disclaimer: payload.disclaimer };
    else if (event === "sources") yield { kind: "sources", sources: payload.sources };
    else if (event === "token") yield { kind: "token", text: payload.t };
    else if (event === "done") yield { kind: "done", text: payload.text, cited: payload.cited ?? [], abstained: !!payload.abstained };
    else if (event === "error") yield { kind: "error", code: payload.code, message: payload.message };
  }
}
