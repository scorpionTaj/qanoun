import { Workspace } from "@/components/chat/workspace";

export default async function ChatPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ q?: string }>;
}) {
  const { locale } = await params;
  const { q } = await searchParams;
  return <Workspace locale={locale} initialQuestion={q ?? ""} />;
}
