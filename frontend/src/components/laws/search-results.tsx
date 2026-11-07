import Link from "next/link";
import { FileText } from "lucide-react";
import type { SearchResponse } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function SearchResults({ response, locale }: { response: SearchResponse; locale: string }) {
  if (!response.results.length) {
    return (
      <p className="rounded-xl border border-dashed border-zellige-200 bg-white p-8 text-center text-zellige-500">
        0
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {response.results.map((hit, index) => (
        <Link
          key={`${hit.law_slug}-${hit.article_number}-${index}`}
          href={`/${locale}/laws/${hit.law_slug}#article-${encodeURIComponent(hit.article_number)}`}
          className="group"
        >
          <Card className="transition-all group-hover:-translate-y-0.5 group-hover:shadow-md">
            <CardContent className="p-5">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <Badge variant="domain">{locale === "fr" && hit.law_title_fr ? hit.law_title_fr : hit.law_title}</Badge>
                <Badge variant="outline">
                  <FileText className="h-3 w-3" />
                  {locale === "fr"
                    ? `Article ${hit.article_number}`
                    : locale === "en"
                      ? `Article ${hit.article_number}`
                      : `المادة ${hit.article_number}`}
                </Badge>
                <span className="text-zellige-400 dark:text-zellige-500">
                  {locale === "ar" ? "ص" : "p."}
                  {hit.page}
                </span>
              </div>
              <p className="mt-3 line-clamp-3 leading-7 text-zellige-800 dark:text-zellige-100">{hit.text}</p>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  );
}
