"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Button, Chip, Skeleton } from "@heroui/react";
import { BookOpen, Check, Copy, ExternalLink, X } from "lucide-react";
import { api, lawUrl } from "@/lib/api";
import type { Article, SearchHit } from "@/lib/types";

export interface OpenedSource {
  hit: SearchHit;
  n: number; // citation number shown in the answer, 1-based
}

/** The full cited article (the retrieved passage is only a chunk of it). Rendered in the
 * desktop side column and in the mobile bottom drawer. */
export function ArticleView({
  source,
  locale,
  onClose,
}: {
  source: OpenedSource;
  locale: string;
  onClose?: () => void;
}) {
  const t = useTranslations("chat");
  const { hit, n } = source;
  const [article, setArticle] = useState<Article | null>(null);
  const [failed, setFailed] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setArticle(null);
    setFailed(false);
    let cancelled = false;
    api
      .article(hit.law_slug, hit.article_number)
      .then((a) => !cancelled && setArticle(a))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [hit]);

  const title = locale !== "ar" && hit.law_title_fr ? hit.law_title_fr : hit.law_title;
  const label = locale === "ar" ? `المادة ${hit.article_number}` : `Art. ${hit.article_number}`;
  const text = article?.text ?? hit.text;
  const href = lawUrl(locale, hit.law_slug, hit.article_number);

  const copy = async () => {
    await navigator.clipboard.writeText(`«${title}» — ${label}\n${text}\n${window.location.origin}${href}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-start justify-between gap-3 border-b border-separator p-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs text-muted">
            <Chip size="sm" color="accent" variant="primary" className="min-w-6 justify-center font-bold">
              {n}
            </Chip>
            {t("panelTitle")}
          </div>
          <h2 className="mt-2 font-bold leading-6" dir="auto">
            {title}
          </h2>
          <p className="mt-0.5 text-sm font-semibold text-accent" dir="auto">
            {label}
            <span className="ms-2 text-xs font-normal text-muted">
              {locale === "ar" ? "ص" : "p."}
              {article ? article.page_start : hit.page}
            </span>
          </p>
        </div>
        {onClose && (
          <Button isIconOnly size="sm" variant="ghost" aria-label={t("closePanel")} onPress={onClose}>
            <X className="size-4" aria-hidden />
          </Button>
        )}
      </div>

      <div className="thin-scroll min-h-0 flex-1 overflow-y-auto overscroll-contain p-4">
        {!article && !failed && <Skeleton className="mb-3 h-3 w-24 rounded" />}
        <p
          className="whitespace-pre-line font-arabic text-[1.05rem] leading-8"
          dir={hit.language === "fr" ? "ltr" : "rtl"}
          lang={hit.language}
        >
          {text}
        </p>
      </div>

      <div className="flex items-center gap-2 border-t border-separator p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          className="inline-flex h-10 flex-1 items-center justify-center gap-1.5 rounded-full bg-accent px-4 text-sm font-medium text-accent-foreground transition-opacity hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        >
          <ExternalLink className="size-3.5 rtl:-scale-x-100" aria-hidden />
          {t("openInReader")}
        </a>
        <Button variant="secondary" onPress={() => void copy()}>
          {copied ? <Check className="size-3.5" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
          {copied ? t("copied") : t("copyArticle")}
        </Button>
      </div>
    </div>
  );
}

export function ArticlePlaceholder() {
  const t = useTranslations("chat");
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <span className="flex size-14 items-center justify-center rounded-2xl bg-default text-muted">
        <BookOpen className="size-6" aria-hidden />
      </span>
      <p className="max-w-[16rem] text-sm leading-6 text-muted">{t("panelHint")}</p>
    </div>
  );
}
