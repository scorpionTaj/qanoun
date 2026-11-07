"use client";

import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Alert, Button, Chip, Disclosure, Spinner, TextArea, Tooltip } from "@heroui/react";
import { ArrowUp, BookOpenCheck, Check, Copy, History, Library, Scale, Sparkles, Square } from "lucide-react";
import type { Message } from "@/lib/conversations";
import { loadChoice } from "@/lib/settings";
import { streamSse } from "@/lib/sse";
import type { SearchHit } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ScopeSelect, type Scope } from "./scope-select";
import { AiSourceSelect } from "./ai-source-select";

const ERROR_CODES = [
  "unreachable", "auth", "rate_limit", "unavailable", "model", "empty", "interrupted", "retrieval", "network",
];
const STAGES = ["rewriting", "searching", "answering"] as const;

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type OpenSource = (hit: SearchHit, citation: number) => void;

export function ChatPanel({
  locale,
  initialMessages,
  initialQuestion,
  onChange,
  onOpenSource,
  activeArticleId,
  onShowHistory,
  scope,
  onScopeChange,
}: {
  scope: Scope;
  onScopeChange: (scope: Scope) => void;
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

  // Latest messages for building the follow-up context inside ask().
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  // Report every change up; the workspace persists finished turns.
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  useEffect(() => onChangeRef.current(messages), [messages]);

  // Follow the answer while it streams, only if the reader is already near the bottom.
  useEffect(() => {
    const el = scrollRef.current;
    if (el && el.scrollHeight - el.scrollTop - el.clientHeight < 160) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const ask = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || busy) return;
      const history = recentTurns(messagesRef.current);
      setBusy(true);
      setInput("");
      setMessages((prev) => [
        ...prev,
        { role: "user", text: trimmed, scopeLabel: scope.group || scope.domain ? scope.label : undefined },
        { role: "assistant", text: "", streaming: true, stage: "searching" },
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
          body: JSON.stringify({
            question: trimmed,
            provider: provider || undefined,
            model,
            domain: scope.domain,
            group: scope.group,
            history,
          }),
          signal: controller.signal,
        });
        if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);

        for await (const event of streamSse(response, controller.signal)) {
          const data = event.data ? JSON.parse(event.data) : {};
          if (event.event === "status") {
            if (STAGES.includes(data.stage)) setMessages((prev) => patchLast(prev, { stage: data.stage }));
          } else if (event.event === "meta") {
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
            const ms = data.timings ? Object.values(data.timings as Record<string, number>).reduce((a, b) => a + b, 0) : 0;
            setMessages((prev) =>
              patchLast(prev, (m) => ({
                text: data.text ?? m.text,
                abstained: data.abstained,
                cited: data.cited,
                streaming: false,
                stage: undefined,
                seconds: ms ? Math.round(ms / 100) / 10 : undefined,
              }))
            );
          } else if (event.event === "error") {
            // Translated, actionable message; the raw provider error stays one click away.
            const code = ERROR_CODES.includes(data.code) ? data.code : "error";
            setMessages((prev) =>
              patchLast(prev, { text: t(`errors.${code}`), errorDetail: data.message, error: true, streaming: false, stage: undefined })
            );
          }
        }
        // Closed without `done` or `error` (API restarted, proxy timeout…): never leave the
        // bubble spinning or a partial answer looking complete.
        setMessages((prev) =>
          prev.at(-1)?.streaming
            ? patchLast(prev, { text: t("errors.interrupted"), error: true, streaming: false, stage: undefined })
            : prev
        );
      } catch (error) {
        if ((error as Error).name === "AbortError") {
          setMessages((prev) =>
            patchLast(prev, (m) =>
              m.text
                ? { streaming: false, stopped: true, stage: undefined }
                : { text: t("stoppedEmpty"), streaming: false, error: true, stage: undefined }
            )
          );
        } else {
          setMessages((prev) =>
            patchLast(prev, { text: t("errors.network"), errorDetail: String(error), error: true, streaming: false, stage: undefined })
          );
        }
      } finally {
        setBusy(false);
        abortRef.current = null;
        inputRef.current?.focus();
      }
    },
    [busy, t, scope]
  );

  // Auto-ask when arriving with ?q= (from the home search or a law page).
  useEffect(() => {
    if (initialQuestion && !startedRef.current) {
      startedRef.current = true;
      void ask(initialQuestion);
    }
  }, [initialQuestion, ask]);

  return (
    <section className="flex h-full min-h-0 min-w-0 flex-col" aria-label={t("title")}>
      <div className="flex items-center gap-2 border-b border-separator px-4 py-3">
        <Button isIconOnly size="sm" variant="ghost" aria-label={t("history")} onPress={onShowHistory} className="lg:hidden">
          <History className="size-4" aria-hidden />
        </Button>
        <div className="min-w-0">
          <h1 className="truncate text-base font-bold">{t("title")}</h1>
          <p className="truncate text-xs text-muted">{t("subtitle")}</p>
        </div>
      </div>

      <div ref={scrollRef} className="thin-scroll min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
          {messages.length === 0 && (
            <div className="flex flex-col items-center gap-6 py-10 text-center">
              <span className="flex size-14 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
                <Scale className="size-7" aria-hidden />
              </span>
              <p className="max-w-md text-pretty leading-7 text-muted">{t("emptyState")}</p>
              <div className="grid w-full max-w-xl gap-2 sm:grid-cols-2">
                {(t.raw("suggestions") as string[]).map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => void ask(suggestion)}
                    dir="auto"
                    className="rounded-[var(--radius)] border border-separator bg-surface px-4 py-3 text-start text-sm transition-colors hover:border-accent/40 hover:bg-accent/5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
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

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask(input);
        }}
        className="border-t border-separator bg-background/80 px-4 py-3 backdrop-blur-md"
      >
        {/* Where the answer comes from (laws) and who writes it (AI). */}
        <div className="mx-auto mb-2 flex max-w-3xl flex-wrap items-center gap-x-3 gap-y-1.5">
          <span className="flex min-w-0 items-center gap-1.5">
            <span className="shrink-0 text-xs text-muted">{t("scopeLabel")}</span>
            <ScopeSelect locale={locale} scope={scope} onChange={onScopeChange} />
          </span>
          <span className="flex min-w-0 items-center gap-1.5">
            <span className="shrink-0 text-xs text-muted">{t("aiLabel")}</span>
            <AiSourceSelect />
          </span>
        </div>
        <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-[1.25rem] border border-border bg-surface p-1.5 shadow-sm focus-within:border-accent">
          <TextArea
            ref={inputRef}
            aria-label={t("inputPlaceholder")}
            name="question"
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              // Enter sends, Shift+Enter adds a line; never send mid IME composition.
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                void ask(input);
              }
            }}
            placeholder={t("inputPlaceholder")}
            dir="auto"
            autoComplete="off"
            className="max-h-40 min-h-10 flex-1 resize-none border-0 bg-transparent shadow-none [field-sizing:content] focus:ring-0"
          />
          {busy ? (
            <Button isIconOnly variant="secondary" aria-label={t("stop")} onPress={() => abortRef.current?.abort()} className="rounded-full">
              <Square className="size-3.5 fill-current" aria-hidden />
            </Button>
          ) : (
            <Button type="submit" isIconOnly aria-label={t("send")} isDisabled={!input.trim()} className="rounded-full">
              <ArrowUp className="size-4" aria-hidden />
            </Button>
          )}
        </div>
        <p className="mx-auto mt-1.5 max-w-3xl text-center text-[11px] text-muted">{t("disclaimer")}</p>
      </form>
    </section>
  );
}

/** The last few finished exchanges, oldest first, for follow-up questions ("and for
 * women?"). Errors and stopped answers are left out; long answers are trimmed. */
function recentTurns(messages: Message[], maxTurns = 6): { role: "user" | "assistant"; text: string }[] {
  const turns: { role: "user" | "assistant"; text: string }[] = [];
  for (let i = 0; i + 1 < messages.length; i += 2) {
    const [question, answer] = [messages[i], messages[i + 1]];
    if (question.role !== "user" || answer.role !== "assistant") continue;
    if (answer.error || answer.streaming || answer.stopped || !answer.text) continue;
    turns.push({ role: "user", text: question.text.slice(0, 2000) });
    turns.push({ role: "assistant", text: answer.text.slice(0, 2000) });
  }
  return turns.slice(-maxTurns);
}

function patchLast(messages: Message[], patch: Partial<Message> | ((m: Message) => Partial<Message>)): Message[] {
  if (!messages.length) return messages;
  const last = messages.at(-1)!;
  const resolved = typeof patch === "function" ? patch(last) : patch;
  return [...messages.slice(0, -1), { ...last, ...resolved }];
}

/** Answer text with every [n] turned into a button that opens source n beside the answer. */
function AnswerText({ message, onOpenSource }: { message: Message; onOpenSource: OpenSource }) {
  return (
    <>
      {message.text.split(/(\[\d+\])/g).map((part, i) => {
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
            className="mx-0.5 inline-flex h-5 min-w-5 -translate-y-0.5 items-center justify-center rounded-md bg-accent/12 px-1 align-middle text-[11px] font-bold text-accent transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-2 focus-visible:outline-focus"
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

  if (message.role === "user") {
    return (
      <div className="animate-fade-up flex flex-col items-end gap-1">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-[1.25rem] rounded-ee-md bg-accent px-4 py-2.5 text-accent-foreground" dir="auto">
          {message.text}
        </div>
        {message.scopeLabel && (
          <span className="flex items-center gap-1 text-[11px] text-muted" dir="auto">
            <Library className="size-3" aria-hidden />
            {t("scopeIn", { name: message.scopeLabel })}
          </span>
        )}
      </div>
    );
  }

  if (message.error) {
    return (
      <Alert status="danger" className="animate-fade-up">
        <Alert.Indicator />
        <Alert.Content>
          <Alert.Title>{message.text}</Alert.Title>
          {message.errorDetail && (
            <Alert.Description>
              <details className="text-xs">
                <summary className="cursor-pointer select-none">{t("errorDetails")}</summary>
                <p className="mt-1 break-words font-mono" dir="ltr">
                  {message.errorDetail}
                </p>
              </details>
            </Alert.Description>
          )}
        </Alert.Content>
      </Alert>
    );
  }

  const cited = message.cited ?? [];
  const done = !message.streaming;
  const copy = async () => {
    await navigator.clipboard.writeText(message.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };
  const stageLabel = {
    rewriting: t("stageRewriting"),
    searching: t("stageSearching"),
    answering: t("stageAnswering"),
  };

  return (
    <article className="animate-fade-up flex flex-col gap-2">
      <div className="rounded-[1.25rem] rounded-es-md border border-separator bg-surface px-4 py-3 leading-8" dir="auto">
        {message.text ? (
          <span className="whitespace-pre-wrap">
            <AnswerText message={message} onOpenSource={onOpenSource} />
            {message.streaming && <span className="ms-1 inline-block h-4 w-1.5 animate-blink bg-accent align-middle" aria-hidden />}
          </span>
        ) : (
          <span className="flex items-center gap-2.5 text-sm text-muted" role="status">
            <Spinner size="sm" />
            {stageLabel[message.stage ?? "searching"]}
          </span>
        )}
      </div>

      {message.stopped && <p className="text-xs font-medium text-saffron-700 dark:text-saffron-300">{t("stopped")}</p>}
      {message.abstained && <p className="text-xs font-medium text-saffron-700 dark:text-saffron-300">{t("abstained")}</p>}

      {done && message.text && (
        <div className="flex flex-wrap items-center gap-1 text-xs text-muted">
          <Tooltip delay={400}>
            <Button size="sm" variant="ghost" onPress={() => void copy()} aria-label={t("copyAnswer")} className="h-7 px-2">
              {copied ? <Check className="size-3.5" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
              {copied ? t("copied") : t("copyAnswer")}
            </Button>
            <Tooltip.Content>{t("copyAnswer")}</Tooltip.Content>
          </Tooltip>
          {message.answeredBy && (
            <span dir="ltr" translate="no" className="px-1">
              {message.answeredBy}
              {message.seconds != null && ` · ${t("answeredIn", { seconds: message.seconds })}`}
            </span>
          )}
        </div>
      )}

      {message.rewritten && (
        <p className="flex items-center gap-1.5 text-xs text-muted" dir="auto">
          <Sparkles className="size-3 shrink-0 text-saffron-500" aria-hidden />
          {t("rewritten")}: {message.rewritten}
        </p>
      )}

      {done && message.sources && message.sources.length > 0 && (
        <Disclosure>
          <Disclosure.Heading>
            <Disclosure.Trigger className="flex items-center gap-1.5 rounded-md px-1 py-1 text-xs font-semibold text-muted hover:text-foreground">
              <BookOpenCheck className="size-3.5" aria-hidden />
              {t("sources")} ({message.sources.length})
              <Disclosure.Indicator />
            </Disclosure.Trigger>
          </Disclosure.Heading>
          <Disclosure.Content>
            <Disclosure.Body>
              <ol className="mt-1 flex flex-col gap-1.5">
                {message.sources.map((hit, index) => {
                  const isCited = cited.includes(index);
                  const title = locale !== "ar" && hit.law_title_fr ? hit.law_title_fr : hit.law_title;
                  return (
                    <li key={`${hit.article_id}-${index}`}>
                      <button
                        onClick={() => onOpenSource(hit, index + 1)}
                        dir="auto"
                        className={cn(
                          "flex w-full items-start gap-2.5 rounded-[var(--radius)] border bg-surface p-2.5 text-start text-xs transition-colors hover:bg-default",
                          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                          isCited ? "border-accent/40" : "border-separator",
                          activeArticleId === hit.article_id && "outline-2 outline-saffron-500"
                        )}
                      >
                        <Chip size="sm" color={isCited ? "accent" : "default"} variant={isCited ? "primary" : "secondary"} className="min-w-6 justify-center font-bold">
                          {index + 1}
                        </Chip>
                        <span className="min-w-0 flex-1">
                          <span className="block font-semibold">
                            {title} · {locale === "ar" ? `المادة ${hit.article_number}` : `Art. ${hit.article_number}`}
                          </span>
                          <span className="mt-0.5 line-clamp-2 block text-muted">{hit.text}</span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ol>
            </Disclosure.Body>
          </Disclosure.Content>
        </Disclosure>
      )}

      {message.disclaimer && done && <p className="text-[11px] text-muted" dir="auto">{message.disclaimer}</p>}
    </article>
  );
}
