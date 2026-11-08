"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Autocomplete, Button, Header, ListBox, SearchField, type Key } from "@heroui/react";
import { Library, X } from "lucide-react";
import { api } from "@/lib/api";
import type { DomainInfo, LawSummary } from "@/lib/types";
import { formatNumber, lawTitle, normalizeArabic } from "@/lib/utils";
import { DomainIcon } from "@/components/common/domain-icon";

/** Where answers may come from: the whole corpus, one legal domain, or one law (all its
 * editions). Keys: "all" | "domain:<id>" | "group:<group_slug>". */
export interface Scope {
  domain?: string;
  group?: string;
  label?: string; // shown on each question, e.g. "Code de la famille"
}

const ALL = "all";
const SCOPE_KEY = "qanoun-chat-scope";

export function scopeKey(scope: Scope): string {
  if (scope.group) return `group:${scope.group}`;
  if (scope.domain) return `domain:${scope.domain}`;
  return ALL;
}

export function loadScope(): Scope {
  try {
    const raw = localStorage.getItem(SCOPE_KEY);
    const parsed = raw ? (JSON.parse(raw) as Scope) : {};
    return { domain: parsed.domain || undefined, group: parsed.group || undefined, label: parsed.label };
  } catch {
    return {};
  }
}

export function saveScope(scope: Scope) {
  try {
    localStorage.setItem(SCOPE_KEY, JSON.stringify(scope));
  } catch {}
}

// Same letter folding as the search index: «احكام» finds «أحكام», «famille» finds «Famille».
const matches = (text: string, query: string) => normalizeArabic(text).includes(normalizeArabic(query.trim()));

export function ScopeSelect({
  locale,
  scope,
  onChange,
}: {
  locale: string;
  scope: Scope;
  onChange: (scope: Scope) => void;
}) {
  const t = useTranslations("chat");
  const [domains, setDomains] = useState<DomainInfo[]>([]);
  const [laws, setLaws] = useState<LawSummary[]>([]);

  useEffect(() => {
    api.domains().then(setDomains).catch(() => {});
    api.laws().then(setLaws).catch(() => {});
  }, []);

  // One entry per law (group), titled in the UI language when an edition has it; its
  // article count is the edition's (both editions carry the same articles).
  const groups = useMemo(() => {
    const byGroup = new Map<string, LawSummary>();
    const preferred = locale === "ar" ? "ar" : "fr";
    for (const law of laws) {
      const current = byGroup.get(law.group_slug);
      if (!current || (law.language === preferred && current.language !== preferred)) byGroup.set(law.group_slug, law);
    }
    return [...byGroup.values()].sort((a, b) => lawTitle(a, locale).localeCompare(lawTitle(b, locale), locale));
  }, [laws, locale]);

  const domainLabel = (d: DomainInfo) => d.label[locale as "ar" | "fr" | "en"] ?? d.domain;

  // A scope from a link (?group= / ?domain=) arrives without a label: name it once loaded.
  useEffect(() => {
    if (scope.label) return;
    if (scope.group) {
      const law = groups.find((x) => x.group_slug === scope.group);
      if (law) onChange({ ...scope, label: lawTitle(law, locale) });
    } else if (scope.domain) {
      const d = domains.find((x) => x.domain === scope.domain);
      if (d) onChange({ ...scope, label: domainLabel(d) });
    }
  }, [groups, domains]); // eslint-disable-line react-hooks/exhaustive-deps

  const select = (key: string) => {
    if (key === ALL) return onChange({});
    const [kind, id] = key.split(":");
    if (kind === "domain") {
      const d = domains.find((x) => x.domain === id);
      return onChange({ domain: id, label: d ? domainLabel(d) : id });
    }
    const law = groups.find((x) => x.group_slug === id);
    onChange({ group: id, label: law ? lawTitle(law, locale) : id });
  };

  const scoped = Boolean(scope.group || scope.domain);

  // Name of the current scope in the CURRENT language (a saved label may be from another
  // locale: «Logement & baux» on the English page).
  const currentName = (() => {
    if (scope.group) {
      const law = groups.find((x) => x.group_slug === scope.group);
      return law ? lawTitle(law, locale) : scope.label;
    }
    if (scope.domain) {
      const d = domains.find((x) => x.domain === scope.domain);
      return d ? domainLabel(d) : scope.label;
    }
    return t("scopeAll");
  })();
  const count = (n: number | null) => (n == null ? "" : `${formatNumber(n, locale)} ${t("articlesShort")}`);

  // HeroUI Autocomplete (Select trigger + search field in the popover). It replaced a
  // ComboBox whose re-renders made React 19's dev prop-diff logger read React Aria's
  // collection nodes and throw "childNodes is not supported".
  return (
    <div className="flex min-w-0 items-center gap-1">
      <Autocomplete
        aria-label={t("scopeLabel")}
        value={scopeKey(scope)}
        onChange={(key: Key | Key[] | null) => key != null && !Array.isArray(key) && select(String(key))}
        className="w-[min(18rem,60vw)]"
      >
        <Autocomplete.Trigger className="h-8 min-h-8 gap-1.5 rounded-full border-0 bg-default ps-3 pe-8 text-xs shadow-none [&_[data-slot=autocomplete-value]]:text-xs">
          <Library className="size-3.5 shrink-0 text-accent" aria-hidden />
          <Autocomplete.Value className="min-w-0 flex-1 truncate">{currentName}</Autocomplete.Value>
          <Autocomplete.Indicator />
        </Autocomplete.Trigger>
        <Autocomplete.Popover className="min-w-80">
          <Autocomplete.Filter filter={matches}>
            <SearchField autoFocus aria-label={t("scopeSearch")} name="scope-search" variant="secondary" className="p-2">
              <SearchField.Group>
                <SearchField.SearchIcon />
                <SearchField.Input placeholder={t("scopeSearch")} />
                <SearchField.ClearButton />
              </SearchField.Group>
            </SearchField>
            <ListBox className="max-h-80" renderEmptyState={() => <p className="p-3 text-sm text-muted">{t("scopeNone")}</p>}>
              <ListBox.Item id={ALL} textValue={t("scopeAll")}>
                <Library className="size-4 text-muted" aria-hidden />
                <span className="flex-1">{t("scopeAll")}</span>
                <ListBox.ItemIndicator />
              </ListBox.Item>
              <ListBox.Section>
                <Header>{t("scopeDomains")}</Header>
                {domains.map((d) => (
                  <ListBox.Item key={d.domain} id={`domain:${d.domain}`} textValue={domainLabel(d)}>
                    <DomainIcon domain={d.domain} className="size-4 text-accent" />
                    <span className="flex-1 truncate">{domainLabel(d)}</span>
                    <span className="text-[11px] tabular-nums text-muted">{count(d.articles)}</span>
                    <ListBox.ItemIndicator />
                  </ListBox.Item>
                ))}
              </ListBox.Section>
              <ListBox.Section>
                <Header>{t("scopeLaws")}</Header>
                {groups.map((law) => (
                  <ListBox.Item key={law.group_slug} id={`group:${law.group_slug}`} textValue={lawTitle(law, locale)}>
                    <DomainIcon domain={law.domain} className="size-4 text-muted" />
                    <span className="flex-1 truncate" dir="auto">
                      {lawTitle(law, locale)}
                    </span>
                    <span className="text-[11px] tabular-nums text-muted">{count(law.article_count)}</span>
                    <ListBox.ItemIndicator />
                  </ListBox.Item>
                ))}
              </ListBox.Section>
            </ListBox>
          </Autocomplete.Filter>
        </Autocomplete.Popover>
      </Autocomplete>
      {scoped && (
        <Button isIconOnly size="sm" variant="ghost" aria-label={t("scopeClear")} onPress={() => onChange({})} className="size-7 min-w-7 rounded-full">
          <X className="size-3.5" aria-hidden />
        </Button>
      )}
    </div>
  );
}
