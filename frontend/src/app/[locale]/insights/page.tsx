import { InsightsDashboard } from "@/components/insights/insights-dashboard";

export default async function InsightsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;  return <InsightsDashboard locale={locale} />;
}
