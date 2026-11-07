/** Light/dark theme: a cookie (so the SERVER renders the right theme on every navigation,
 * including locale switches that reload the document), mirrored to the html element as
 * the `dark` class (Tailwind) and `data-theme` (HeroUI tokens). */

export type Theme = "light" | "dark";
export const THEME_COOKIE = "qanoun-theme";

export function applyTheme(theme: Theme, persist = false) {
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  root.dataset.theme = theme;
  if (!persist) return;
  document.cookie = `${THEME_COOKIE}=${theme}; path=/; max-age=31536000; samesite=lax`;
  try {
    localStorage.setItem(THEME_COOKIE, theme);
  } catch {}
}

export function storedTheme(): Theme {
  const cookie = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${THEME_COOKIE}=`))
    ?.split("=")[1];
  if (cookie === "light" || cookie === "dark") return cookie;
  try {
    const saved = localStorage.getItem(THEME_COOKIE);
    if (saved === "light" || saved === "dark") return saved;
  } catch {}
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Inline head script: first visits (no cookie yet) follow the OS preference, no flash. */
export const themeInitScript = `
(function () {
  try {
    if (/(?:^|; )qanoun-theme=(light|dark)/.test(document.cookie)) return;
    if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      var r = document.documentElement; r.classList.add("dark"); r.dataset.theme = "dark";
    }
  } catch (e) {}
})();
`;
