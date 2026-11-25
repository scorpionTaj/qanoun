/** Saved conversations: on the device (the 40 most recent), synced with the account when
 * signed in. Same shape as the web app's, so a conversation started on one shows on the other. */
import type { Source, StoredConversation } from "./api";
import { readJson, writeJson } from "./storage";

export interface Message {
  role: "user" | "assistant";
  text: string;
  sources?: Source[];
  cited?: number[]; // 0-based indexes into sources: «[2]» in the text is 1
  disclaimer?: string;
  answeredBy?: string;
  error?: boolean;
  streaming?: boolean;
  stage?: string;
}

export interface Conversation extends StoredConversation {
  messages: Message[];
}

const KEY = "qanoun.conversations";
const MAX = 40;

export const loadConversations = (): Conversation[] => readJson<Conversation[]>(KEY, []);

export function saveConversations(list: Conversation[]): void {
  writeJson(KEY, [...list].sort((a, b) => b.updatedAt - a.updatedAt).slice(0, MAX));
}

export function newConversation(): Conversation {
  return { id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`, title: "", updatedAt: Date.now(), messages: [] };
}

export function titleFor(messages: Message[]): string {
  const first = messages.find((m) => m.role === "user")?.text ?? "";
  return first.length > 80 ? `${first.slice(0, 79)}…` : first;
}

/** What is kept: finished messages only (a stream cut short is not saved half-way). */
export const storable = (c: Conversation): Conversation => ({
  ...c,
  messages: c.messages.filter((m) => !m.streaming).map(({ stage: _stage, streaming: _streaming, ...m }) => m),
});

/** Union by id; the newer copy wins (the web app's rule, and the server's). */
export function mergeConversations(local: Conversation[], remote: Conversation[]): Conversation[] {
  const byId = new Map<string, Conversation>();
  for (const c of [...remote, ...local]) {
    const current = byId.get(c.id);
    if (!current || c.updatedAt > current.updatedAt) byId.set(c.id, c);
  }
  return [...byId.values()].sort((a, b) => b.updatedAt - a.updatedAt);
}
