/** AI provider preference. API keys live in the backend's .env file — the browser only
 * remembers WHICH configured provider and model to prefer, and sends those two ids with
 * each question. Nothing secret is ever stored here. */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const STORAGE_KEY = "qanoun-llm-choice";
const LEGACY_KEY = "qanoun-llm-settings"; // held a base URL + API key before keys moved to .env

export interface LlmChoice {
  provider: string; // "" = the server's default
  model: string; // "" = the provider's recommended model
}

export interface ProviderInfo {
  id: string;
  label: string;
  configured: boolean;
  local: boolean;
  model: string;
  key_env: string;
  key_url: string;
  base_url: string | null;
}

export interface ProvidersResponse {
  default: string;
  providers: ProviderInfo[];
}

export interface TestResult {
  ok: boolean;
  provider: string;
  model?: string;
  latency_ms?: number;
  code?: string;
  message?: string;
  failed?: { model: string; code: string; message: string }[]; // models tried before the one that worked
}

export const DEFAULT_CHOICE: LlmChoice = { provider: "", model: "" };

export function loadChoice(): LlmChoice {
  try {
    localStorage.removeItem(LEGACY_KEY); // drop any API key saved by older versions
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_CHOICE;
    const parsed = JSON.parse(raw) as Partial<LlmChoice>;
    return {
      provider: typeof parsed.provider === "string" ? parsed.provider : "",
      model: typeof parsed.model === "string" ? parsed.model : "",
    };
  } catch {
    return DEFAULT_CHOICE;
  }
}

export function saveChoice(choice: LlmChoice) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(choice));
  } catch {}
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json() as Promise<T>;
}

export const llmApi = {
  providers: () => fetch(`${API_URL}/api/llm/providers`).then((r) => json<ProvidersResponse>(r)),
  models: (provider: string) =>
    fetch(`${API_URL}/api/llm/providers/${encodeURIComponent(provider)}/models`).then((r) =>
      json<{ recommended: string | null; models: string[] }>(r)
    ),
  test: (choice: LlmChoice) =>
    fetch(`${API_URL}/api/llm/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(choice),
    }).then((r) => json<TestResult>(r)),
};
