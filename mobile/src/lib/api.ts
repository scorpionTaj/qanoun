/** The Qanoun API (the same FastAPI the web app uses). Signed-in calls carry the session
 * token in X-Qanoun-Session (session.ts). */
import { fetch } from "expo/fetch";

import { API_URL } from "./config";
import { getSession } from "./session";
import type { Settings } from "./settings";
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

export interface Provider {
  id: string;
  label: string;
  configured: boolean;
  local: boolean;
}

export interface User {
  id: number;
  email: string;
  is_admin: boolean;
}

export interface StoredConversation {
  id: string;
  title: string;
  updatedAt: number;
  messages: object[];
}

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

async function call<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const session = getSession();
  const response = await fetch(`${API_URL}${path}`, {
    method: init.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      ...(session ? { "X-Qanoun-Session": session } : {}),
    },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new ApiError(response.status, (detail as { detail?: string }).detail ?? `HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export const listLaws = () => call<LawSummary[]>("/api/laws");
export const getLaw = (slug: string) => call<LawDetail>(`/api/laws/${encodeURIComponent(slug)}`);

export const providers = () => call<{ default: string; providers: Provider[] }>("/api/llm/providers");
export const models = (provider: string) =>
  call<{ recommended: string | null; models: string[] }>(`/api/llm/providers/${encodeURIComponent(provider)}/models`);

export const accountApi = {
  me: () => call<{ user: User | null; signup_allowed: boolean }>("/api/auth/me"),
  signIn: (mode: "login" | "signup", email: string, password: string) =>
    call<{ ok: boolean; token: string }>(`/api/auth/${mode}`, { method: "POST", body: { email, password, client: "app" } }),
  signOut: () => call("/api/auth/logout", { method: "POST", body: {} }),
  settings: () => call<Partial<Settings>>("/api/auth/settings"),
  saveSettings: (settings: Settings) => call("/api/auth/settings", { method: "PUT", body: settings }),
  conversations: () => call<StoredConversation[]>("/api/conversations"),
  saveConversation: (c: StoredConversation) =>
    call(`/api/conversations/${encodeURIComponent(c.id)}`, {
      method: "PUT", body: { title: c.title, updated_at: c.updatedAt, messages: c.messages },
    }),
  deleteConversation: (id: string) => call(`/api/conversations/${encodeURIComponent(id)}`, { method: "DELETE" }),
};

/** What the answer stream reports, in order: stage → sources → model → tokens → done (or error). */
export type ChatUpdate =
  | { kind: "stage"; stage: string }
  | { kind: "meta"; rewritten: string; disclaimer: string }
  | { kind: "sources"; sources: Source[] }
  | { kind: "model"; label: string }
  | { kind: "token"; text: string }
  | { kind: "done"; text: string; cited: number[]; abstained: boolean }
  | { kind: "error"; code: string; message: string };

export async function* ask(
  question: string,
  history: Turn[],
  settings: Settings,
  signal?: AbortSignal,
): AsyncGenerator<ChatUpdate> {
  const response = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      question,
      history: history.slice(-6),
      provider: settings.provider || null,
      model: settings.model,
      style: settings.style,
      answer_language: settings.answer_language,
    }),
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
    else if (event === "model") yield { kind: "model", label: `${payload.provider_label} · ${payload.model}` };
    else if (event === "token") yield { kind: "token", text: payload.t };
    else if (event === "done") yield { kind: "done", text: payload.text, cited: payload.cited ?? [], abstained: !!payload.abstained };
    else if (event === "error") yield { kind: "error", code: payload.code, message: payload.message };
  }
}
