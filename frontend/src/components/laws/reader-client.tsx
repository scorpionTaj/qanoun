"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Check, Copy, Link2, Minus, Plus, Search } from "lucide-react";
import type { Article } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { cn, normalizeArabic } from "@/lib/utils";

type FontSize = "sm" | "base" | "lg" | "xl";
const FONT_KEY = "qanoun-reader-font";

export function ReaderClient({
  articles,
  lawTitle,
  locale,
  isArabic,
}: {
  articles: Article[];
  lawTitle: string;
  locale: string;
  isArabic: boolean;
}) {
  const t = useTranslations("reader");
  const [fontSize, setFontSize] = useState<FontSize>("base");
  const [query, setQuery] = useState("");
  const [copied, setCopied] = useState<number | null>(null);

  // Restore the saved font size (written by setFont; read after mount to avoid a
  // server/client hydration mismatch).
  useEffect(() => {
    try {
      const saved = localStorage.getItem(FONT_KEY) as FontSize | null;
      if (saved && ["sm", "base", "lg", "xl"].includes(saved)) setFontSize(saved);
    } catch {}
  }, []);

  // Normalized once per law, not per keystroke.
  const normalizedTexts = useMemo(() => articles.map((a) => normalizeArabic(a.text)), [articles]);

  const filtered = useMemo(() => {
    const q = normalizeArabic(query.trim());
    if (!q) return articles;
    // match by article number prefix or by content (أحكام finds احكام, ١٢ finds 12)
    return articles.filter((a, i) => a.number.startsWith(q) || normalizedTexts[i].includes(q));
  }, [articles, normalizedTexts, query]);

  const setFont = (dir: 1 | -1) => {
    const order: FontSize[] = ["sm", "base", "lg", "xl"];
    const next = order[Math.min(order.length - 1, Math.max(0, order.indexOf(fontSize) + dir))];
    setFontSize(next);
    try {
      localStorage.setItem(FONT_KEY, next);
    } catch {}
  };

  const copyCitation = async (article: Article) => {
    const label = isArabic
      ? `«${lawTitle}» — المادة ${article.number}`
      : `«${lawTitle}» — Article ${article.number}`;
    const url = `${window.location.origin}/${locale}/laws/${window.location.pathname.split("/").pop()}#article-${encodeURIComponent(article.number)}`;
    await navigator.clipboard.writeText(`${label}\n${url}`);
    setCopied(article.id);
    setTimeout(() => setCopied(null), 1600);
  };

  const shareLaw = async () => {
    await navigator.clipboard.writeText(window.location.href);
    setCopied(-1);
    setTimeout(() => setCopied(null), 1600);
  };

  const articleLabel = (number: string) =>
    isArabic ? `المادة ${number}` : `Article ${number}`;

  return (
    <div>
      {/* Toolbar */}
      <div className="sticky top-16 z-20 -mx-4 mb-6 flex flex-wrap items-center gap-2 border-b border-zellige-100 bg-sand-50/95 px-4 py-3 backdrop-blur dark:border-zellige-800 dark:bg-[#0b1310]/95">
        <div className="relative flex-1 min-w-52">
          <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zellige-400" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("jumpPlaceholder")}
            className="h-9 ps-9 text-sm"
          />
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-zellige-200 p-0.5 dark:border-zellige-700">
          <button
            onClick={() => setFont(-1)}
            aria-label="smaller font"
            className="flex h-7 w-7 items-center justify-center rounded-md text-zellige-600 hover:bg-zellige-100 dark:text-zellige-300 dark:hover:bg-zellige-800"
          >
            <Minus className="h-3.5 w-3.5" />
          </button>
          <span className="w-8 text-center text-xs font-bold text-zellige-500 dark:text-zellige-400">
            A
          </span>
          <button
            onClick={() => setFont(1)}
            aria-label="larger font"
            className="flex h-7 w-7 items-center justify-center rounded-md text-zellige-600 hover:bg-zellige-100 dark:text-zellige-300 dark:hover:bg-zellige-800"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        </div>
        <button
          onClick={shareLaw}
          className="flex h-9 items-center gap-1.5 rounded-lg border border-zellige-200 px-3 text-xs font-medium text-zellige-700 hover:bg-zellige-50 dark:border-zellige-700 dark:text-zellige-200 dark:hover:bg-zellige-800"
        >
          {copied === -1 ? <Check className="h-3.5 w-3.5 text-zellige-500" /> : <Link2 className="h-3.5 w-3.5" />}
          {copied === -1 ? t("copied") : t("share")}
        </button>
        <span className="text-xs text-zellige-400">
          {filtered.length}/{articles.length}
        </span>
      </div>

      {/* Articles */}
      <div className="reader-body flex flex-col gap-3" data-size={fontSize}>
        {filtered.length === 0 && (
          <p className="rounded-xl border border-dashed border-zellige-200 bg-white p-8 text-center text-zellige-500 dark:border-zellige-700 dark:bg-[#12201a]">
            {t("noMatch")}
          </p>
        )}
        {filtered.map((article) => (
          <article
            key={article.id}
            id={`article-${encodeURIComponent(article.number)}`}
            className="article-target article-card scroll-mt-32 rounded-xl border border-zellige-100 bg-white p-5 shadow-sm transition-shadow hover:shadow dark:border-zellige-800 dark:bg-[#12201a]"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="inline-flex items-center rounded-lg bg-zellige-700 px-2.5 py-1 text-sm font-bold text-white dark:bg-zellige-600">
                {articleLabel(article.number)}
              </span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-zellige-400 dark:text-zellige-500">
                  {isArabic ? "ص" : "p."}
                  {article.page_start}
                  {article.page_end !== article.page_start ? `–${article.page_end}` : ""}
                </span>
                <button
                  onClick={() => void copyCitation(article)}
                  title={t("copyCitation")}
                  className="flex h-7 w-7 items-center justify-center rounded-md text-zellige-400 transition-colors hover:bg-zellige-100 hover:text-zellige-700 dark:hover:bg-zellige-800 dark:hover:text-zellige-200"
                >
                  {copied === article.id ? (
                    <Check className="h-3.5 w-3.5 text-zellige-500" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                </button>
              </div>
            </div>
            <p className="mt-3 leading-8 text-zellige-900 dark:text-zellige-100" dir={isArabic ? "rtl" : "ltr"}>
              {article.text}
            </p>
          </article>
        ))}
      </div>
    </div>
  );
}
