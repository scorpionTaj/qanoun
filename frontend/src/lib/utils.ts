import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function lawTitle(
  law: { title_ar: string; title_fr: string | null },
  locale: string
): string {
  if (locale === "fr") return law.title_fr ?? law.title_ar;
  return law.title_ar;
}

export function formatNumber(value: number | null | undefined, locale: string): string {
  if (value == null) return "—";
  return new Intl.NumberFormat(locale === "ar" ? "ar-MA" : locale).format(value);
}

// Mirror of qanoun_pipeline.normalize.normalize for client-side matching: index and query
// must fold identically (alef/ya/ta-marbuta variants, harakat, tatweel, Arabic digits).
const LETTERS: Record<string, string> = { "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه" };

export function normalizeArabic(text: string): string {
  return text
    .normalize("NFKC")
    .replace(/[ً-ْٰـ]/g, "")
    .replace(/[أإآٱىة]/g, (c) => LETTERS[c])
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660))
    .replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x06f0))
    .toLowerCase();
}
