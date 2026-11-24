"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { Button, Chip, SearchField, ToggleButton, ToggleButtonGroup, Tooltip } from "@heroui/react";
import { Check, Copy, Link2 } from "lucide-react";
import { lawUrl } from "@/lib/api";
import type { AmendmentEvent, Article, ArticleRef, References } from "@/lib/types";
import { lawTitle as titleIn, normalizeArabic } from "@/lib/utils";

const MAX_REFS_SHOWN = 12;

type FontSize = "sm" | "base" | "lg" | "xl";
const SIZES: FontSize[] = ["sm", "base", "lg", "xl"];
const FONT_KEY = "qanoun-reader-font";

export function ReaderClient({
  articles,
  lawTitle,
  isArabic,
  amended = {},
  lawSlug,
  references,
  history = {},
}: {
  articles: Article[];
  lawTitle: string;
  isArabic: boolean;
  amended?: Record<string, string[]>; // article number → amending texts
  lawSlug: string;
  references?: References;
  history?: Record<string, AmendmentEvent[]>; // article number → changes, oldest first
}) {
  const t = useTranslations("reader");
  const locale = useLocale();
  const [fontSize, setFontSize] = useState<FontSize>("base");
  const [query, setQuery] = useState("");
  const [copied, setCopied] = useState<number | null>(null);
  const [amendedSince, setAmendedSince] = useState<number | null>(null);
  // Years in which this law's articles were amended, newest first, for the "amended since" filter.
  const amendmentYears = useMemo(
    () => [...new Set(Object.values(history).flatMap((events) => events.map((e) => e.year)).filter((y): y is number => !!y))].sort((a, b) => b - a),
    [history],
  );

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
    const since = amendedSince;
    return articles.filter((a, i) => {
      if (since && !(history[a.number] ?? []).some((e) => (e.year ?? 0) >= since)) return false;
      // by article number prefix or content (أحكام finds احكام, ١٢ finds 12)
      return !q || a.number.startsWith(q) || normalizedTexts[i].includes(q);
    });
  }, [articles, normalizedTexts, query, amendedSince, history]);

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

  // Same law: jump within the page. Another law: open its reader at that article.
  const refRow = (label: string, refs: ArticleRef[]) => (
    <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
      <span className="text-muted">{label}</span>
      {refs.slice(0, MAX_REFS_SHOWN).map((ref) => {
        const other = ref.law_slug !== lawSlug ? references?.laws[ref.law_slug] : undefined;
        const text = other ? `${articleLabel(ref.number)} — ${titleIn(other, locale)}` : articleLabel(ref.number);
        return ref.law_slug === lawSlug ? (
          <a key={`${ref.law_slug}#${ref.number}`} href={`#article-${encodeURIComponent(ref.number)}`} className="text-accent hover:underline">
            {text}
          </a>
        ) : (
          <Link key={`${ref.law_slug}#${ref.number}`} href={lawUrl(locale, ref.law_slug, ref.number)} className="text-accent hover:underline">
            {text}
          </Link>
        );
      })}
      {refs.length > MAX_REFS_SHOWN && <span className="text-muted">{t("moreRefs", { count: refs.length - MAX_REFS_SHOWN })}</span>}
    </p>
  );

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

        {amendmentYears.length > 0 && (
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted">{t("amendedSince")}</span>
            <select
              className="h-10 rounded-lg border border-border bg-surface px-2 tabular-nums"
              value={amendedSince ?? ""}
              onChange={(e) => setAmendedSince(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">{t("anyTime")}</option>
              {amendmentYears.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </label>
        )}

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
              <span className="flex items-center gap-2">
                <Chip color="accent" variant="primary" className="font-bold">
                  {articleLabel(article.number)}
                </Chip>
                {amended[article.number] && (
                  <Chip size="sm" variant="soft" color="warning" title={amended[article.number].join(" · ")}>
                    {t("amended", { refs: amended[article.number].join(", ") })}
                  </Chip>
                )}
              </span>
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
            {history[article.number] && (
              <p className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1 border-t border-separator pt-3 text-sm" data-testid="amendment-history">
                <span className="text-muted">{t("history")}</span>
                {history[article.number].map((event) => (
                  <span key={event.ref} className="tabular-nums">
                    {event.year ? <span className="font-semibold">{event.year}</span> : null}{" "}
                    <span dir="ltr">{event.ref}</span>
                    {event.kinds.length ? <span className="text-muted"> ({event.kinds.map((k) => t(`kind.${k}`)).join(locale === "ar" ? "، " : ", ")})</span> : null}
                  </span>
                ))}
              </p>
            )}
            {(references?.cites[article.number] || references?.cited_by[article.number]) && (
              <div className="mt-3 flex flex-col gap-1 border-t border-separator pt-3 text-sm">
                {references.cites[article.number] && refRow(t("refersTo"), references.cites[article.number])}
                {references.cited_by[article.number] && refRow(t("referencedBy"), references.cited_by[article.number])}
              </div>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
