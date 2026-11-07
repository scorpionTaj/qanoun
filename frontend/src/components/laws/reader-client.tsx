"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Button, Chip, SearchField, ToggleButton, ToggleButtonGroup, Tooltip } from "@heroui/react";
import { Check, Copy, Link2 } from "lucide-react";
import type { Article } from "@/lib/types";
import { normalizeArabic } from "@/lib/utils";

type FontSize = "sm" | "base" | "lg" | "xl";
const SIZES: FontSize[] = ["sm", "base", "lg", "xl"];
const FONT_KEY = "qanoun-reader-font";

export function ReaderClient({
  articles,
  lawTitle,
  isArabic,
}: {
  articles: Article[];
  lawTitle: string;
  isArabic: boolean;
}) {
  const t = useTranslations("reader");
  const [fontSize, setFontSize] = useState<FontSize>("base");
  const [query, setQuery] = useState("");
  const [copied, setCopied] = useState<number | null>(null);

  // Restore the saved font size after mount (avoids a hydration mismatch).
  useEffect(() => {
    try {
      const saved = localStorage.getItem(FONT_KEY) as FontSize | null;
      if (saved && SIZES.includes(saved)) setFontSize(saved);
    } catch {}
  }, []);

  const chooseSize = (size: FontSize) => {
    setFontSize(size);
    try {
      localStorage.setItem(FONT_KEY, size);
    } catch {}
  };

  // Normalized once per law, not per keystroke.
  const normalizedTexts = useMemo(() => articles.map((a) => normalizeArabic(a.text)), [articles]);
  const filtered = useMemo(() => {
    const q = normalizeArabic(query.trim());
    if (!q) return articles;
    // by article number prefix or content (أحكام finds احكام, ١٢ finds 12)
    return articles.filter((a, i) => a.number.startsWith(q) || normalizedTexts[i].includes(q));
  }, [articles, normalizedTexts, query]);

  const flash = (id: number) => {
    setCopied(id);
    setTimeout(() => setCopied(null), 1600);
  };

  const copyCitation = async (article: Article) => {
    const label = isArabic ? `«${lawTitle}» — المادة ${article.number}` : `«${lawTitle}» — Article ${article.number}`;
    const url = `${window.location.origin}${window.location.pathname}#article-${encodeURIComponent(article.number)}`;
    await navigator.clipboard.writeText(`${label}\n${url}`);
    flash(article.id);
  };

  const shareLaw = async () => {
    await navigator.clipboard.writeText(window.location.href.split("#")[0]);
    flash(-1);
  };

  const articleLabel = (number: string) => (isArabic ? `المادة ${number}` : `Article ${number}`);

  return (
    <div>
      {/* Toolbar */}
      <div className="sticky top-16 z-20 -mx-4 mb-6 flex flex-wrap items-center gap-2 border-b border-separator bg-background/90 px-4 py-3 backdrop-blur-md">
        <SearchField aria-label={t("jumpPlaceholder")} value={query} onChange={setQuery} className="min-w-52 flex-1">
          <SearchField.Group className="h-10">
            <SearchField.SearchIcon />
            <SearchField.Input placeholder={t("jumpPlaceholder")} />
            <SearchField.ClearButton />
          </SearchField.Group>
        </SearchField>

        <ToggleButtonGroup
          aria-label={t("fontSize")}
          size="sm"
          selectionMode="single"
          disallowEmptySelection
          selectedKeys={[fontSize]}
          onSelectionChange={(keys) => {
            const next = [...keys][0] as FontSize | undefined;
            if (next) chooseSize(next);
          }}
        >
          {SIZES.map((size, i) => (
            <ToggleButton key={size} id={size} aria-label={`${t("fontSize")} ${i + 1}`}>
              {i > 0 && <ToggleButtonGroup.Separator />}
              <span style={{ fontSize: `${0.7 + i * 0.12}rem` }} className="font-semibold">
                A
              </span>
            </ToggleButton>
          ))}
        </ToggleButtonGroup>

        <Button size="sm" variant="secondary" onPress={() => void shareLaw()}>
          {copied === -1 ? <Check className="size-3.5" aria-hidden /> : <Link2 className="size-3.5" aria-hidden />}
          {copied === -1 ? t("copied") : t("share")}
        </Button>

        <span className="text-xs tabular-nums text-muted" aria-live="polite">
          {filtered.length}/{articles.length}
        </span>
      </div>

      {/* Articles */}
      <div className="reader-body flex flex-col gap-3" data-size={fontSize}>
        {filtered.length === 0 && (
          <p className="rounded-2xl border border-dashed border-border p-10 text-center text-muted">{t("noMatch")}</p>
        )}
        {filtered.map((article) => (
          <article
            key={article.id}
            id={`article-${encodeURIComponent(article.number)}`}
            className="article-card scroll-mt-36 rounded-[var(--radius)] border border-separator bg-surface p-5"
          >
            <div className="flex items-center justify-between gap-3">
              <Chip color="accent" variant="primary" className="font-bold">
                {articleLabel(article.number)}
              </Chip>
              <div className="flex items-center gap-1">
                <span className="text-xs tabular-nums text-muted">
                  {isArabic ? "ص" : "p."}
                  {article.page_start}
                  {article.page_end !== article.page_start ? `–${article.page_end}` : ""}
                </span>
                <Tooltip delay={400}>
                  <Button
                    isIconOnly
                    size="sm"
                    variant="ghost"
                    aria-label={t("copyCitation")}
                    onPress={() => void copyCitation(article)}
                  >
                    {copied === article.id ? <Check className="size-3.5" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
                  </Button>
                  <Tooltip.Content>{copied === article.id ? t("copied") : t("copyCitation")}</Tooltip.Content>
                </Tooltip>
              </div>
            </div>
            <p className="mt-3 whitespace-pre-line leading-[2]" dir={isArabic ? "rtl" : "ltr"} lang={isArabic ? "ar" : "fr"}>
              {article.text}
            </p>
          </article>
        ))}
      </div>
    </div>
  );
}
