/** Answer preferences (Settings page), kept in this browser and sent with each question. */

export interface Preferences {
  style: "concise" | "detailed";
  answerLanguage: "auto" | "ar" | "fr" | "en"; // auto = the question's own language/dialect
  sources: 3 | 5 | 8; // articles retrieved per answer
}

const KEY = "qanoun-preferences";
export const DEFAULT_PREFERENCES: Preferences = { style: "concise", answerLanguage: "auto", sources: 5 };

export function loadPreferences(): Preferences {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) ?? "{}") as Partial<Preferences>;
    return {
      style: saved.style === "detailed" ? "detailed" : "concise",
      answerLanguage: ["ar", "fr", "en"].includes(saved.answerLanguage as string)
        ? (saved.answerLanguage as Preferences["answerLanguage"])
        : "auto",
      sources: saved.sources === 3 || saved.sources === 8 ? saved.sources : 5,
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function savePreferences(preferences: Preferences) {
  try {
    localStorage.setItem(KEY, JSON.stringify(preferences));
  } catch {}
}
