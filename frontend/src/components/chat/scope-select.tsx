"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Header, ListBox, Select } from "@heroui/react";
import { Library } from "lucide-react";
import { api } from "@/lib/api";
import type { DomainInfo, LawSummary } from "@/lib/types";
import { lawTitle } from "@/lib/utils";
import { DomainIcon } from "@/components/common/domain-icon";

/** Where answers may come from: the whole corpus, one legal domain, or one law (all its
 * editions). Keys: "" | "domain:<id>" | "group:<group_slug>". */
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

  // One entry per law (group), titled in the UI language when an edition has it.
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

  return (
    <Select
      aria-label={t("scopeLabel")}
      selectedKey={scopeKey(scope)}
      onSelectionChange={(key) => key != null && select(String(key))}
      className="max-w-[16rem] min-w-0"
    >
      <Select.Trigger className="h-8 min-h-8 gap-1.5 rounded-full border-0 bg-default px-3 text-xs shadow-none">
        <Library className="size-3.5 shrink-0 text-accent" aria-hidden />
        <Select.Value className="truncate">
          {/* While the lists load, show the saved label instead of a blank trigger. */}
          {scope.label ?? t("scopeAll")}
        </Select.Value>
        <Select.Indicator />
      </Select.Trigger>
      <Select.Popover className="min-w-72">
        <ListBox className="max-h-80">
          <ListBox.Item id={ALL} textValue={t("scopeAll")}>
            {t("scopeAll")}
            <ListBox.ItemIndicator />
          </ListBox.Item>
          <ListBox.Section>
            <Header>{t("scopeDomains")}</Header>
            {domains.map((d) => (
              <ListBox.Item key={d.domain} id={`domain:${d.domain}`} textValue={domainLabel(d)}>
                <DomainIcon domain={d.domain} className="size-3.5 text-muted" />
                {domainLabel(d)}
                <ListBox.ItemIndicator />
              </ListBox.Item>
            ))}
          </ListBox.Section>
          <ListBox.Section>
            <Header>{t("scopeLaws")}</Header>
            {groups.map((law) => (
              <ListBox.Item key={law.group_slug} id={`group:${law.group_slug}`} textValue={lawTitle(law, locale)}>
                <span className="truncate" dir="auto">
                  {lawTitle(law, locale)}
                </span>
                <ListBox.ItemIndicator />
              </ListBox.Item>
            ))}
          </ListBox.Section>
        </ListBox>
      </Select.Popover>
    </Select>
  );
}
