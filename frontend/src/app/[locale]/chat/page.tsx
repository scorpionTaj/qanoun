import { Workspace } from "@/components/chat/workspace";

export default async function ChatPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ q?: string; group?: string; domain?: string }>;
}) {
  const { locale } = await params;
  const { q, group, domain } = await searchParams;
  const initialScope = group ? { group } : domain ? { domain } : null;
  return <Workspace locale={locale} initialQuestion={q ?? ""} initialScope={initialScope} />;
}
