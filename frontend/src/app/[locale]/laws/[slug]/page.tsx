import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { ExternalLink, MessageSquareText } from "lucide-react";
import { api } from "@/lib/api";
import { formatNumber, lawTitle } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Locale } from "@/i18n/routing";

// Reader content changes with every re-ingestion.
export const dynamic = "force-dynamic";

export default async function LawReaderPage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;  const t = await getTranslations("laws");

  const law = await api.law(slug).catch(() => null);
  if (!law) notFound();
  const siblings = await api.laws({ group: law.group_slug }).catch(() => []);
  const otherEditions = siblings.filter((s) => s.slug !== law.slug);

  const isArabic = law.language === "ar";
  const articleLabel = (number: string) =>
    locale === "fr" || (locale === "en" && !isArabic)
      ? `Article ${number}`
      : `المادة ${number}`;

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      {/* Header */}
      <header className="border-b border-zellige-100 pb-6">
        <h1 className="text-3xl font-bold text-zellige-900">{lawTitle(law, locale)}</h1>
        {locale !== "ar" && law.title_fr && law.title_fr !== lawTitle(law, locale) && (
          <p className="mt-1 text-zellige-500" dir="rtl">
            {law.title_ar}
          </p>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {law.law_number && (
            <Badge variant="outline">
              {t("lawNumber")} {law.law_number}
            </Badge>
          )}
          {law.year && <Badge variant="sand">{law.year}</Badge>}
          <Badge>
            {formatNumber(law.article_count, locale)} {t("articles")}
          </Badge>
          {law.source_url && (
            <a
              href={law.source_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs font-medium text-zellige-600 underline-offset-2 hover:underline"
            >
              {t("source")}
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
          <Link
            href={`/${locale}/chat?q=${encodeURIComponent(lawTitle(law, locale))}`}
            className="inline-flex items-center gap-1.5 rounded-full bg-zellige-700 px-3 py-1 text-xs font-medium text-white hover:bg-zellige-800"
          >
            <MessageSquareText className="h-3 w-3" />
            {t("askAbout")}
          </Link>
        </div>
      </header>

      {/* Preamble */}
      {law.preamble && (
        <Card className="mt-6 border-sand-200 bg-sand-50">
          <CardHeader>
            <CardTitle className="text-sand-800">{t("preamble")}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="line-clamp-6 leading-8 text-sand-900/80" dir={isArabic ? "rtl" : "ltr"}>
              {law.preamble}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Articles */}
      <div className="mt-8 flex flex-col gap-3">
        {law.articles.map((article) => (
          <article
            key={article.id}
            id={`article-${encodeURIComponent(article.number)}`}
            className="scroll-mt-24 rounded-xl border border-zellige-100 bg-white p-5 shadow-sm transition-shadow hover:shadow"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="inline-flex items-center rounded-lg bg-zellige-700 px-2.5 py-1 text-sm font-bold text-white">
                {articleLabel(article.number)}
              </span>
              <span className="text-xs text-zellige-400">
                {locale === "ar" ? "ص" : "p."}
                {article.page_start}
                {article.page_end !== article.page_start ? `–${article.page_end}` : ""}
              </span>
            </div>
            <p className="mt-3 leading-8 text-zellige-900" dir={isArabic ? "rtl" : "ltr"}>
              {article.text}
            </p>
          </article>
        ))}
      </div>

      {/* Other editions of the same law (bilingual pairs) */}
      {otherEditions.length > 0 && (
        <div className="mt-8 rounded-xl border border-zellige-100 bg-white p-5">
          <h2 className="text-sm font-bold text-zellige-700">{t("otherEditions")}</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {otherEditions.map((sibling) => (
              <Link
                key={sibling.slug}
                href={`/${locale}/laws/${sibling.slug}`}
                className="inline-flex items-center gap-2 rounded-full border border-zellige-200 px-3 py-1.5 text-sm text-zellige-700 hover:bg-zellige-50"
              >
                {lawTitle(sibling, locale)}
                <Badge variant={sibling.language === "ar" ? "default" : "secondary"}>
                  {sibling.language.toUpperCase()}
                </Badge>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
