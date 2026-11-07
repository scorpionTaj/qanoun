/** Saved conversations for the Ask workspace. Single-user and per-browser by design:
 * kept in localStorage (no account needed), capped so storage stays small. Every read and
 * write tolerates a missing or blocked localStorage. */

import type { SearchHit } from "./types";

export interface Message {
  role: "user" | "assistant";
  text: string;
  sources?: SearchHit[];
  cited?: number[];
  abstained?: boolean;
  rewritten?: string;
  disclaimer?: string;
  error?: boolean;
  errorDetail?: string;
  answeredBy?: string; // "Google Gemini · gemini-2.5-flash"
  streaming?: boolean;
  stage?: "rewriting" | "searching" | "answering"; // live progress while streaming
  seconds?: number; // server-side time to answer
  stopped?: boolean; // the user pressed Stop: the text may be incomplete
}

export interface Conversation {
  id: string;
  title: string;
  updatedAt: number;
  messages: Message[];
}

const KEY = "qanoun-conversations";
const MAX_CONVERSATIONS = 40;

export function newConversation(): Conversation {
  const id =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return { id, title: "", updatedAt: Date.now(), messages: [] };
}

export function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(KEY);
    const list = raw ? (JSON.parse(raw) as Conversation[]) : [];
    return Array.isArray(list) ? list.filter((c) => c && c.id && Array.isArray(c.messages)) : [];
  } catch {
    return [];
  }
}

export function saveConversations(list: Conversation[]) {
  // Only finished turns are worth keeping; never persist a half-streamed answer.
  const clean = list
    .filter((c) => c.messages.length > 0)
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .slice(0, MAX_CONVERSATIONS)
    .map((c) => ({ ...c, messages: c.messages.filter((m) => !m.streaming) }));
  try {
    localStorage.setItem(KEY, JSON.stringify(clean));
  } catch {
    // quota exceeded or storage blocked: the workspace keeps working in memory
  }
}

export function titleFor(messages: Message[]): string {
  const first = messages.find((m) => m.role === "user")?.text ?? "";
  return first.length > 60 ? `${first.slice(0, 57)}…` : first;
}
