"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";

type Theme = "light" | "dark";

export const THEME_COOKIE = "qanoun-theme";

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
  // Cookie so the SERVER renders the right class on every navigation (soft or hard):
  // localStorage alone does not survive locale switches, which reload the document.
  document.cookie = `${THEME_COOKIE}=${theme}; path=/; max-age=31536000; samesite=lax`;
  try {
    localStorage.setItem(THEME_COOKIE, theme);
  } catch {}
}

export function ThemeToggle({ className }: { className?: string }) {
  const [theme, setTheme] = useState<Theme | null>(null);

  // Read the class the server (cookie) or head script already applied.
  useEffect(() => {
    setTheme(document.documentElement.classList.contains("dark") ? "dark" : "light");
  }, []);

  const toggle = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    applyTheme(next);
  };

  return (
    <button
      onClick={toggle}
      aria-label="toggle theme"
      title={theme === "dark" ? "Light mode" : "Dark mode"}
      className={cn(
        "flex h-9 w-9 items-center justify-center rounded-lg border border-zellige-200 text-zellige-600 transition-colors hover:bg-zellige-50",
        "dark:border-zellige-700 dark:text-sand-200 dark:hover:bg-zellige-800",
        className
      )}
    >
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}

/** Inline head script: for first visits (no cookie yet) follow the OS preference. */
export const themeInitScript = `
(function () {
  try {
    if (/(?:^|; )qanoun-theme=(light|dark)/.test(document.cookie)) return;
    if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      document.documentElement.classList.add("dark");
    }
  } catch (e) {}
})();
`;
