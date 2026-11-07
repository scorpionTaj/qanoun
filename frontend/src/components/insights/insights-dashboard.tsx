"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Alert, Card, Label, ListBox, Select, Skeleton } from "@heroui/react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import type { AnalyticsSummary, DomainInfo, KeywordCount } from "@/lib/types";
import { formatNumber } from "@/lib/utils";

// Theme tokens (globals.css), so charts follow the palette and dark mode automatically.
const ACCENT = "var(--accent)";
const SAFFRON = "var(--color-saffron-500)";
const MUTED = "var(--muted)";
const GRID = "var(--separator)";
const PIE = [ACCENT, SAFFRON, "var(--muted)"];
const tick = { fontSize: 11, fill: MUTED };
const tooltipProps = {
  contentStyle: {
    background: "var(--overlay)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    color: "var(--overlay-foreground)",
    fontSize: 12,
  },
  labelStyle: { color: "var(--overlay-foreground)", fontWeight: 600 },
  itemStyle: { color: "var(--overlay-foreground)" },
  cursor: { fill: "color-mix(in oklch, var(--accent) 10%, transparent)" },
};

const ALL = "__all__";

export function InsightsDashboard({ locale }: { locale: string }) {
  const t = useTranslations("insights");
  const tc = useTranslations("common");
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [domains, setDomains] = useState<DomainInfo[]>([]);
  const [keywords, setKeywords] = useState<KeywordCount[] | null>(null);
  const [keywordDomain, setKeywordDomain] = useState<string>(ALL);
  const [error, setError] = useState(false);

  useEffect(() => {
    Promise.all([
      api.analyticsSummary().then(setSummary),
      api.domains().then(setDomains),
      api.keywords().then(setKeywords),
    ]).catch(() => setError(true));
  }, []);

  const loadKeywords = (domain: string) => {
    setKeywordDomain(domain);
    setKeywords(null);
    api
      .keywords(domain === ALL ? undefined : domain)
      .then(setKeywords)
      .catch(() => setError(true));
  };

  const label = (d: DomainInfo) => d.label[locale as "ar" | "fr" | "en"] ?? d.domain;
  const domainLabels = Object.fromEntries(domains.map((d) => [d.domain, label(d)]));
  const domainData = (summary?.by_domain ?? []).map((d) => ({
    name: domainLabels[d.domain] ?? d.domain,
    laws: d.laws,
    articles: d.articles,
  }));
  const languageNames: Record<string, string> = { ar: "العربية", fr: "Français", en: "English" };
  const languageData = (summary?.by_language ?? []).map((l) => ({
    name: languageNames[l.language] ?? l.language,
    value: l.laws,
  }));
  const yearData = (summary?.by_year ?? []).map((y) => ({ year: String(y.year), laws: y.laws }));

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-3xl font-bold">{t("title")}</h1>
      <p className="mt-1 text-muted">{t("subtitle")}</p>

      {error && (
        <Alert status="danger" className="mt-6">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Title>{tc("error")}</Alert.Title>
          </Alert.Content>
        </Alert>
      )}

      {/* KPI row */}
      <dl className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        {summary
          ? [
              { label: t("laws"), value: summary.totals.laws },
              { label: t("articles"), value: summary.totals.articles },
              { label: t("tokens"), value: summary.totals.chunks },
              { label: t("articleLength"), value: summary.article_length.median_chars, suffix: t("chars") },
            ].map(({ label: name, value, suffix }) => (
              <Card key={name} className="gap-1 p-5">
                <dt className="order-2 text-sm text-muted">{name}</dt>
                <dd className="order-1 text-3xl font-bold tabular-nums">
                  {formatNumber(value, locale)}
                  {suffix && <span className="ms-1 text-sm font-medium text-muted">{suffix}</span>}
                </dd>
              </Card>
            ))
          : Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-[var(--radius)]" />)}
      </dl>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <ChartCard title={t("byDomain")} ready={!!summary}>
          <BarChart data={domainData} margin={{ top: 8, right: 0, left: 0, bottom: 24 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
            <XAxis dataKey="name" tick={tick} angle={-30} textAnchor="end" interval={0} height={60} />
            {/* Two scales: articles run in the thousands, laws in single digits. */}
            <YAxis yAxisId="articles" tick={tick} allowDecimals={false} />
            <YAxis yAxisId="laws" orientation="right" tick={tick} allowDecimals={false} />
            <Tooltip {...tooltipProps} />
            <Legend wrapperStyle={{ color: MUTED, fontSize: 12 }} />
            <Bar yAxisId="articles" dataKey="articles" name={t("articles")} fill={ACCENT} radius={[6, 6, 0, 0]} />
            <Bar yAxisId="laws" dataKey="laws" name={t("laws")} fill={SAFFRON} radius={[6, 6, 0, 0]} />
          </BarChart>
        </ChartCard>

        <ChartCard title={t("byYear")} ready={!!summary}>
          <BarChart data={yearData} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
            <XAxis dataKey="year" tick={tick} />
            <YAxis tick={tick} allowDecimals={false} />
            <Tooltip {...tooltipProps} />
            <Bar dataKey="laws" name={t("laws")} fill={ACCENT} radius={[6, 6, 0, 0]} />
          </BarChart>
        </ChartCard>

        <ChartCard title={t("byLanguage")} ready={!!summary}>
          <PieChart>
            <Pie data={languageData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={95} paddingAngle={3} stroke="none">
              {languageData.map((_, index) => (
                <Cell key={index} fill={PIE[index % PIE.length]} />
              ))}
            </Pie>
            <Tooltip {...tooltipProps} />
            <Legend wrapperStyle={{ color: MUTED, fontSize: 12 }} />
          </PieChart>
        </ChartCard>

        <ChartCard
          title={t("keywords")}
          ready={keywords !== null}
          action={
            <Select
              aria-label={t("keywordDomainHint")}
              className="w-44"
              selectedKey={keywordDomain}
              onSelectionChange={(key) => key != null && loadKeywords(String(key))}
            >
              <Label className="sr-only">{t("keywordDomainHint")}</Label>
              <Select.Trigger className="h-9">
                <Select.Value />
                <Select.Indicator />
              </Select.Trigger>
              <Select.Popover>
                <ListBox>
                  <ListBox.Item id={ALL} textValue={t("allDomains")}>
                    {t("allDomains")}
                    <ListBox.ItemIndicator />
                  </ListBox.Item>
                  {domains.map((d) => (
                    <ListBox.Item key={d.domain} id={d.domain} textValue={label(d)}>
                      {label(d)}
                      <ListBox.ItemIndicator />
                    </ListBox.Item>
                  ))}
                </ListBox>
              </Select.Popover>
            </Select>
          }
        >
          <BarChart data={(keywords ?? []).slice(0, 12)} layout="vertical" margin={{ top: 0, right: 12, left: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
            <XAxis type="number" tick={tick} />
            <YAxis type="category" dataKey="token" width={96} tick={{ ...tick, fill: "var(--foreground)" }} />
            <Tooltip {...tooltipProps} />
            <Bar dataKey="count" name={t("occurrences")} fill={SAFFRON} radius={[0, 6, 6, 0]} />
          </BarChart>
        </ChartCard>
      </div>
    </div>
  );
}

function ChartCard({
  title,
  ready,
  action,
  children,
}: {
  title: string;
  ready: boolean;
  action?: React.ReactNode;
  children: React.ReactElement;
}) {
  return (
    <Card className="gap-4 p-5">
      <Card.Header className="flex-row items-center justify-between gap-3">
        <Card.Title className="text-base">{title}</Card.Title>
        {action}
      </Card.Header>
      <Card.Content>
        {/* Fixed-height box of its own: Card.Content's flex sizing collapses a percentage
            height, and ResponsiveContainer measures its parent. */}
        <div className="h-72 w-full">
          {ready ? (
            <ResponsiveContainer width="100%" height="100%">
              {children}
            </ResponsiveContainer>
          ) : (
            <Skeleton className="h-full rounded-xl" />
          )}
        </div>
      </Card.Content>
    </Card>
  );
}
