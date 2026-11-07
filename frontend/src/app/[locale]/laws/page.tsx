import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { Card, Chip } from "@/components/ui/heroui";
import { api } from "@/lib/api";
import type { LawSummary } from "@/lib/types";
import { cn, formatNumber, lawTitle } from "@/lib/utils";
import { SearchBar } from "@/components/laws/search-bar";
import { SearchResults } from "@/components/laws/search-results";
import { DomainIcon } from "@/components/common/domain-icon";
import type { Locale } from "@/i18n/routing";

// Live corpus data — must not be baked in at build time.
export const dynamic = "force-dynamic";

/** Bilingual laws are separate documents sharing a group: show one card per law, with its
 * editions (AR / FR) as links, and the edition matching the UI language first. */
function groupEditions(laws: LawSummary[], locale: string): LawSummary[][] {
  const groups = new Map<string, LawSummary[]>();
  for (const law of laws) groups.set(law.group_slug, [...(groups.get(law.group_slug) ?? []), law]);
  const preferred = locale === "ar" ? "ar" : "fr";
  return [...groups.values()].map((editions) =>
    editions.sort((a, b) => Number(b.language === preferred) - Number(a.language === preferred))
  );
}

export default async function LawsPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ domain?: string; q?: string }>;
}) {
  const { locale } = await params;
  const { domain, q } = await searchParams;
  const t = await getTranslations("laws");
  const query = q?.trim();

  const [domains, laws, searchResponse] = await Promise.all([
    api.domains().catch(() => []),
    query ? Promise.resolve([]) : api.laws({ domain }).catch(() => []),
    query ? api.search({ q: query, domain, k: 20 }).catch(() => null) : Promise.resolve(null),
  ]);
  const groups = groupEditions(laws, locale);

  const filterHref = (d?: string) => {
    const qs = new URLSearchParams();
    if (d) qs.set("domain", d);
    if (query) qs.set("q", query);
    return `/${locale}/laws${qs.size ? `?${qs}` : ""}`;
  };
  const chipClass = (active: boolean) =>
    cn(
      "inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm transition-colors",
      "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
      active ? "bg-accent font-medium text-accent-foreground" : "bg-default text-foreground hover:bg-default/70"
    );

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-3xl font-bold">{t("title")}</h1>
      <p className="mt-1 text-muted">{t("subtitle")}</p>

      <div className="sticky top-16 z-20 -mx-4 mt-6 bg-background/90 px-4 py-3 backdrop-blur-md">
        <SearchBar
          locale={locale}
          initialValue={query ?? ""}
          placeholder={t("searchPlaceholder")}
          buttonLabel={t("searchButton")}
          domain={domain}
        />
        <nav aria-label={t("domainFilter")} className="thin-scroll mt-3 flex gap-2 overflow-x-auto pb-1">
          <Link href={filterHref()} className={cn(chipClass(!domain), "shrink-0 whitespace-nowrap")} aria-current={!domain ? "page" : undefined}>
            {t("allDomains")}
          </Link>
          {domains.map((d) => (
            <Link
              key={d.domain}
              href={filterHref(d.domain)}
              className={cn(chipClass(domain === d.domain), "shrink-0 whitespace-nowrap")}
              aria-current={domain === d.domain ? "page" : undefined}
            >
              <DomainIcon domain={d.domain} className="size-3.5" />
              {d.label[locale as Locale]}
              <span className="tabular-nums opacity-70">{d.laws}</span>
            </Link>
          ))}
        </nav>
      </div>

      {query && searchResponse && (
        <section className="mt-6" aria-labelledby="results-title">
          <h2 id="results-title" className="mb-4 text-lg font-bold">
            {t("resultsFor")} «{query}»
          </h2>
          <SearchResults response={searchResponse} locale={locale} emptyLabel={t("noResults")} />
        </section>
      )}

      {!query && (
        <section className="mt-6">
          {groups.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-border p-10 text-center text-muted">{t("noResults")}</p>
          ) : (
            <ul className="grid gap-3 md:grid-cols-2">
              {groups.map((editions) => {
                const main = editions[0];
                return (
                  <li key={main.group_slug}>
                    <Card className="relative h-full gap-3 p-5 transition-shadow hover:shadow-md">
                      <div className="flex items-start gap-3">
                        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent">
                          <DomainIcon domain={main.domain} className="size-5" />
                        </span>
                        <div className="min-w-0 flex-1">
                          <Link
                            href={`/${locale}/laws/${main.slug}`}
                            className="font-bold leading-6 after:absolute after:inset-0 hover:text-accent focus-visible:outline-none"
                          >
                            {lawTitle(main, locale)}
                          </Link>
                          <div className="mt-2 flex flex-wrap items-center gap-1.5">
                            {main.law_number && (
                              <Chip size="sm" variant="secondary">
                                {t("lawNumber")} {main.law_number}
                              </Chip>
                            )}
                            {main.year && (
                              <Chip size="sm" variant="soft" color="warning">
                                {main.year}
                              </Chip>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="mt-auto flex items-center justify-between gap-3 text-sm text-muted">
                        <span className="tabular-nums">
                          {formatNumber(main.article_count, locale)} {t("articles")}
                        </span>
                        {/* Edition links sit above the card-wide link (relative z-10). */}
                        <span className="relative z-10 flex gap-1">
                          {editions.map((edition) => (
                            <Link
                              key={edition.slug}
                              href={`/${locale}/laws/${edition.slug}`}
                              hrefLang={edition.language}
                              aria-label={`${lawTitle(edition, locale)} — ${edition.language.toUpperCase()}`}
                              className="rounded-md bg-default px-2 py-0.5 text-xs font-semibold uppercase text-foreground hover:bg-accent hover:text-accent-foreground"
                            >
                              {edition.language}
                            </Link>
                          ))}
                        </span>
                      </div>
                    </Card>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
