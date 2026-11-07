"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { applyTheme, storedTheme } from "@/lib/theme";

/** Re-applies the stored theme after every client-side navigation: Next's router cache can
 * serve payloads rendered before a theme change (e.g. switching locale right after toggling). */
export function ThemeSync() {
  const pathname = usePathname();
  useEffect(() => applyTheme(storedTheme()), [pathname]);
  return null;
}
