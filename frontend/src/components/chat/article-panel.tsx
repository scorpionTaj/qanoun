"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { BookOpen, Check, Copy, ExternalLink, Loader2, X } from "lucide-react";
import { api, lawUrl } from "@/lib/api";
import type { Article, SearchHit } from "@/lib/types";
import { cn } from "@/lib/utils";

/** The cited article, beside the answer (desktop) or as a bottom sheet (mobile). Shows the
 * full article text — the retrieved passage is only a chunk of it. */
export function ArticlePanel({
  hit,
  index,
  locale,
  onClose,
}: {
  hit: SearchHit | null;
  index: number | null; // citation number shown in the answer, 1-based
  locale: string;
  onClose: () => void;
}) {
  const t = useTranslations("chat");
  const [article, setArticle] = useState<Article | null>(null);
  const [failed, setFailed] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setArticle(null);
    setFailed(false);
    if (!hit) return;
    let cancelled = false;
    api
      .article(hit.law_slug, hit.article_number)
      .then((a) => !cancelled && setArticle(a))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [hit]);

  useEffect(() => {
    if (!hit) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [hit, onClose]);

  if (!hit) {
    return (
      <div className="hidden h-full flex-col items-center justify-center gap-3 p-6 text-center lg:flex">
        <BookOpen className="h-8 w-8 text-zellige-300 dark:text-zellige-700" aria-hidden />
        <p className="max-w-[16rem] text-sm leading-6 text-zellige-500 dark:text-zellige-400">{t("panelHint")}</p>
      </div>
    );
  }

  const title = locale !== "ar" && hit.law_title_fr ? hit.law_title_fr : hit.law_title;
  const label = hit.language === "fr" || locale !== "ar" ? `Art. ${hit.article_number}` : `المادة ${hit.article_number}`;
  const text = article?.text ?? hit.text;
  const href = lawUrl(locale, hit.law_slug, hit.article_number);

  const copy = async () => {
    await navigator.clipboard.writeText(`«${title}» — ${label}\n${text}\n${window.location.origin}${href}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  return (
    <>
      {/* Mobile/tablet: dimmed backdrop behind the bottom sheet */}
      <button
        aria-label={t("closePanel")}
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/40 lg:hidden"
      />
      <aside
        aria-label={t("panelTitle")}
        className={cn(
          "flex flex-col bg-white dark:bg-[#101c17]",
          // bottom sheet below lg, in-flow column from lg
          "fixed inset-x-0 bottom-0 z-50 max-h-[78dvh] rounded-t-2xl border-t border-zellige-100 shadow-2xl dark:border-zellige-800",
          "lg:static lg:z-auto lg:h-full lg:max-h-none lg:rounded-none lg:border-t-0 lg:shadow-none"
        )}
      >
        <div className="flex items-start justify-between gap-3 border-b border-zellige-100 p-4 dark:border-zellige-800">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-xs text-zellige-500 dark:text-zellige-400">
              {index != null && (
                <span className="flex h-5 min-w-5 items-center justify-center rounded-md bg-zellige-700 px-1 font-bold text-white dark:bg-zellige-500 dark:text-zellige-950">
                  {index}
                </span>
              )}
              <span>{t("panelTitle")}</span>
            </div>
            <h2 className="mt-1 text-base font-bold leading-6 text-zellige-900 dark:text-white" dir="auto">
              {title}
            </h2>
            <p className="mt-0.5 text-sm font-semibold text-zellige-600 dark:text-zellige-300" dir="auto">
              {label}
              <span className="ms-2 text-xs font-normal text-zellige-400">
                {locale === "ar" ? "ص" : "p."}
                {article ? article.page_start : hit.page}
              </span>
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label={t("closePanel")}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-zellige-500 hover:bg-zellige-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zellige-500 dark:hover:bg-zellige-800"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        <div className="thin-scroll flex-1 overflow-y-auto overscroll-contain p-4">
          {!article && !failed && (
            <Loader2 className="mb-3 h-4 w-4 animate-spin text-zellige-400" aria-label={t("loadingArticle")} />
          )}
          <p
            className="whitespace-pre-line font-arabic text-[1.05rem] leading-8 text-zellige-900 dark:text-zellige-100"
            dir={hit.language === "fr" ? "ltr" : "rtl"}
          >
            {text}
          </p>
        </div>

        <div className="flex items-center gap-2 border-t border-zellige-100 p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] dark:border-zellige-800">
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-xl bg-zellige-700 px-3 text-sm font-medium text-white transition-colors hover:bg-zellige-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zellige-500 dark:bg-zellige-500 dark:text-zellige-950 dark:hover:bg-zellige-400"
          >
            <ExternalLink className="h-3.5 w-3.5 rtl:-scale-x-100" aria-hidden />
            {t("openInReader")}
          </a>
          <button
            onClick={() => void copy()}
            className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-zellige-200 px-3 text-sm text-zellige-700 transition-colors hover:bg-zellige-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zellige-500 dark:border-zellige-700 dark:text-zellige-200 dark:hover:bg-zellige-800"
          >
            {copied ? <Check className="h-3.5 w-3.5" aria-hidden /> : <Copy className="h-3.5 w-3.5" aria-hidden />}
            {copied ? t("copied") : t("copyArticle")}
          </button>
        </div>
      </aside>
    </>
  );
}
