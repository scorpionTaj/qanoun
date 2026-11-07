import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Database, SearchCheck, ScrollText, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { HeroSearch } from "@/components/home/hero-search";
import type { Locale } from "@/i18n/routing";

// Live corpus data — must not be baked in at build time.
export const dynamic = "force-dynamic";

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;  const t = await getTranslations("home");
  const isRtl = locale === "ar";
  const Arrow = isRtl ? ArrowLeft : ArrowRight;

  const [domains, summary] = await Promise.all([
    api.domains().catch(() => []),
    api.analyticsSummary().catch(() => null),
  ]);

  const stats = summary
    ? [
        { value: summary.totals.laws, label: t("statsLaws") },
        { value: summary.totals.articles, label: t("statsArticles") },
        { value: summary.totals.chunks, label: t("statsChunks") },
        { value: summary.totals.domains, label: t("statsDomains") },
      ]
    : [];

  const how = [
    { icon: Database, title: t("how1Title"), body: t("how1Body") },
    { icon: SearchCheck, title: t("how2Title"), body: t("how2Body") },
    { icon: ScrollText, title: t("how3Title"), body: t("how3Body") },
  ];

  return (
    <div className="flex flex-col">
      {/* Hero — the gradient comes from .zellige-pattern (see globals.css) */}
      <section className="zellige-pattern text-white">
        <div className="mx-auto max-w-6xl px-4 py-20 text-center md:py-28">
          <Badge variant="sand" className="mx-auto mb-6 bg-white/10 text-sand-200 backdrop-blur">
            <Sparkles className="h-3.5 w-3.5" />
            {await getTranslations({ locale, namespace: "app" }).then((n) => n("tagline"))}
          </Badge>
          <h1 className="mx-auto max-w-3xl text-4xl font-bold leading-tight md:text-5xl">
            {t("heroTitle")}
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-zellige-100/90">{t("heroSubtitle")}</p>

          <div className="mx-auto mt-8 max-w-2xl">
            <HeroSearch locale={locale} placeholder={t("askPlaceholder")} askLabel={t("askButton")} />
          </div>

          <div className="mt-6 flex flex-wrap items-center justify-center gap-4 text-sm">
            <Link
              href={`/${locale}/laws`}
              className="inline-flex items-center gap-1.5 rounded-xl bg-white/10 px-4 py-2 font-medium text-white backdrop-blur transition-colors hover:bg-white/20"
            >
              {t("browseButton")}
              <Arrow className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* Stats strip */}
      {stats.length > 0 && (
        <section className="border-b border-zellige-100 bg-white dark:border-zellige-800 dark:bg-[#0e1915]">
          <div className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-4 py-8 md:grid-cols-4">
            {stats.map(({ value, label }) => (
              <div key={label} className="text-center">
                <div className="text-3xl font-bold text-zellige-800 dark:text-zellige-100">
                  {formatNumber(value, locale)}
                </div>
                <div className="mt-1 text-sm text-zellige-500 dark:text-zellige-400">{label}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Topic grid */}
      <section className="mx-auto w-full max-w-6xl px-4 py-14">
        <h2 className="text-2xl font-bold text-zellige-900 dark:text-white">{t("topicsTitle")}</h2>
        <p className="mt-1 text-zellige-500 dark:text-zellige-400">{t("topicsSubtitle")}</p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {domains.map((d) => (
            <Link key={d.domain} href={`/${locale}/laws?domain=${d.domain}`} className="group">
              <Card className="h-full transition-all group-hover:-translate-y-0.5 group-hover:shadow-md">
                <CardContent className="flex items-start justify-between gap-3 p-5">
                  <div>
                    <div className="font-semibold text-zellige-900 dark:text-white">{d.label[locale as Locale]}</div>
                    <div className="mt-1 text-sm text-zellige-500 dark:text-zellige-400">
                      {formatNumber(d.laws, locale)} · {formatNumber(d.articles, locale)}{" "}
                      {t("statsArticles")}
                    </div>
                  </div>
                  <Arrow className="h-4 w-4 text-zellige-300 dark:text-zellige-600 transition-transform group-hover:translate-x-0.5 rtl:group-hover:-translate-x-0.5" />
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="border-t border-zellige-100 bg-white dark:border-zellige-800 dark:bg-[#0e1915]">
        <div className="mx-auto max-w-6xl px-4 py-14">
          <h2 className="text-2xl font-bold text-zellige-900 dark:text-white">{t("howTitle")}</h2>
          <div className="mt-8 grid gap-8 md:grid-cols-3">
            {how.map(({ icon: Icon, title, body }) => (
              <div key={title} className="flex flex-col gap-3">
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-zellige-100 text-zellige-700 dark:bg-zellige-800/80 dark:text-zellige-200">
                  <Icon className="h-5 w-5" />
                </span>
                <h3 className="font-bold text-zellige-900 dark:text-white">{title}</h3>
                <p className="text-sm leading-6 text-zellige-600 dark:text-zellige-300">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
