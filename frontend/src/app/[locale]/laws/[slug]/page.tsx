import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { ExternalLink, MessageSquareText } from "lucide-react";
import { api } from "@/lib/api";
import { formatNumber, lawTitle } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ReaderClient } from "@/components/laws/reader-client";

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
  const otherEditions = siblings.filter((s) => s.slug !== law.slug);

  const isArabic = law.language === "ar";

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      {/* Header */}
      <header className="border-b border-zellige-100 pb-6 dark:border-zellige-800">
        <h1 className="text-3xl font-bold text-zellige-900 dark:text-white">{lawTitle(law, locale)}</h1>
        {locale !== "ar" && law.title_fr && law.title_fr !== lawTitle(law, locale) && (
          <p className="mt-1 text-zellige-500 dark:text-zellige-400" dir="rtl">
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
              className="inline-flex items-center gap-1 text-xs font-medium text-zellige-600 underline-offset-2 hover:underline dark:text-zellige-300"
            >
              {t("source")}
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
          <Link
            href={`/${locale}/chat?q=${encodeURIComponent(lawTitle(law, locale))}`}
            className="inline-flex items-center gap-1.5 rounded-full bg-zellige-700 px-3 py-1 text-xs font-medium text-white hover:bg-zellige-800 dark:bg-zellige-600 dark:hover:bg-zellige-500"
          >
            <MessageSquareText className="h-3 w-3" />
            {t("askAbout")}
          </Link>
        </div>
      </header>

      {/* Preamble */}
      {law.preamble && (
        <Card className="mt-6 border-sand-200 bg-sand-50 dark:border-sand-900 dark:bg-[#161a12]">
          <CardHeader>
            <CardTitle className="text-sand-800 dark:text-sand-300">{t("preamble")}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="line-clamp-6 leading-8 text-sand-900/80 dark:text-sand-200/80" dir={isArabic ? "rtl" : "ltr"}>
              {law.preamble}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Articles (client tools: search, font size, copy citation, share) */}
      <div className="mt-8">
        <ReaderClient
          articles={law.articles}
          lawTitle={lawTitle(law, locale)}
          locale={locale}
          isArabic={isArabic}
        />
      </div>

      {/* Other editions of the same law (bilingual pairs) */}
      {otherEditions.length > 0 && (
        <div className="mt-8 rounded-xl border border-zellige-100 bg-white p-5 dark:border-zellige-800 dark:bg-[#12201a]">
          <h2 className="text-sm font-bold text-zellige-700 dark:text-zellige-300">{t("otherEditions")}</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {otherEditions.map((sibling) => (
              <Link
                key={sibling.slug}
                href={`/${locale}/laws/${sibling.slug}`}
                className="inline-flex items-center gap-2 rounded-full border border-zellige-200 px-3 py-1.5 text-sm text-zellige-700 hover:bg-zellige-50 dark:border-zellige-700 dark:text-zellige-200 dark:hover:bg-zellige-800/60"
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
