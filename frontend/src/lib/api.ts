/** Typed API client for the Qanoun FastAPI backend. */

import type {
  AnalyticsSummary,
  Article,
  DomainInfo,
  KeywordCount,
  LawDetail,
  LawSummary,
  SearchResponse,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new ApiError(response.status, `GET ${path} failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  domains: () => get<DomainInfo[]>("/api/domains"),
  laws: (params: { domain?: string; group?: string } = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]);
    const suffix = qs.size ? `?${qs}` : "";
    return get<LawSummary[]>(`/api/laws${suffix}`);
  },
  law: (slug: string) => get<LawDetail>(`/api/laws/${encodeURIComponent(slug)}`),
  article: (slug: string, number: string) =>
    get<Article>(`/api/laws/${encodeURIComponent(slug)}/articles/${encodeURIComponent(number)}`),
  analyticsSummary: () => get<AnalyticsSummary>("/api/analytics/summary"),
  keywords: (domain?: string) =>
    get<KeywordCount[]>(`/api/analytics/keywords${domain ? `?domain=${domain}` : ""}`),
  search: async (body: { q: string; domain?: string; law_slug?: string; k?: number }) => {
    const response = await fetch(`${API_URL}/api/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new ApiError(response.status, `search failed: ${response.status}`);
    }
    return response.json() as Promise<SearchResponse>;
  },
};

export const lawUrl = (locale: string, slug: string, articleNumber?: string) =>
  `/${locale}/laws/${slug}${articleNumber ? `#article-${encodeURIComponent(articleNumber)}` : ""}`;
