"use client";

import { useEffect, useState } from "react";
import { Button, Tooltip } from "@heroui/react";
import { Moon, Sun } from "lucide-react";
import { useTranslations } from "next-intl";
import { applyTheme, type Theme } from "@/lib/theme";

export function ThemeToggle() {
  const t = useTranslations("app");
  const [theme, setTheme] = useState<Theme | null>(null);

  // Read what the server (cookie) or the head script already applied.
  useEffect(() => {
    setTheme(document.documentElement.classList.contains("dark") ? "dark" : "light");
  }, []);

  const label = theme === "dark" ? t("lightMode") : t("darkMode");

  return (
    <Tooltip delay={400}>
      <Button
        isIconOnly
        size="sm"
        variant="ghost"
        aria-label={label}
        onPress={() => {
          const next: Theme = theme === "dark" ? "light" : "dark";
          setTheme(next);
          applyTheme(next, true);
        }}
      >
        {theme === "dark" ? <Sun className="size-4" aria-hidden /> : <Moon className="size-4" aria-hidden />}
      </Button>
      <Tooltip.Content>{label}</Tooltip.Content>
    </Tooltip>
  );
}
