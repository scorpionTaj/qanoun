import type { Metadata } from "next";
import { cookies } from "next/headers";
import { Inter, Noto_Naskh_Arabic } from "next/font/google";
import { notFound } from "next/navigation";
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
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
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
