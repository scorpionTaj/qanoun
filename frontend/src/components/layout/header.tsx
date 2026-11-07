"use client";

import { useTranslations } from "next-intl";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { BarChart3, BookOpen, House, MessagesSquare } from "lucide-react";
import { locales, type Locale } from "@/i18n/routing";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { SettingsDialog } from "@/components/settings/settings-dialog";
import { cn } from "@/lib/utils";

export function Header() {
  const t = useTranslations("app");
  const pathname = usePathname() ?? "";
  const currentLocale = (pathname.split("/")[1] ?? "ar") as Locale;
  const rest = pathname.split("/").slice(2).join("/");
  const isActive = (path: string) => (path === "" ? rest === "" : rest.startsWith(path));

  const nav = [
    { href: "", label: t("nav.home"), icon: House },
    { href: "chat", label: t("nav.chat"), icon: MessagesSquare },
    { href: "laws", label: t("nav.laws"), icon: BookOpen },
    { href: "insights", label: t("nav.insights"), icon: BarChart3 },
  ];
  const hrefFor = (href: string) => `/${currentLocale}${href ? `/${href}` : ""}`;

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-separator bg-background/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4">
          <Link href={`/${currentLocale}`} className="flex items-center gap-2.5 rounded-lg" aria-label={t("title")}>
            <span className="flex size-9 items-center justify-center rounded-xl bg-accent font-arabic text-lg font-bold text-accent-foreground">
              ق
            </span>
            <span className="flex flex-col leading-none">
              <span className="font-arabic text-lg font-bold">{t("title")}</span>
              <span className="hidden text-[11px] text-muted sm:block">{t("tagline")}</span>
            </span>
          </Link>

          <nav aria-label={t("nav.label")} className="hidden items-center gap-1 rounded-full bg-default p-1 md:flex">
            {nav.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={hrefFor(href)}
                aria-current={isActive(href) ? "page" : undefined}
                className={cn(
                  "flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors",
                  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                  isActive(href)
                    ? "bg-surface text-foreground shadow-sm"
                    : "text-muted hover:text-foreground"
                )}
              >
                <Icon className="size-4" aria-hidden />
                {label}
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-1">
            <ThemeToggle />
            <SettingsDialog />
            <div className="ms-1 flex items-center rounded-full bg-default p-0.5" role="group" aria-label={t("language")}>
              {locales.map((locale) => (
                <Link
                  key={locale}
                  href={`/${locale}${rest ? `/${rest}` : ""}`}
                  prefetch={false}
                  hrefLang={locale}
                  aria-current={locale === currentLocale ? "true" : undefined}
                  className={cn(
                    "rounded-full px-2.5 py-1 text-xs font-semibold uppercase transition-colors",
                    locale === currentLocale ? "bg-accent text-accent-foreground" : "text-muted hover:text-foreground"
                  )}
                >
                  {locale}
                </Link>
              ))}
            </div>
          </div>
        </div>
      </header>

      {/* Phones: sections in a bottom tab bar. A SIBLING of <header>, not a child: the
          header's backdrop-blur would become the containing block for position:fixed. */}
      <nav
        aria-label={t("nav.label")}
        className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-separator bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden"
      >
        {nav.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={hrefFor(href)}
            aria-current={isActive(href) ? "page" : undefined}
            className={cn(
              "flex h-16 flex-col items-center justify-center gap-1 text-[11px] font-medium transition-colors",
              isActive(href) ? "text-accent" : "text-muted"
            )}
          >
            <span
              className={cn(
                "flex h-7 w-12 items-center justify-center rounded-full transition-colors",
                isActive(href) && "bg-accent/12"
              )}
            >
              <Icon className="size-[18px]" aria-hidden />
            </span>
            {label}
          </Link>
        ))}
      </nav>
    </>
  );
}
