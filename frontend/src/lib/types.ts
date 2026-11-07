/** Shared API types mirroring the FastAPI responses (qanoun_api). */

export type Locale = "ar" | "fr" | "en";

export interface DomainInfo {
  domain: string;
  label: { ar: string; fr: string; en: string };
  laws: number;
  articles: number;
}

export interface LawSummary {
  slug: string;
  group_slug: string;
  title_ar: string;
  title_fr: string | null;
  law_number: string | null;
  year: number | null;
  domain: string;
  language: "ar" | "fr";
  source_url: string | null;
  page_count: number | null;
  article_count: number | null;
  chunk_count: number;
}

export interface Article {
  id: number;
  number: string;
  ordinal: number;
  text: string;
  page_start: number;
  page_end: number;
}

export interface LawDetail extends LawSummary {
  preamble: string | null;
  warnings: string[];
  articles: Article[];
}

export interface SearchHit {
  law_slug: string;
  law_title: string;
  law_title_fr: string | null;
  group_slug: string;
  domain: string;
  language: "ar" | "fr";
  article_number: string;
  article_id: number;
  page: number;
  text: string;
  score: number;
}

export interface SearchResponse {
  query: string;
  search_query: string;
  variety: string;
  results: SearchHit[];
}

export interface AnalyticsSummary {
  totals: {
    laws: number;
    articles: number;
    chunks: number;
    domains: number;
    year_min: number | null;
    year_max: number | null;
  };
  by_domain: { domain: string; laws: number; articles: number; chunks: number }[];
  by_year: { year: number; laws: number }[];
  by_language: { language: string; laws: number }[];
  article_length: { median_chars: number; avg_chars: number; max_chars: number };
}

export interface KeywordCount {
  token: string;
  count: number;
}
