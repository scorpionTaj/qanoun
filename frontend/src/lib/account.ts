/** Optional account: session cookie set by the API (httpOnly — never readable here). */

import type { Conversation } from "./conversations";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Me {
  user: { id: number; email: string; is_admin: boolean } | null;
  signup_allowed: boolean;
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    credentials: "include",
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw Object.assign(new Error(body.detail ?? `HTTP ${response.status}`), { status: response.status });
  }
  return response.json() as Promise<T>;
}

export const accountApi = {
  me: () => call<Me>("/api/auth/me"),
  signup: (email: string, password: string) =>
    call("/api/auth/signup", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    call("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  logout: () => call("/api/auth/logout", { method: "POST", body: "{}" }),
  conversations: () => call<Conversation[]>("/api/conversations"),
  put: (c: Conversation) =>
    call(`/api/conversations/${encodeURIComponent(c.id)}`, {
      method: "PUT",
      body: JSON.stringify({ title: c.title, updated_at: c.updatedAt, messages: c.messages.filter((m) => !m.streaming) }),
    }),
  remove: (id: string) => call(`/api/conversations/${encodeURIComponent(id)}`, { method: "DELETE" }),
  removeAll: () => call("/api/conversations", { method: "DELETE" }),
};

/** Union of local and server conversations by id; the newer copy wins. */
export function mergeConversations(local: Conversation[], remote: Conversation[]): Conversation[] {
  const byId = new Map<string, Conversation>();
  for (const c of [...remote, ...local]) {
    const current = byId.get(c.id);
    if (!current || c.updatedAt > current.updatedAt) byId.set(c.id, c);
  }
  return [...byId.values()].sort((a, b) => b.updatedAt - a.updatedAt);
}
