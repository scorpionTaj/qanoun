import { defineRouting } from "next-intl/routing";

export const locales = ["ar", "fr", "en"] as const;
export type Locale = (typeof locales)[number];

export const routing = defineRouting({
  locales,
  defaultLocale: "ar",
  // Arabic is RTL; keep the locale always visible in the URL for shareable links.
  localePrefix: "always",
});
