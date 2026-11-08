"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Button, Drawer } from "@heroui/react";
import { BookOpen, MessageSquarePlus, MessagesSquare, Trash2 } from "lucide-react";
import {
  loadConversations,
  newConversation,
  saveConversations,
  titleFor,
  type Conversation,
  type Message,
} from "@/lib/conversations";
import type { SearchHit } from "@/lib/types";
import { accountApi, mergeConversations } from "@/lib/account";
import { cn } from "@/lib/utils";
import { ChatPanel } from "./chat-panel";
import { ArticlePlaceholder, ArticleView, type OpenedSource } from "./article-panel";
import { loadScope, saveScope, type Scope } from "./scope-select";

const DESKTOP = "(min-width: 1024px)";
const PANELS_KEY = "qanoun-panels";

/** True from the lg breakpoint, where history and article are columns instead of drawers. */
function useIsDesktop(): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const query = window.matchMedia(DESKTOP);
      query.addEventListener("change", onChange);
      return () => query.removeEventListener("change", onChange);
    },
    () => window.matchMedia(DESKTOP).matches,
    () => true
  );
}

/** "Majlis": history · conversation · cited article. Below lg, history and article are
 * HeroUI drawers (start side and bottom). */
export function Workspace({
  locale,
  initialQuestion,
  initialScope,
}: {
  locale: string;
  initialQuestion: string;
  initialScope: Scope | null; // from ?group= / ?domain= (e.g. "Ask about this law")
}) {
  const t = useTranslations("chat");
  const router = useRouter();
  const pathname = usePathname();
  const isDesktop = useIsDesktop();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  // The conversation opened on arrival is the only one that may auto-ask a ?q= question.
  const [first] = useState<Conversation>(() => newConversation());
  const [active, setActive] = useState<Conversation>(first);
  const [loaded, setLoaded] = useState(false);
  const [source, setSource] = useState<OpenedSource | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const signedIn = useRef(false);
  // Desktop side columns can be collapsed; remembered per browser.
  const [panels, setPanels] = useState({ history: true, article: true });
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(PANELS_KEY) ?? "null");
      if (saved && typeof saved.history === "boolean" && typeof saved.article === "boolean") setPanels(saved);
    } catch {}
  }, []);
  const togglePanel = useCallback((name: "history" | "article", value?: boolean) => {
    setPanels((prev) => {
      const next = { ...prev, [name]: value ?? !prev[name] };
      try {
        localStorage.setItem(PANELS_KEY, JSON.stringify(next));
      } catch {}
      return next;
    });
  }, []);
  const [scope, setScope] = useState<Scope>({});
  const changeScope = useCallback((next: Scope) => {
    setScope(next);
    saveScope(next);
  }, []);

  // Saved conversations load after mount (no hydration mismatch). Drop ?q= from the URL
  // through the router (a raw history.replaceState is overwritten by Next's own state).
  useEffect(() => {
    setConversations(loadConversations());
    setLoaded(true);
    // Signed in: merge with the server copy (newest wins) and upload what it lacks.
    accountApi
      .me()
      .then(async ({ user }) => {
        if (!user) return;
        signedIn.current = true;
        const remote = await accountApi.conversations();
        const merged = mergeConversations(loadConversations(), remote);
        setConversations(merged);
        saveConversations(merged);
        const remoteAt = new Map(remote.map((c) => [c.id, c.updatedAt]));
        for (const c of merged) if ((remoteAt.get(c.id) ?? -1) < c.updatedAt) void accountApi.put(c).catch(() => {});
      })
      .catch(() => {}); // API down or signed out: the browser copy keeps working
    // A link's scope wins over the remembered one (and becomes the remembered one).
    if (initialScope) changeScope(initialScope);
    else setScope(loadScope());
    if (initialQuestion || initialScope) router.replace(pathname, { scroll: false });
  }, [initialQuestion, initialScope, pathname, router, changeScope]);

  const onChange = useCallback(
    (messages: Message[]) => {
      if (!messages.length) return;
      const updated: Conversation = { ...active, messages, title: titleFor(messages), updatedAt: Date.now() };
      const finished = !messages.some((m) => m.streaming);
      setConversations((prev) => {
        const next = [updated, ...prev.filter((c) => c.id !== updated.id)];
        if (finished) saveConversations(next);
        return next;
      });
      if (finished && signedIn.current) void accountApi.put(updated).catch(() => {});
    },
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
    if (signedIn.current) void accountApi.remove(id).catch(() => {});
    if (id === active.id) startNew();
  };

  const openSource = useCallback(
    (hit: SearchHit, n: number) => {
      setSource({ hit, n });
      togglePanel("article", true); // a citation click must show its article
    },
    [togglePanel]
  );
  const closeSource = useCallback(() => setSource(null), []);

  // Reopening the first conversation from history passes its saved messages: never re-asks.
  const autoQuestion = active.id === first.id && active.messages.length === 0 ? initialQuestion : "";

  const history = (
    <HistoryList
      conversations={conversations}
      loaded={loaded}
      activeId={active.id}
      locale={locale}
      onNew={startNew}
      onOpen={open}
      onDelete={remove}
    />
  );

  return (
    <div
      className="grid h-[calc(100dvh-4rem)] grid-cols-1 transition-[grid-template-columns] duration-200 max-md:h-[calc(100dvh-8rem)]"
      style={
        isDesktop
          ? {
              gridTemplateColumns: [panels.history && "17rem", "minmax(0,1fr)", panels.article && "26rem"]
                .filter(Boolean)
                .join(" "),
            }
          : undefined
      }
    >
      {isDesktop ? (
        panels.history && (
          <aside aria-label={t("history")} className="min-h-0 border-e border-separator bg-surface/60">
            {history}
          </aside>
        )
      ) : (
        <Drawer>
          {/* HeroUI's side drawer positions with logical CSS but slides with a physical
              translateX, which disagree under RTL (it ends up off-screen). Do the drawer's
              geometry in LTR, pick the physical side ourselves, and restore RTL inside. */}
          <Drawer.Backdrop isOpen={historyOpen} onOpenChange={setHistoryOpen} className="[direction:ltr]">
            <Drawer.Content placement={locale === "ar" ? "right" : "left"}>
              <Drawer.Dialog aria-label={t("history")} className="h-full w-[85vw] max-w-xs p-0">
                <div dir={locale === "ar" ? "rtl" : "ltr"} className="h-full">
                  {history}
                </div>
              </Drawer.Dialog>
            </Drawer.Content>
          </Drawer.Backdrop>
        </Drawer>
      )}

      {/* Remounts per conversation so its state starts clean. */}
      <ChatPanel
        key={active.id}
        locale={locale}
        initialMessages={active.messages}
        initialQuestion={autoQuestion}
        onChange={onChange}
        onOpenSource={openSource}
        activeArticleId={source?.hit.article_id ?? null}
        onShowHistory={() => (isDesktop ? togglePanel("history") : setHistoryOpen(true))}
        panels={isDesktop ? panels : null}
        onToggleArticle={() => togglePanel("article")}
        scope={scope}
        onScopeChange={changeScope}
      />

      {isDesktop ? (
        panels.article && (
          <aside aria-label={t("panelTitle")} className="min-h-0 border-s border-separator bg-surface">
            {source ? <ArticleView source={source} locale={locale} onClose={closeSource} /> : <ArticlePlaceholder />}
          </aside>
        )
      ) : (
        <Drawer>
          <Drawer.Backdrop isOpen={!!source} onOpenChange={(isOpen) => !isOpen && closeSource()}>
            <Drawer.Content placement="bottom">
              <Drawer.Dialog aria-label={t("panelTitle")} className="max-h-[80dvh] p-0">
                <Drawer.Handle />
                {source && <ArticleView source={source} locale={locale} onClose={closeSource} />}
              </Drawer.Dialog>
            </Drawer.Content>
          </Drawer.Backdrop>
        </Drawer>
      )}
    </div>
  );
}

function HistoryList({
  conversations,
  loaded,
  activeId,
  locale,
  onNew,
  onOpen,
  onDelete,
}: {
  conversations: Conversation[];
  loaded: boolean;
  activeId: string;
  locale: string;
  onNew: () => void;
  onOpen: (c: Conversation) => void;
  onDelete: (id: string) => void;
}) {
  const t = useTranslations("chat");
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="p-3">
        <Button fullWidth onPress={onNew}>
          <MessageSquarePlus className="size-4" aria-hidden />
          {t("newChat")}
        </Button>
      </div>
      <div className="px-4 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-muted">{t("history")}</div>
      <nav className="thin-scroll min-h-0 flex-1 overflow-y-auto px-2 pb-3" aria-label={t("history")}>
        {loaded && conversations.length === 0 && (
          <p className="px-2 py-3 text-xs leading-5 text-muted">{t("noHistory")}</p>
        )}
        <ul className="flex flex-col gap-0.5">
          {conversations.map((c) => (
            <HistoryItem
              key={c.id}
              conversation={c}
              active={c.id === activeId}
              locale={locale}
              onOpen={() => onOpen(c)}
              onDelete={() => onDelete(c.id)}
            />
          ))}
        </ul>
      </nav>
      <div className="border-t border-separator p-3">
        <Link
          href={`/${locale}/laws`}
          className="flex items-center gap-2 rounded-lg px-2 py-2 text-sm text-muted hover:bg-default hover:text-foreground"
        >
          <BookOpen className="size-4" aria-hidden />
          {t("browseLaws")}
        </Link>
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
  const date = new Intl.DateTimeFormat(locale === "ar" ? "ar-MA" : locale, { day: "numeric", month: "short" }).format(
    conversation.updatedAt
  );

  return (
    <li className="group relative">
      <button
        onClick={onOpen}
        aria-current={active ? "true" : undefined}
        className={cn(
          "flex w-full items-start gap-2 rounded-lg px-2 py-2 pe-10 text-start text-sm transition-colors",
          "focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-focus",
          active ? "bg-accent/10 text-foreground" : "text-muted hover:bg-default hover:text-foreground"
        )}
      >
        <MessagesSquare className={cn("mt-0.5 size-3.5 shrink-0", active && "text-accent")} aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="block truncate" dir="auto">
            {conversation.title || "…"}
          </span>
          <span className="block text-[11px] text-muted">{date}</span>
        </span>
      </button>
      <Button
        size="sm"
        variant={confirming ? "danger" : "ghost"}
        isIconOnly={!confirming}
        aria-label={confirming ? t("confirmDelete") : t("deleteChat")}
        onPress={() => (confirming ? onDelete() : setConfirming(true))}
        onBlur={() => setConfirming(false)}
        className={cn(
          "absolute end-1 top-1.5 h-7 min-w-7",
          !confirming && "opacity-0 focus-visible:opacity-100 group-hover:opacity-100 max-lg:opacity-100"
        )}
      >
        {confirming ? t("confirmDelete") : <Trash2 className="size-3.5" aria-hidden />}
      </Button>
    </li>
  );
}
