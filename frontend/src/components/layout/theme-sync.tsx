"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { THEME_COOKIE } from "@/components/layout/theme-toggle";

/**
 * Re-applies the stored theme after every client-side navigation.
 *
 * Why: Next's client router cache serves pre-rendered RSC payloads that can predate a
 * theme change — switching locale right after toggling would otherwise flash the old
 * theme until the next full reload (the cookie itself is correct, as a refresh proves).
 * Watching the pathname re-syncs the html class from the cookie on every route change.
 */
export function ThemeSync() {
  const pathname = usePathname();

  useEffect(() => {
    const cookie = document.cookie
      .split("; ")
      .find((row) => row.startsWith(`${THEME_COOKIE}=`))
      ?.split("=")[1] as "light" | "dark" | undefined;
    let theme: "light" | "dark";
    if (cookie) {
      theme = cookie;
    } else {
      try {
        theme = (localStorage.getItem(THEME_COOKIE) as "light" | "dark") ??
          (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      } catch {
        return;
      }
    }
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [pathname]);

  return null;
}
