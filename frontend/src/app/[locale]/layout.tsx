import type { Metadata } from "next";
import { cookies } from "next/headers";
import { Inter, Noto_Naskh_Arabic } from "next/font/google";
import { notFound } from "next/navigation";
import Script from "next/script";
import { NextIntlClientProvider, hasLocale } from "next-intl";
import { getTranslations } from "next-intl/server";
import { routing } from "@/i18n/routing";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { FooterGate } from "@/components/layout/footer-gate";
import { themeInitScript } from "@/lib/theme";
import { ThemeSync } from "@/components/layout/theme-sync";
import "../globals.css";

const naskh = Noto_Naskh_Arabic({
  subsets: ["arabic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-naskh",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

// Only the configured locales exist: anything else in the first segment (e.g. a stray
// /favicon.ico request, which the proxy skips because it has a dot) is a 404 instead of
// rendering pages with locale "favicon.ico" (Intl.NumberFormat threw RangeError on that).
export const dynamicParams = false;

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "app" });
  return {
    title: `${t("title")} — ${t("tagline")}`,
    description: t("description"),
  };
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();

  // The theme is a cookie so the SERVER renders the class: switching locale (which
  // reloads the document) and hard navigations keep the chosen theme, with no flash.
  const theme = (await cookies()).get("qanoun-theme")?.value === "dark" ? "dark" : "";
  const t = await getTranslations({ locale, namespace: "app" });

  return (
    <html
      lang={locale}
      dir={locale === "ar" ? "rtl" : "ltr"}
      className={theme}
      data-theme={theme || "light"}
      suppressHydrationWarning
    >
      <head>
        {/* Runs before hydration (no theme flash). next/script, not a raw <script>: React 19
            warns that script tags rendered by components never run on the client. */}
        <Script id="theme-init" strategy="beforeInteractive">
          {themeInitScript}
        </Script>
      </head>
      <body
        className={`${naskh.variable} ${inter.variable} min-h-screen`}
      >
        <NextIntlClientProvider>
          <ThemeSync />
          <a
            href="#main"
            className="sr-only focus:not-sr-only focus:fixed focus:start-3 focus:top-3 focus:z-[60] focus:rounded-lg focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-foreground"
          >
            {t("skipToContent")}
          </a>
          <div className="flex min-h-screen flex-col">
            <Header />
            {/* bottom padding clears the phone tab bar */}
            <main id="main" className="flex-1 pb-16 md:pb-0">
              {children}
            </main>
            <FooterGate>
              <Footer />
            </FooterGate>
          </div>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
