import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { ArrowLeft, ArrowRight, BookOpenCheck, Database, SearchCheck } from "lucide-react";
import { Card, Chip } from "@/components/ui/heroui";
import { api } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import { HeroSearch } from "@/components/home/hero-search";
import { DomainIcon } from "@/components/common/domain-icon";
import type { Locale } from "@/i18n/routing";

// Live corpus data — must not be baked in at build time.
export const dynamic = "force-dynamic";

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const t = await getTranslations("home");
  const chat = await getTranslations("chat");
  const app = await getTranslations("app");
  const Arrow = locale === "ar" ? ArrowLeft : ArrowRight;

  const [domains, summary] = await Promise.all([
    api.domains().catch(() => []),
    api.analyticsSummary().catch(() => null),
  ]);

  const stats = summary
    ? [
        { value: summary.totals.laws, label: t("statsLaws") },
        { value: summary.totals.articles, label: t("statsArticles") },
        { value: summary.totals.domains, label: t("statsDomains") },
      ]
    : [];

  const how = [
    { icon: Database, title: t("how1Title"), body: t("how1Body") },
    { icon: SearchCheck, title: t("how2Title"), body: t("how2Body") },
    { icon: BookOpenCheck, title: t("how3Title"), body: t("how3Body") },
  ];

  return (
    <div className="flex flex-col">
      {/* Hero */}
      <section className="hero-pattern text-white">
        <div className="mx-auto flex max-w-4xl flex-col items-center px-4 pb-20 pt-16 text-center md:pb-28 md:pt-24">
          <Chip size="sm" variant="soft" className="mb-6 bg-white/12 text-white">
            {app("tagline")}
          </Chip>
          <h1 className="text-balance font-arabic text-4xl font-bold leading-tight md:text-6xl">{t("heroTitle")}</h1>
          <p className="mt-5 max-w-2xl text-pretty text-lg text-white/80">{t("heroSubtitle")}</p>
          <div className="mt-9 w-full max-w-2xl">
            <HeroSearch
              locale={locale}
              placeholder={t("askPlaceholder")}
              askLabel={t("askButton")}
              examples={(chat.raw("suggestions") as string[]).slice(0, 4)}
            />
          </div>
          {stats.length > 0 && (
            <dl className="mt-12 grid w-full max-w-xl grid-cols-3 gap-4">
              {stats.map(({ value, label }) => (
                <div key={label} className="flex flex-col items-center gap-1">
                  <dt className="order-2 text-xs text-white/70">{label}</dt>
                  <dd className="order-1 text-2xl font-bold tabular-nums md:text-3xl">{formatNumber(value, locale)}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      </section>

      {/* Domains */}
      <section className="mx-auto w-full max-w-6xl px-4 py-16">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-2xl font-bold">{t("topicsTitle")}</h2>
            <p className="mt-1 text-muted">{t("topicsSubtitle")}</p>
          </div>
          <Link href={`/${locale}/laws`} className="inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline">
            {t("browseButton")}
            <Arrow className="size-4" aria-hidden />
          </Link>
        </div>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {domains.map((d) => (
            <Link
              key={d.domain}
              href={`/${locale}/laws?domain=${d.domain}`}
              className="group rounded-[var(--radius)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            >
              <Card className="h-full flex-row items-center gap-4 p-4 transition-shadow group-hover:shadow-md">
                <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent">
                  <DomainIcon domain={d.domain} className="size-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-semibold">{d.label[locale as Locale]}</div>
                  <div className="text-sm tabular-nums text-muted">
                    {formatNumber(d.laws, locale)} · {formatNumber(d.articles, locale)} {t("statsArticles")}
                  </div>
                </div>
                <Arrow
                  className="size-4 text-muted transition-transform group-hover:translate-x-0.5 rtl:group-hover:-translate-x-0.5"
                  aria-hidden
                />
              </Card>
            </Link>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="border-y border-separator bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-16">
          <h2 className="text-2xl font-bold">{t("howTitle")}</h2>
          <ol className="mt-8 grid gap-8 md:grid-cols-3">
            {how.map(({ icon: Icon, title, body }, index) => (
              <li key={title} className="flex flex-col gap-3">
                <div className="flex items-center gap-3">
                  <span className="flex size-11 items-center justify-center rounded-xl bg-accent text-accent-foreground">
                    <Icon className="size-5" aria-hidden />
                  </span>
                  <span className="font-mono text-sm text-muted">0{index + 1}</span>
                </div>
                <h3 className="font-bold">{title}</h3>
                <p className="text-sm leading-6 text-muted">{body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>
    </div>
  );
}
