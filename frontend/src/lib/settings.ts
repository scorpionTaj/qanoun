/** Client-side LLM provider settings: stored in localStorage, sent per request to the
 * backend (which never persists them). Works with any OpenAI-compatible endpoint. */

export interface LlmSettings {
  enabled: boolean;
  baseUrl: string;
  model: string;
  apiKey: string;
}

export interface ProviderPreset {
  id: string;
  label: { ar: string; fr: string; en: string };
  baseUrl: string;
  needsKey: boolean;
  keyUrl?: string;
  models: string[]; // free-tier-friendly suggestions, first = default
  hint: { ar: string; fr: string; en: string };
}

export const PRESETS: ProviderPreset[] = [
  {
    id: "lmstudio",
    label: { ar: "LM Studio (محلي)", fr: "LM Studio (local)", en: "LM Studio (local)" },
    baseUrl: "http://localhost:1234/v1",
    needsKey: false,
    models: [],
    hint: {
      ar: "قم بتحميل نموذج محادثة في LM Studio ثم اتركه يعمل.",
      fr: "Chargez un modèle de chat dans LM Studio et laissez le serveur tourner.",
      en: "Load a chat model in LM Studio and keep the server running.",
    },
  },
  {
    id: "openrouter",
    label: { ar: "OpenRouter", fr: "OpenRouter", en: "OpenRouter" },
    baseUrl: "https://openrouter.ai/api/v1",
    needsKey: true,
    keyUrl: "https://openrouter.ai/keys",
    models: [
      "meta-llama/llama-3.3-70b-instruct:free",
      "google/gemini-2.0-flash-exp:free",
      "qwen/qwen-2.5-72b-instruct:free",
      "mistralai/mistral-small-3.1-24b-instruct:free",
    ],
    hint: {
      ar: "مجاني للنماذج التي تنتهي بـ :free — أنشئ مفتاحاً من openrouter.ai/keys",
      fr: "Gratuit pour les modèles suffixés :free — créez une clé sur openrouter.ai/keys",
      en: "Free for models ending in :free — create a key at openrouter.ai/keys",
    },
  },
  {
    id: "gemini",
    label: { ar: "Google Gemini", fr: "Google Gemini", en: "Google Gemini" },
    baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
    needsKey: true,
    keyUrl: "https://aistudio.google.com/apikey",
    models: ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash"],
    hint: {
      ar: "طبقة مجانية سخية — أنشئ مفتاح API مجاني من Google AI Studio",
      fr: "Palier gratuit généreux — créez une clé API gratuite dans Google AI Studio",
      en: "Generous free tier — create a free API key in Google AI Studio",
    },
  },
  {
    id: "nvidia",
    label: { ar: "NVIDIA NIM", fr: "NVIDIA NIM", en: "NVIDIA NIM" },
    baseUrl: "https://integrate.api.nvidia.com/v1",
    needsKey: true,
    keyUrl: "https://build.nvidia.com/",
    models: [
      "meta/llama-3.3-70b-instruct",
      "mistralai/mistral-nemotron",
      "qwen/qwen2.5-coder-32b-instruct",
    ],
    hint: {
      ar: "رصيد مجاني عند التسجيل في build.nvidia.com",
      fr: "Crédit gratuit à l'inscription sur build.nvidia.com",
      en: "Free credits when you sign up at build.nvidia.com",
    },
  },
];

const STORAGE_KEY = "qanoun-llm-settings";

export const DEFAULT_SETTINGS: LlmSettings = {
  enabled: false,
  baseUrl: "http://localhost:1234/v1",
  model: "",
  apiKey: "",
};

export function loadSettings(): LlmSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    return { ...DEFAULT_SETTINGS, ...(JSON.parse(raw) as Partial<LlmSettings>) };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function saveSettings(settings: LlmSettings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export function settingsForRequest(settings: LlmSettings): LlmSettings | undefined {
  if (!settings.enabled || !settings.baseUrl) return undefined;
  return settings;
}
