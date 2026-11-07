import { ChatPanel } from "@/components/chat/chat-panel";

export default async function ChatPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ q?: string }>;
}) {
  const { locale } = await params;
  const { q } = await searchParams;  return <ChatPanel locale={locale} initialQuestion={q ?? ""} />;
}
