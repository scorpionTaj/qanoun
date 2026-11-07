"use client";

import { useTranslations } from "next-intl";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { Scale, Gavel, MessagesSquare, BarChart3 } from "lucide-react";
import { locales, type Locale } from "@/i18n/routing";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { cn } from "@/lib/utils";

export function Header() {
  const t = useTranslations("app");
  const pathname = usePathname() ?? "";
  // pathname starts with /{locale}/…
  const currentLocale = (pathname.split("/")[1] ?? "ar") as Locale;
  const rest = pathname.split("/").slice(2).join("/");
  const isActive = (path: string) =>
    path === "" ? rest === "" : rest.startsWith(path);

  const nav = [
    { href: "", label: t("nav.home"), icon: Scale },
    { href: "laws", label: t("nav.laws"), icon: Gavel },
    { href: "chat", label: t("nav.chat"), icon: MessagesSquare },
    { href: "insights", label: t("nav.insights"), icon: BarChart3 },
  ];

  return (
    <header className="sticky top-0 z-40 border-b border-zellige-100 bg-white/90 backdrop-blur dark:border-zellige-800 dark:bg-[#0b1310]/90">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
        <Link href={`/${currentLocale}`} className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-zellige-700 text-lg font-bold text-white dark:bg-zellige-600">
            ق
          </span>
          <span className="flex flex-col leading-none">
            <span className="text-lg font-bold text-zellige-900 dark:text-white">{t("title")}</span>
            <span className="text-[11px] text-zellige-500 dark:text-zellige-400">{t("tagline")}</span>
          </span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {nav.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={`/${currentLocale}${href ? `/${href}` : ""}`}
              className={cn(
                "flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive(href)
                  ? "bg-zellige-100 text-zellige-900 dark:bg-zellige-800/80 dark:text-white"
                  : "text-zellige-600 hover:bg-zellige-50 hover:text-zellige-900 dark:text-zellige-300 dark:hover:bg-zellige-800/50 dark:hover:text-white"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          <div className="flex items-center gap-1 rounded-lg border border-zellige-200 p-0.5 dark:border-zellige-700">
            {locales.map((locale) => (
              <Link
                key={locale}
                href={`/${locale}${rest ? `/${rest}` : ""}`}
                prefetch={false}
                className={cn(
                  "rounded-md px-2 py-1 text-xs font-semibold uppercase transition-colors",
                  locale === currentLocale
                    ? "bg-zellige-700 text-white dark:bg-zellige-600"
                    : "text-zellige-500 hover:text-zellige-800 dark:text-zellige-400 dark:hover:text-white"
                )}
              >
                {locale}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </header>
  );
}
