import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { FileText } from "lucide-react";
import { api } from "@/lib/api";
import { formatNumber, lawTitle } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SearchBar } from "@/components/laws/search-bar";
import { SearchResults } from "@/components/laws/search-results";
import type { Locale } from "@/i18n/routing";

// Live corpus data — must not be baked in at build time.
export const dynamic = "force-dynamic";

export default async function LawsPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ domain?: string; q?: string }>;
}) {
  const { locale } = await params;
  const { domain, q } = await searchParams;  const t = await getTranslations("laws");
  const query = q?.trim();

  const [domains, laws, searchResponse] = await Promise.all([
    api.domains().catch(() => []),
    query ? Promise.resolve([]) : api.laws({ domain }).catch(() => []),
    query
      ? api.search({ q: query, domain, k: 20 }).catch(() => null)
      : Promise.resolve(null),
  ]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold text-zellige-900">{t("title")}</h1>
        <p className="text-zellige-500">{t("subtitle")}</p>
      </div>

      <div className="mt-6">
        <SearchBar locale={locale} initialValue={query ?? ""} placeholder={t("searchPlaceholder")} buttonLabel={t("searchButton")} domain={domain} />
      </div>

      {/* Domain filter chips */}
      <div className="mt-5 flex flex-wrap gap-2">
        <Link
          href={`/${locale}/laws${query ? `?q=${encodeURIComponent(query)}` : ""}`}
          className={!domain ? "rounded-full bg-zellige-700 px-3.5 py-1.5 text-sm font-medium text-white" : "rounded-full border border-zellige-200 bg-white px-3.5 py-1.5 text-sm text-zellige-600 hover:bg-zellige-50"}
        >
          {t("allDomains")}
        </Link>
        {domains.map((d) => {
          const active = domain === d.domain;
          const qs = new URLSearchParams();
          if (d.domain) qs.set("domain", d.domain);
          if (query) qs.set("q", query);
          return (
            <Link
              key={d.domain}
              href={`/${locale}/laws?${qs}`}
              className={active ? "rounded-full bg-zellige-700 px-3.5 py-1.5 text-sm font-medium text-white" : "rounded-full border border-zellige-200 bg-white px-3.5 py-1.5 text-sm text-zellige-600 hover:bg-zellige-50"}
            >
              {d.label[locale as Locale]}{" "}
              <span className={active ? "text-zellige-200" : "text-zellige-400"}>({d.laws})</span>
            </Link>
          );
        })}
      </div>

      {/* Search results */}
      {query && searchResponse && (
        <section className="mt-8">
          <h2 className="mb-4 text-lg font-bold text-zellige-900">
            {t("searchInLaws")} — {t("resultsFor")} «{query}»
          </h2>
          <SearchResults response={searchResponse} locale={locale} />
        </section>
      )}

      {/* Law list */}
      {!query && (
        <section className="mt-8">
          {laws.length === 0 ? (
            <p className="rounded-xl border border-dashed border-zellige-200 bg-white p-8 text-center text-zellige-500">
              {t("noResults")}
            </p>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {laws.map((law) => (
                <Link key={law.slug} href={`/${locale}/laws/${law.slug}`} className="group">
                  <Card className="h-full transition-all group-hover:-translate-y-0.5 group-hover:shadow-md">
                    <CardContent className="p-5">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h3 className="truncate font-bold text-zellige-900">
                            {lawTitle(law, locale)}
                          </h3>
                          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-zellige-500">
                            {law.law_number && (
                              <Badge variant="outline">
                                {t("lawNumber")} {law.law_number}
                              </Badge>
                            )}
                            {law.year && <Badge variant="sand">{law.year}</Badge>}
                            <Badge variant={law.language === "ar" ? "default" : "secondary"}>
                              {law.language.toUpperCase()}
                            </Badge>
                          </div>
                        </div>
                        <FileText className="h-5 w-5 shrink-0 text-zellige-300" />
                      </div>
                      <div className="mt-3 text-sm text-zellige-500">
                        {formatNumber(law.article_count, locale)} {t("articles")} ·{" "}
                        {formatNumber(law.page_count, locale)} {t("pages")}
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
