"use client";

import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import {
  BookOpenCheck,
  Check,
  ChevronDown,
  CircleAlert,
  Copy,
  History,
  Scale,
  Search,
  Send,
  Sparkles,
  Square,
} from "lucide-react";
import type { Message } from "@/lib/conversations";
import { loadChoice } from "@/lib/settings";
import { streamSse } from "@/lib/sse";
import type { SearchHit } from "@/lib/types";
import { cn } from "@/lib/utils";

const ERROR_CODES = [
  "unreachable", "auth", "rate_limit", "unavailable", "model", "empty", "interrupted", "retrieval", "network",
];

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface OpenSource {
  (hit: SearchHit, citation: number): void;
}

export function ChatPanel({
  locale,
  initialMessages,
  initialQuestion,
  onChange,
  onOpenSource,
  activeArticleId,
  onShowHistory,
}: {
  locale: string;
  initialMessages: Message[];
  initialQuestion: string;
  onChange: (messages: Message[]) => void;
  onOpenSource: OpenSource;
  activeArticleId: number | null;
  onShowHistory: () => void;
}) {
  const t = useTranslations("chat");
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const startedRef = useRef(false);

  // Report every change up; the workspace persists finished turns.
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  useEffect(() => {
    onChangeRef.current(messages);
  }, [messages]);

  // Follow the answer while it streams, but only if the reader is already near the bottom.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 160) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const ask = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || busy) return;
      setBusy(true);
      setInput("");
      setMessages((prev) => [
        ...prev,
        { role: "user", text: trimmed },
        { role: "assistant", text: "", streaming: true },
      ]);
      requestAnimationFrame(() => {
        const el = scrollRef.current;
        if (el) el.scrollTop = el.scrollHeight;
      });

      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const { provider, model } = loadChoice();
        const response = await fetch(`${API_URL}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: trimmed, provider: provider || undefined, model }),
          signal: controller.signal,
        });
        if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);

        for await (const event of streamSse(response, controller.signal)) {
          const data = event.data ? JSON.parse(event.data) : {};
          if (event.event === "meta") {
            // The server echoes the question when nothing was rewritten (MSA, French…).
            const rewritten = data.rewritten && data.rewritten !== trimmed ? data.rewritten : undefined;
            setMessages((prev) => patchLast(prev, { rewritten, disclaimer: data.disclaimer }));
          } else if (event.event === "sources") {
            setMessages((prev) => patchLast(prev, { sources: data.sources }));
          } else if (event.event === "model") {
            setMessages((prev) => patchLast(prev, { answeredBy: `${data.provider_label} · ${data.model}` }));
          } else if (event.event === "token") {
            setMessages((prev) => patchLast(prev, (m) => ({ text: m.text + data.t })));
          } else if (event.event === "done") {
            // The server's final text wins: it replaces a streamed "NO_ANSWER" with the
            // abstention message and drops <think> blocks from reasoning models.
            setMessages((prev) =>
              patchLast(prev, (m) => ({
                text: data.text ?? m.text,
                abstained: data.abstained,
                cited: data.cited,
                streaming: false,
              }))
            );
          } else if (event.event === "error") {
            // Translated, actionable message; the raw provider error stays one click away.
            const code = ERROR_CODES.includes(data.code) ? data.code : "error";
            setMessages((prev) =>
              patchLast(prev, { text: t(`errors.${code}`), errorDetail: data.message, error: true, streaming: false })
            );
          }
        }
        // The stream closed without `done` or `error` (API restarted, proxy timeout…):
        // never leave the bubble spinning or a partial answer looking complete.
        setMessages((prev) =>
          prev.at(-1)?.streaming
            ? patchLast(prev, { text: t("errors.interrupted"), error: true, streaming: false })
            : prev
        );
      } catch (error) {
        if ((error as Error).name === "AbortError") {
          setMessages((prev) =>
            patchLast(prev, (m) =>
              m.text
                ? { streaming: false, stopped: true }
                : { text: t("stoppedEmpty"), streaming: false, error: true }
            )
          );
        } else {
          setMessages((prev) =>
            patchLast(prev, { text: t("errors.network"), errorDetail: String(error), error: true, streaming: false })
          );
        }
      } finally {
        setBusy(false);
        abortRef.current = null;
        inputRef.current?.focus();
      }
    },
    [busy, t]
  );

  const stop = () => abortRef.current?.abort();

  // Auto-ask when arriving with ?q= (from the home search or a law page).
  useEffect(() => {
    if (initialQuestion && !startedRef.current) {
      startedRef.current = true;
      void ask(initialQuestion);
    }
  }, [initialQuestion, ask]);

  const submit = () => void ask(input);

  return (
    <section className="flex h-full min-w-0 flex-col" aria-label={t("title")}>
      {/* Column header */}
      <div className="flex items-center gap-2 border-b border-zellige-100 px-4 py-3 dark:border-zellige-800">
        <button
          onClick={onShowHistory}
          aria-label={t("history")}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-zellige-600 hover:bg-zellige-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zellige-500 dark:text-zellige-300 dark:hover:bg-zellige-800 lg:hidden"
        >
          <History className="h-4 w-4" aria-hidden />
        </button>
        <div className="min-w-0">
          <h1 className="truncate text-base font-bold text-zellige-900 dark:text-white">{t("title")}</h1>
          <p className="truncate text-xs text-zellige-500 dark:text-zellige-400">{t("subtitle")}</p>
        </div>
      </div>

      {/* Conversation */}
      <div ref={scrollRef} className="thin-scroll flex-1 overflow-y-auto overscroll-contain" aria-live="polite">
        <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
          {messages.length === 0 && (
            <div className="flex flex-col items-center gap-6 py-10 text-center">
              <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-zellige-100 text-zellige-700 dark:bg-zellige-800/80 dark:text-zellige-200">
                <Scale className="h-7 w-7" aria-hidden />
              </span>
              <p className="max-w-md leading-7 text-zellige-600 dark:text-zellige-300">{t("emptyState")}</p>
              <div className="grid w-full max-w-xl gap-2 sm:grid-cols-2">
                {(t.raw("suggestions") as string[]).map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => void ask(suggestion)}
                    dir="auto"
                    className="rounded-xl border border-zellige-200 bg-white px-4 py-3 text-start text-sm text-zellige-700 transition-colors hover:border-zellige-300 hover:bg-zellige-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zellige-500 dark:border-zellige-700 dark:bg-[#12201a] dark:text-zellige-200 dark:hover:bg-zellige-800/60"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message, index) => (
            <MessageBubble
              key={index}
              message={message}
              locale={locale}
              onOpenSource={onOpenSource}
              activeArticleId={activeArticleId}
            />
          ))}
        </div>
      </div>

      {/* Composer */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="border-t border-zellige-100 bg-sand-50/80 px-4 py-3 dark:border-zellige-800 dark:bg-[#0b1310]/80"
      >
        <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-zellige-200 bg-white p-2 shadow-sm focus-within:ring-2 focus-within:ring-zellige-500 dark:border-zellige-700 dark:bg-[#0f1b16]">
          <label htmlFor="chat-input" className="sr-only">
            {t("inputPlaceholder")}
          </label>
          <textarea
            id="chat-input"
            ref={inputRef}
            name="question"
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              // Enter sends, Shift+Enter adds a line; never send mid IME composition.
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={t("inputPlaceholder")}
            dir="auto"
            autoComplete="off"
            className="max-h-40 min-h-[2.5rem] flex-1 resize-none bg-transparent px-2 py-2 text-[0.95rem] leading-6 text-zellige-950 outline-none placeholder:text-zellige-400 dark:text-zellige-100 dark:placeholder:text-zellige-500 [field-sizing:content]"
          />
          {busy ? (
            <button
              type="button"
              onClick={stop}
              aria-label={t("stop")}
              title={t("stop")}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-zellige-900 text-white transition-colors hover:bg-zellige-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zellige-500 dark:bg-zellige-200 dark:text-zellige-950"
            >
              <Square className="h-3.5 w-3.5 fill-current" aria-hidden />
            </button>
          ) : (
            <button
              type="submit"
              aria-label={t("send")}
              disabled={!input.trim()}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-zellige-700 text-white transition-colors hover:bg-zellige-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zellige-500 disabled:opacity-40 dark:bg-zellige-500 dark:text-zellige-950"
            >
              <Send className="h-4 w-4 rtl:-scale-x-100" aria-hidden />
            </button>
          )}
        </div>
        <p className="mx-auto mt-1.5 flex max-w-3xl items-center gap-1.5 text-[11px] text-zellige-400 dark:text-zellige-500">
          <CircleAlert className="h-3 w-3" aria-hidden />
          {t("disclaimer")}
        </p>
      </form>
    </section>
  );
}

function patchLast(
  messages: Message[],
  patch: Partial<Message> | ((m: Message) => Partial<Message>)
): Message[] {
  if (!messages.length) return messages;
  const last = messages.at(-1)!;
  const resolved = typeof patch === "function" ? patch(last) : patch;
  return [...messages.slice(0, -1), { ...last, ...resolved }];
}

/** Answer text with every [n] turned into a button that opens source n beside the answer. */
function AnswerText({
  message,
  onOpenSource,
}: {
  message: Message;
  onOpenSource: OpenSource;
}) {
  const parts = message.text.split(/(\[\d+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const match = /^\[(\d+)\]$/.exec(part);
        const hit = match ? message.sources?.[Number(match[1]) - 1] : undefined;
        if (!match || !hit || message.streaming) return <Fragment key={i}>{part}</Fragment>;
        const n = Number(match[1]);
        return (
          <button
            key={i}
            type="button"
            onClick={() => onOpenSource(hit, n)}
            title={`${hit.law_title} — ${hit.article_number}`}
            className="mx-0.5 inline-flex h-5 min-w-5 -translate-y-0.5 items-center justify-center rounded-md bg-zellige-100 px-1 align-middle text-[11px] font-bold text-zellige-800 transition-colors hover:bg-zellige-700 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zellige-500 dark:bg-zellige-800 dark:text-zellige-100 dark:hover:bg-zellige-500 dark:hover:text-zellige-950"
          >
            {n}
          </button>
        );
      })}
    </>
  );
}

function MessageBubble({
  message,
  locale,
  onOpenSource,
  activeArticleId,
}: {
  message: Message;
  locale: string;
  onOpenSource: OpenSource;
  activeArticleId: number | null;
}) {
  const t = useTranslations("chat");
  const [copied, setCopied] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);

  if (message.role === "user") {
    return (
      <div className="animate-fade-up flex justify-end">
        <div
          className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-ee-md bg-zellige-700 px-4 py-2.5 text-white dark:bg-zellige-600"
          dir="auto"
        >
          {message.text}
        </div>
      </div>
    );
  }

  const cited = message.cited ?? [];
  const copyAnswer = async () => {
    await navigator.clipboard.writeText(message.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };
  const done = !message.streaming;

  return (
    <article className="animate-fade-up flex flex-col gap-2">
      <div
        className={cn(
          "relative rounded-2xl px-4 py-3 leading-8",
          message.error
            ? "border border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-200"
            : "border border-zellige-100 bg-white text-zellige-950 dark:border-zellige-800 dark:bg-[#12201a] dark:text-zellige-100"
        )}
        dir="auto"
      >
        {message.text ? (
          <span className="whitespace-pre-wrap">
            <AnswerText message={message} onOpenSource={onOpenSource} />
          </span>
        ) : (
          <span className="flex items-center gap-2 text-sm text-zellige-500 dark:text-zellige-400">
            <Search className="h-4 w-4 animate-pulse" aria-hidden />
            {t("searchingSources")}
          </span>
        )}
        {message.streaming && message.text && (
          <span className="ms-1 inline-block h-4 w-1.5 animate-blink bg-zellige-400 align-middle" aria-hidden />
        )}
      </div>

      {message.stopped && <p className="text-xs font-medium text-sand-700 dark:text-sand-300">{t("stopped")}</p>}
      {message.abstained && <p className="text-xs font-medium text-sand-700 dark:text-sand-300">{t("abstained")}</p>}

      {message.error && message.errorDetail && (
        <details className="text-[11px] text-zellige-400 dark:text-zellige-500">
          <summary className="cursor-pointer select-none">{t("errorDetails")}</summary>
          <p className="mt-1 break-words font-mono" dir="ltr">
            {message.errorDetail}
          </p>
        </details>
      )}

      {/* Toolbar: copy · sources · model · rewrite note */}
      {done && !message.error && message.text && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zellige-500 dark:text-zellige-400">
          <button
            onClick={() => void copyAnswer()}
            className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 hover:bg-zellige-100 hover:text-zellige-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zellige-500 dark:hover:bg-zellige-800 dark:hover:text-zellige-100"
          >
            {copied ? <Check className="h-3.5 w-3.5" aria-hidden /> : <Copy className="h-3.5 w-3.5" aria-hidden />}
            {copied ? t("copied") : t("copyAnswer")}
          </button>
          {message.sources && message.sources.length > 0 && (
            <button
              onClick={() => setSourcesOpen(!sourcesOpen)}
              aria-expanded={sourcesOpen}
              className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 hover:bg-zellige-100 hover:text-zellige-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zellige-500 dark:hover:bg-zellige-800 dark:hover:text-zellige-100"
            >
              <BookOpenCheck className="h-3.5 w-3.5" aria-hidden />
              {t("sources")} ({message.sources.length})
              <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", sourcesOpen && "rotate-180")} aria-hidden />
            </button>
          )}
          {message.answeredBy && (
            <span dir="ltr" translate="no" className="text-zellige-400 dark:text-zellige-500">
              {message.answeredBy}
            </span>
          )}
        </div>
      )}

      {message.rewritten && !message.error && (
        <p className="flex items-center gap-1 text-xs text-zellige-400 dark:text-zellige-500" dir="auto">
          <Sparkles className="h-3 w-3 shrink-0" aria-hidden />
          {t("rewritten")}: {message.rewritten}
        </p>
      )}

      {done && sourcesOpen && message.sources && (
        <ol className="flex flex-col gap-1.5">
          {message.sources.map((hit, index) => {
            const isCited = cited.includes(index);
            const title = locale !== "ar" && hit.law_title_fr ? hit.law_title_fr : hit.law_title;
            return (
              <li key={`${hit.article_id}-${index}`}>
                <button
                  onClick={() => onOpenSource(hit, index + 1)}
                  dir="auto"
                  className={cn(
                    "flex w-full items-start gap-2.5 rounded-xl border p-2.5 text-start text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zellige-500",
                    "border-zellige-100 bg-white hover:bg-zellige-50 dark:border-zellige-800 dark:bg-[#12201a] dark:hover:bg-zellige-800/40",
                    isCited && "border-zellige-300 dark:border-zellige-600",
                    activeArticleId === hit.article_id && "ring-2 ring-sand-400 dark:ring-sand-500"
                  )}
                >
                  <span
                    className={cn(
                      "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md font-bold",
                      isCited
                        ? "bg-zellige-700 text-white dark:bg-zellige-500 dark:text-zellige-950"
                        : "bg-zellige-100 text-zellige-600 dark:bg-zellige-800 dark:text-zellige-300"
                    )}
                  >
                    {index + 1}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block font-bold text-zellige-800 dark:text-zellige-100">
                      {title} · {locale === "ar" ? `المادة ${hit.article_number}` : `Art. ${hit.article_number}`}
                    </span>
                    <span className="mt-0.5 line-clamp-2 block text-zellige-500 dark:text-zellige-400">{hit.text}</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      )}

      {message.disclaimer && done && !message.error && (
        <p className="text-[11px] text-zellige-400 dark:text-zellige-500" dir="auto">
          {message.disclaimer}
        </p>
      )}
    </article>
  );
}
