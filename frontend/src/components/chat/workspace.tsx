"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Gavel, MessageSquarePlus, MessagesSquare, Trash2, X } from "lucide-react";
import {
  loadConversations,
  newConversation,
  saveConversations,
  titleFor,
  type Conversation,
  type Message,
} from "@/lib/conversations";
import type { SearchHit } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ChatPanel } from "./chat-panel";
import { ArticlePanel } from "./article-panel";

/** "Majlis": history · conversation · cited article, side by side. Below lg the history is
 * a drawer and the article a bottom sheet. */
export function Workspace({ locale, initialQuestion }: { locale: string; initialQuestion: string }) {
  const t = useTranslations("chat");
  const router = useRouter();
  const pathname = usePathname();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  // The conversation opened on arrival is the only one that may auto-ask a ?q= question.
  const [first] = useState<Conversation>(() => newConversation());
  const [active, setActive] = useState<Conversation>(first);
  const [loaded, setLoaded] = useState(false);
  const [source, setSource] = useState<{ hit: SearchHit; n: number } | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);

  // Saved conversations come from localStorage, so they load after mount (no hydration
  // mismatch). A ?q= question always starts a fresh conversation; drop it from the URL so
  // a reload doesn't ask it again.
  useEffect(() => {
    setConversations(loadConversations());
    setLoaded(true);
    // Through the Next router: a raw history.replaceState is overwritten by its own state.
    if (initialQuestion) router.replace(pathname, { scroll: false });
  }, [initialQuestion, pathname, router]);

  const onChange = useCallback(
    (messages: Message[]) => {
      if (!messages.length) return;
      const updated: Conversation = {
        ...active,
        messages,
        title: titleFor(messages),
        updatedAt: Date.now(),
      };
      setConversations((prev) => {
        const next = [updated, ...prev.filter((c) => c.id !== updated.id)];
        if (!messages.some((m) => m.streaming)) saveConversations(next);
        return next;
      });
    },
    // Recreated per conversation: `active` here is only used for its id.
    [active.id] // eslint-disable-line react-hooks/exhaustive-deps
  );

  const open = (conversation: Conversation) => {
    setActive(conversation);
    setSource(null);
    setHistoryOpen(false);
  };

  const startNew = () => open(newConversation());

  const remove = (id: string) => {
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id);
      saveConversations(next);
      return next;
    });
    if (id === active.id) startNew();
  };

  const openSource = useCallback((hit: SearchHit, n: number) => setSource({ hit, n }), []);
  const closeSource = useCallback(() => setSource(null), []);

  // Reopening that first conversation from history passes its saved messages, so it never
  // asks twice.
  const autoQuestion = active.id === first.id && active.messages.length === 0 ? initialQuestion : "";

  return (
    <div className="grid h-[calc(100dvh-4rem)] grid-cols-1 max-md:h-[calc(100dvh-8rem)] lg:grid-cols-[16rem_minmax(0,1fr)_24rem] xl:grid-cols-[17rem_minmax(0,1fr)_28rem]">
      {/* History: column on lg+, drawer below */}
      {historyOpen && (
        <button
          aria-label={t("closeHistory")}
          onClick={() => setHistoryOpen(false)}
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
        />
      )}
      <aside
        aria-label={t("history")}
        className={cn(
          "flex flex-col border-zellige-100 bg-sand-50 dark:border-zellige-800 dark:bg-[#0d1813] lg:border-e",
          historyOpen
            ? "fixed inset-y-0 start-0 z-50 w-[85vw] max-w-xs border-e shadow-2xl"
            : "hidden lg:flex"
        )}
      >
        <div className="flex items-center gap-2 p-3">
          <button
            onClick={startNew}
            className="flex h-10 flex-1 items-center justify-center gap-2 rounded-xl bg-zellige-700 text-sm font-medium text-white transition-colors hover:bg-zellige-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zellige-500 dark:bg-zellige-500 dark:text-zellige-950 dark:hover:bg-zellige-400"
          >
            <MessageSquarePlus className="h-4 w-4" aria-hidden />
            {t("newChat")}
          </button>
          <button
            onClick={() => setHistoryOpen(false)}
            aria-label={t("closeHistory")}
            className="flex h-10 w-10 items-center justify-center rounded-xl text-zellige-500 hover:bg-zellige-100 dark:hover:bg-zellige-800 lg:hidden"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        <div className="px-4 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-zellige-400 dark:text-zellige-500">
          {t("history")}
        </div>
        <nav className="thin-scroll flex-1 overflow-y-auto px-2 pb-3">
          {loaded && conversations.length === 0 && (
            <p className="px-2 py-3 text-xs leading-5 text-zellige-400 dark:text-zellige-500">{t("noHistory")}</p>
          )}
          <ul className="flex flex-col gap-0.5">
            {conversations.map((c) => (
              <HistoryItem
                key={c.id}
                conversation={c}
                active={c.id === active.id}
                locale={locale}
                onOpen={() => open(c)}
                onDelete={() => remove(c.id)}
              />
            ))}
          </ul>
        </nav>

        <div className="border-t border-zellige-100 p-3 dark:border-zellige-800">
          <Link
            href={`/${locale}/laws`}
            className="flex items-center gap-2 rounded-lg px-2 py-2 text-sm text-zellige-600 hover:bg-zellige-100 dark:text-zellige-300 dark:hover:bg-zellige-800"
          >
            <Gavel className="h-4 w-4" aria-hidden />
            {t("browseLaws")}
          </Link>
        </div>
      </aside>

      {/* Conversation (remounts per conversation so its state starts clean) */}
      <ChatPanel
        key={active.id}
        locale={locale}
        initialMessages={active.messages}
        initialQuestion={autoQuestion}
        onChange={onChange}
        onOpenSource={openSource}
        activeArticleId={source?.hit.article_id ?? null}
        onShowHistory={() => setHistoryOpen(true)}
      />

      {/* Cited article: column on lg+, bottom sheet below */}
      <div className="contents lg:block lg:min-h-0 lg:border-s lg:border-zellige-100 lg:dark:border-zellige-800">
        <ArticlePanel hit={source?.hit ?? null} index={source?.n ?? null} locale={locale} onClose={closeSource} />
      </div>
    </div>
  );
}

function HistoryItem({
  conversation,
  active,
  locale,
  onOpen,
  onDelete,
}: {
  conversation: Conversation;
  active: boolean;
  locale: string;
  onOpen: () => void;
  onDelete: () => void;
}) {
  const t = useTranslations("chat");
  const [confirming, setConfirming] = useState(false);
  const date = new Intl.DateTimeFormat(locale === "ar" ? "ar-MA" : locale, {
    day: "numeric",
    month: "short",
  }).format(conversation.updatedAt);

  return (
    <li className="group relative">
      <button
        onClick={onOpen}
        aria-current={active ? "true" : undefined}
        className={cn(
          "flex w-full items-start gap-2 rounded-lg px-2 py-2 pe-9 text-start text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zellige-500",
          active
            ? "bg-zellige-100 text-zellige-900 dark:bg-zellige-800/80 dark:text-white"
            : "text-zellige-700 hover:bg-zellige-100/70 dark:text-zellige-300 dark:hover:bg-zellige-800/50"
        )}
      >
        <MessagesSquare className="mt-0.5 h-3.5 w-3.5 shrink-0 opacity-60" aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="block truncate" dir="auto">
            {conversation.title || "…"}
          </span>
          <span className="block text-[11px] text-zellige-400 dark:text-zellige-500">{date}</span>
        </span>
      </button>
      <button
        onClick={() => (confirming ? onDelete() : setConfirming(true))}
        onBlur={() => setConfirming(false)}
        aria-label={confirming ? t("confirmDelete") : t("deleteChat")}
        title={confirming ? t("confirmDelete") : t("deleteChat")}
        className={cn(
          "absolute end-1 top-1.5 flex h-7 items-center justify-center rounded-md px-1.5 text-[11px] transition-opacity focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zellige-500",
          confirming
            ? "bg-red-600 font-medium text-white opacity-100"
            : "text-zellige-400 opacity-0 hover:bg-zellige-200 hover:text-red-700 group-hover:opacity-100 dark:hover:bg-zellige-700 max-lg:opacity-100"
        )}
      >
        {confirming ? t("confirmDelete") : <Trash2 className="h-3.5 w-3.5" aria-hidden />}
      </button>
    </li>
  );
}
