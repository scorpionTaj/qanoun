import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { ExternalLink, MessagesSquare } from "lucide-react";
import { Chip } from "@/components/ui/heroui";
import { Preamble } from "@/components/laws/preamble";
import { Amendments } from "@/components/laws/amendments";
import { api } from "@/lib/api";
import { formatNumber, lawTitle } from "@/lib/utils";
import { ReaderClient } from "@/components/laws/reader-client";
import { DomainIcon } from "@/components/common/domain-icon";

// Reader content changes with every re-ingestion.
export const dynamic = "force-dynamic";

export default async function LawReaderPage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  const t = await getTranslations("laws");

  const law = await api.law(slug).catch(() => null);
  if (!law) notFound();
  const siblings = await api.laws({ group: law.group_slug }).catch(() => []);
  const editions = siblings.length ? siblings : [law];
  const isArabic = law.language === "ar";
  const title = lawTitle(law, locale);

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <header className="flex flex-col gap-4">
        <div className="flex items-start gap-4">
          <span className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-accent/10 text-accent">
            <DomainIcon domain={law.domain} className="size-6" />
          </span>
          <div className="min-w-0">
            <h1 className="text-balance text-3xl font-bold leading-tight">{title}</h1>
            {locale !== "ar" && law.title_ar !== title && (
              <p className="mt-1 font-arabic text-muted" dir="rtl" lang="ar">
                {law.title_ar}
              </p>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {law.law_number && (
            <Chip variant="secondary">
              {t("lawNumber")} {law.law_number}
            </Chip>
          )}
          {law.year && (
            <Chip variant="soft" color="warning">
              {law.year}
            </Chip>
          )}
          <Chip variant="secondary">
            {formatNumber(law.article_count, locale)} {t("articles")}
          </Chip>

          {/* Editions: the same law in Arabic and French */}
          {editions.length > 1 && (
            <span className="flex items-center gap-1 rounded-full bg-default p-0.5" role="group" aria-label={t("otherEditions")}>
              {editions.map((edition) => (
                <Link
                  key={edition.slug}
                  href={`/${locale}/laws/${edition.slug}`}
                  hrefLang={edition.language}
                  aria-current={edition.slug === law.slug ? "page" : undefined}
                  className={
                    edition.slug === law.slug
                      ? "rounded-full bg-accent px-2.5 py-0.5 text-xs font-semibold uppercase text-accent-foreground"
                      : "rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase text-muted hover:text-foreground"
                  }
                >
                  {edition.language}
                </Link>
              ))}
            </span>
          )}

          <span className="ms-auto flex flex-wrap items-center gap-2">
            {law.source_url && (
              <a
                href={law.source_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline"
              >
                {t("source")}
                <ExternalLink className="size-3.5" aria-hidden />
              </a>
            )}
            <Link
              href={`/${locale}/chat?group=${encodeURIComponent(law.group_slug)}`}
              className="inline-flex h-9 items-center gap-1.5 rounded-full bg-accent px-4 text-sm font-medium text-accent-foreground transition-opacity hover:opacity-90"
            >
              <MessagesSquare className="size-4" aria-hidden />
              {t("askAbout")}
            </Link>
          </span>
        </div>
      </header>

      {law.preamble && <Preamble title={t("preamble")} text={law.preamble} isArabic={isArabic} />}
      {law.amendments && <Amendments data={law.amendments} />}

      <div className="mt-8">
        <ReaderClient articles={law.articles} lawTitle={title} isArabic={isArabic} amended={law.amendments?.articles} />
      </div>
    </div>
  );
}
