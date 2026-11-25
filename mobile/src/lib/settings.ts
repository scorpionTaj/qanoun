/** Preferences: on the device always, and on the account when signed in (same fields as
 * PUT /api/auth/settings, so they follow the user to another phone). */
import { getLocales } from "expo-localization";
import * as SecureStore from "expo-secure-store";

import { readJson, writeJson } from "./storage";

export type Lang = "ar" | "fr" | "en";

export interface Settings {
  provider: string; // "" = the server's default provider
  model: string; // "" = the provider's recommended model
  style: "concise" | "detailed";
  answer_language: "auto" | Lang;
  ui_language: Lang;
  theme: "system" | "light" | "dark";
}

const KEY = "qanoun.settings";

function deviceLanguage(): Lang {
  const earlier = SecureStore.getItem("qanoun.language"); // where version 0.1.0 kept the choice
  if (earlier === "ar" || earlier === "fr" || earlier === "en") return earlier;
  const code = getLocales()[0]?.languageCode;
  return code === "fr" || code === "en" ? code : "ar"; // Arabic for any other language, like the web
}

export const DEFAULTS: Settings = {
  provider: "", model: "", style: "concise", answer_language: "auto", ui_language: deviceLanguage(), theme: "system",
};

export const loadSettings = (): Settings => ({ ...DEFAULTS, ...readJson<Partial<Settings>>(KEY, {}) });
export const saveSettings = (settings: Settings): void => writeJson(KEY, settings);
