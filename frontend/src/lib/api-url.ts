/**
 * Where the API lives, decided at runtime so one built image fits any deployment.
 *
 * - Server rendering: QANOUN_API_URL (e.g. http://api:8000 inside docker compose), else the
 *   public URL.
 * - Browser: QANOUN_PUBLIC_API_URL, which the root layout writes into the page as
 *   `window.__QANOUN_API_URL__` before the app runs.
 *
 * Both fall back to NEXT_PUBLIC_API_URL, inlined at build time (how Vercel sets it).
 */

declare global {
  interface Window {
    __QANOUN_API_URL__?: string;
  }
}

const BUILD_TIME_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** The public API URL from the runtime environment (server only; undefined if unset). */
export function publicApiUrlFromEnv(): string | undefined {
  return process.env.QANOUN_PUBLIC_API_URL || undefined;
}

export function apiUrl(): string {
  if (typeof window === "undefined") {
    return process.env.QANOUN_API_URL || publicApiUrlFromEnv() || BUILD_TIME_URL;
  }
  return window.__QANOUN_API_URL__ || BUILD_TIME_URL;
}

/** The inline script that hands the runtime public URL to the browser. `<` is escaped so
 * the value can never close the script element. */
export function runtimeConfigScript(url: string): string {
  return `window.__QANOUN_API_URL__=${JSON.stringify(url).replace(/</g, "\\u003c")};`;
}
