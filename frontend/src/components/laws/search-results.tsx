import Link from "next/link";
import { Card, Chip } from "@/components/ui/heroui";
import type { SearchResponse } from "@/lib/types";

export function SearchResults({
  response,
  locale,
  emptyLabel,
}: {
  response: SearchResponse;
  locale: string;
  emptyLabel: string;
}) {
  if (!response.results.length) {
    return <p className="rounded-2xl border border-dashed border-border p-10 text-center text-muted">{emptyLabel}</p>;
  }
  return (
    <ol className="flex flex-col gap-3">
      {response.results.map((hit, index) => (
        <li key={`${hit.law_slug}-${hit.article_number}-${index}`}>
          <Link
            href={`/${locale}/laws/${hit.law_slug}#article-${encodeURIComponent(hit.article_number)}`}
            className="group block rounded-[var(--radius)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          >
            <Card className="gap-3 p-5 transition-shadow group-hover:shadow-md">
              <div className="flex flex-wrap items-center gap-2">
                <Chip size="sm" color="accent" variant="soft">
                  {locale !== "ar" && hit.law_title_fr ? hit.law_title_fr : hit.law_title}
                </Chip>
                <Chip size="sm" variant="secondary">
                  {locale === "ar" ? `المادة ${hit.article_number}` : `Art. ${hit.article_number}`}
                </Chip>
                <span className="text-xs text-muted">
                  {locale === "ar" ? "ص" : "p."}
                  {hit.page}
                </span>
              </div>
              <p className="line-clamp-3 leading-7" dir={hit.language === "fr" ? "ltr" : "rtl"}>
                {hit.text}
              </p>
            </Card>
          </Link>
        </li>
      ))}
    </ol>
  );
}
