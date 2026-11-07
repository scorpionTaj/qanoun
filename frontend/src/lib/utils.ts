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
