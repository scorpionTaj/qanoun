"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
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
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNumber } from "@/lib/utils";

const CHART_COLORS = ["#29553b", "#44855d", "#67a27b", "#ba8c4b", "#d6bd8b", "#8c6038", "#234531"];

export function InsightsDashboard({ locale }: { locale: string }) {
  const t = useTranslations("insights");
  const tc = useTranslations("common");
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [domains, setDomains] = useState<DomainInfo[]>([]);
  const [keywords, setKeywords] = useState<KeywordCount[]>([]);
  const [keywordDomain, setKeywordDomain] = useState<string | undefined>();
  const [error, setError] = useState(false);
  const [isDark, setIsDark] = useState(false);

  // Recharts tooltips are inline-styled SVG: follow the html class, including changes.
  useEffect(() => {
    const root = document.documentElement;
    const update = () => setIsDark(root.classList.contains("dark"));
    update();
    const observer = new MutationObserver(update);
    observer.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  const tooltipStyle = {
    backgroundColor: isDark ? "#12201a" : "#ffffff",
    border: `1px solid ${isDark ? "#29553b" : "#c2dbc9"}`,
    borderRadius: 12,
    color: isDark ? "#e0ede5" : "#1d392a",
    fontSize: 12,
  };

  useEffect(() => {
    Promise.all([
      api.analyticsSummary().then(setSummary),
      api.domains().then(setDomains),
      api.keywords().then(setKeywords),
    ]).catch(() => setError(true));
  }, []);

  const loadKeywords = (domain?: string) => {
    setKeywordDomain(domain);
    api.keywords(domain).then(setKeywords).catch(() => setError(true));
  };

  if (error) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-10">
        <p className="rounded-xl border border-dashed border-red-200 bg-red-50 p-8 text-center text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
          {tc("error")}
        </p>
      </div>
    );
  }

  const domainLabels: Record<string, string> = Object.fromEntries(
    domains.map((d) => [d.domain, d.label[locale as "ar" | "fr" | "en"] ?? d.domain])
  );

  const domainData = (summary?.by_domain ?? []).map((d) => ({
    name: domainLabels[d.domain] ?? d.domain,
    laws: d.laws,
    articles: d.articles,
  }));

  const languageLabels: Record<string, string> = { ar: "العربية", fr: "Français", en: "English" };
  const languageData = (summary?.by_language ?? []).map((l) => ({
    name: languageLabels[l.language] ?? l.language,
    value: l.laws,
  }));

  const yearData = (summary?.by_year ?? []).map((y) => ({ year: String(y.year), laws: y.laws }));

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-3xl font-bold text-zellige-900 dark:text-white">{t("title")}</h1>
      <p className="mt-1 text-zellige-500 dark:text-zellige-400">{t("subtitle")}</p>

      {/* KPI row */}
      <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        {summary ? (
          <>
            <Kpi label={t("laws")} value={summary.totals.laws} locale={locale} />
            <Kpi label={t("articles")} value={summary.totals.articles} locale={locale} />
            <Kpi label={t("tokens")} value={summary.totals.chunks} locale={locale} />
            <Kpi
              label={t("articleLength")}
              value={summary.article_length.median_chars}
              locale={locale}
              suffix="ch"
            />
          </>
        ) : (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)
        )}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {/* By domain */}
        <Card>
          <CardHeader>
            <CardTitle>{t("byDomain")}</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            {summary ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={domainData} margin={{ top: 8, right: 0, left: 0, bottom: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e0ede5" />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 11, fill: "#29553b" }}
                    angle={-30}
                    textAnchor="end"
                    interval={0}
                  />
                  {/* Two scales: articles run in the thousands, laws in single digits — on one
                      axis the laws bars were invisible. */}
                  <YAxis yAxisId="articles" tick={{ fontSize: 11, fill: "#44855d" }} allowDecimals={false} />
                  <YAxis yAxisId="laws" orientation="right" tick={{ fontSize: 11, fill: "#ba8c4b" }} allowDecimals={false} />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: isDark ? '#e0ede5' : '#1d392a' }} cursor={{ fill: isDark ? 'rgba(68,133,93,0.15)' : 'rgba(68,133,93,0.10)' }} />
                  <Legend wrapperStyle={{ color: isDark ? "#e0ede5" : "#29553b", fontSize: 12 }} />
                  <Bar yAxisId="articles" dataKey="articles" name={t("articles")} fill="#44855d" radius={[6, 6, 0, 0]} />
                  <Bar yAxisId="laws" dataKey="laws" name={t("laws")} fill="#ba8c4b" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Skeleton className="h-full" />
            )}
          </CardContent>
        </Card>

        {/* By year */}
        <Card>
          <CardHeader>
            <CardTitle>{t("byYear")}</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            {summary ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={yearData} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e0ede5" />
                  <XAxis dataKey="year" tick={{ fontSize: 11, fill: "#29553b" }} />
                  <YAxis tick={{ fontSize: 11, fill: "#44855d" }} allowDecimals={false} />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: isDark ? '#e0ede5' : '#1d392a' }} cursor={{ fill: isDark ? 'rgba(68,133,93,0.15)' : 'rgba(68,133,93,0.10)' }} />
                  <Bar dataKey="laws" fill="#29553b" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Skeleton className="h-full" />
            )}
          </CardContent>
        </Card>

        {/* By language */}
        <Card>
          <CardHeader>
            <CardTitle>{t("byLanguage")}</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            {summary ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={languageData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={55}
                    outerRadius={90}
                    paddingAngle={3}
                  >
                    {languageData.map((_, index) => (
                      <Cell key={index} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: isDark ? '#e0ede5' : '#1d392a' }} cursor={{ fill: isDark ? 'rgba(68,133,93,0.15)' : 'rgba(68,133,93,0.10)' }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <Skeleton className="h-full" />
            )}
          </CardContent>
        </Card>

        {/* Keywords */}
        <Card>
          <CardHeader className="flex-row items-start justify-between space-y-0">
            <div>
              <CardTitle>{t("keywords")}</CardTitle>
              <CardDescription className="mt-1">{t("keywordDomainHint")}</CardDescription>
            </div>
            <select
              value={keywordDomain ?? ""}
              onChange={(e) => loadKeywords(e.target.value || undefined)}
              className="rounded-lg border border-zellige-200 bg-white px-2 py-1.5 text-xs text-zellige-700 dark:border-zellige-700 dark:bg-[#0f1b16] dark:text-zellige-200"
            >
              <option value="">—</option>
              {domains.map((d) => (
                <option key={d.domain} value={d.domain}>
                  {d.label[locale as "ar" | "fr" | "en"]}
                </option>
              ))}
            </select>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={keywords.slice(0, 12)} layout="vertical" margin={{ top: 0, right: 12, left: 24, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e0ede5" />
                <XAxis type="number" tick={{ fontSize: 11, fill: "#44855d" }} />
                <YAxis
                  type="category"
                  dataKey="token"
                  width={90}
                  tick={{ fontSize: 11, fill: "#29553b" }}
                />
                <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: isDark ? '#e0ede5' : '#1d392a' }} cursor={{ fill: isDark ? 'rgba(68,133,93,0.15)' : 'rgba(68,133,93,0.10)' }} />
                <Bar dataKey="count" fill="#ba8c4b" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Kpi({
  label,
  value,
  locale,
  suffix,
}: {
  label: string;
  value: number;
  locale: string;
  suffix?: string;
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="text-2xl font-bold text-zellige-800 dark:text-zellige-100">
          {formatNumber(value, locale)}
          {suffix && <span className="text-sm font-medium text-zellige-400"> {suffix}</span>}
        </div>
        <div className="mt-1 text-sm text-zellige-500 dark:text-zellige-400">{label}</div>
      </CardContent>
    </Card>
  );
}
