"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { BookOpenCheck, CircleAlert, FileText, Scale, Send, Sparkles } from "lucide-react";
import { api, lawUrl } from "@/lib/api";
import { streamSse } from "@/lib/sse";
import type { SearchHit } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface Message {
  role: "user" | "assistant";
  text: string;
  sources?: SearchHit[];
  cited?: number[];
  abstained?: boolean;
  rewritten?: string;
  disclaimer?: string;
  error?: boolean;
  streaming?: boolean;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function ChatPanel({ locale, initialQuestion }: { locale: string; initialQuestion: string }) {
  const t = useTranslations("chat");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const startedRef = useRef(false);

  const scrollToEnd = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, []);

  useEffect(scrollToEnd, [messages, scrollToEnd]);

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

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const response = await fetch(`${API_URL}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: trimmed }),
          signal: controller.signal,
        });
        if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);

        for await (const event of streamSse(response, controller.signal)) {
          const data = event.data ? JSON.parse(event.data) : {};
          if (event.event === "meta") {
            setMessages((prev) => patchLast(prev, { rewritten: data.rewritten, disclaimer: data.disclaimer }));
          } else if (event.event === "sources") {
            setMessages((prev) => patchLast(prev, { sources: data.sources }));
          } else if (event.event === "token") {
            setMessages((prev) => patchLast(prev, (m) => ({ text: m.text + data.t })));
          } else if (event.event === "done") {
            setMessages((prev) =>
              patchLast(prev, { abstained: data.abstained, cited: data.cited, streaming: false })
            );
          } else if (event.event === "error") {
            setMessages((prev) => patchLast(prev, { text: data.message, error: true, streaming: false }));
          }
        }
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          setMessages((prev) => patchLast(prev, { text: t("errorLlm"), error: true, streaming: false }));
        }
      } finally {
        setBusy(false);
        abortRef.current = null;
      }
    },
    [busy, t]
  );

  // Auto-ask when arriving with ?q= (from the hero search or a law page).
  useEffect(() => {
    if (initialQuestion && !startedRef.current) {
      startedRef.current = true;
      void ask(initialQuestion);
    }
  }, [initialQuestion, ask]);

  return (
    <div className="mx-auto flex h-[calc(100vh-8rem)] max-w-4xl flex-col px-4 py-6">
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-zellige-900">{t("title")}</h1>
        <p className="text-sm text-zellige-500">{t("subtitle")}</p>
      </div>

      <div className="thin-scroll flex-1 overflow-y-auto rounded-2xl border border-zellige-100 bg-white p-4">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-6 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-zellige-100 text-zellige-700">
              <Scale className="h-7 w-7" />
            </span>
            <p className="max-w-md text-zellige-600">{t("emptyState")}</p>
            <div className="flex max-w-xl flex-wrap justify-center gap-2">
              {t.raw("suggestions").map((suggestion: string) => (
                <button
                  key={suggestion}
                  onClick={() => void ask(suggestion)}
                  className="rounded-full border border-zellige-200 bg-sand-50 px-3.5 py-1.5 text-sm text-zellige-700 transition-colors hover:bg-zellige-50"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-col gap-4">
          {messages.map((message, index) => (
            <MessageBubble key={index} message={message} locale={locale} />
          ))}
          {busy && messages.at(-1)?.role === "user" && (
            <div className="flex items-center gap-2 text-sm text-zellige-500">
              <span className="flex gap-1">
                <i className="h-1.5 w-1.5 animate-blink rounded-full bg-zellige-500" />
                <i className="h-1.5 w-1.5 animate-blink rounded-full bg-zellige-500 [animation-delay:200ms]" />
                <i className="h-1.5 w-1.5 animate-blink rounded-full bg-zellige-500 [animation-delay:400ms]" />
              </span>
              {t("thinking")}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask(input);
        }}
        className="mt-4 flex gap-2"
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t("inputPlaceholder")}
          disabled={busy}
          className="h-12"
        />
        <Button type="submit" size="icon" className="h-12 w-12" disabled={busy || !input.trim()}>
          <Send className="h-4 w-4 rtl:-scale-x-100" />
        </Button>
      </form>
      <p className="mt-2 flex items-center gap-1.5 text-xs text-zellige-400">
        <CircleAlert className="h-3.5 w-3.5" />
        {t("disclaimer")}
      </p>
    </div>
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

function MessageBubble({ message, locale }: { message: Message; locale: string }) {
  const t = useTranslations("chat");
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="animate-fade-up flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-ee-md bg-zellige-700 px-4 py-3 text-white">
          {message.text}
        </div>
      </div>
    );
  }

  const citedSources = (message.cited ?? [])
    .map((index) => message.sources?.[index])
    .filter((hit): hit is SearchHit => Boolean(hit));

  return (
    <div className="animate-fade-up flex flex-col items-start gap-2">
      <div
        className={cn(
          "max-w-[90%] rounded-2xl rounded-es-md px-4 py-3 leading-8",
          message.error ? "bg-red-50 text-red-800" : "bg-sand-50 text-zellige-950"
        )}
        dir="auto"
      >
        {message.text || "…"}
        {message.streaming && <span className="ms-1 inline-block h-4 w-1.5 animate-blink bg-zellige-400 align-middle" />}
      </div>

      {message.rewritten && message.rewritten !== message.text && !message.error && (
        <p className="flex items-center gap-1 text-xs text-zellige-400" dir="auto">
          <Sparkles className="h-3 w-3" />
          {t("rewritten")}: {message.rewritten}
        </p>
      )}

      {message.abstained && (
        <p className="text-xs font-medium text-sand-700">{t("abstained")}</p>
      )}

      {/* Sources: all retrieved passages, with cited ones highlighted */}
      {message.sources && message.sources.length > 0 && (
        <div className="w-full">
          <p className="mb-2 flex items-center gap-1.5 text-xs font-bold text-zellige-600">
            <BookOpenCheck className="h-3.5 w-3.5" />
            {t("sources")}
          </p>
          <div className="flex flex-col gap-1.5">
            {message.sources.map((hit, index) => {
              const cited = (message.cited ?? []).includes(index);
              return (
                <a
                  key={`${hit.law_slug}-${hit.article_number}-${index}`}
                  href={lawUrl(locale, hit.law_slug, hit.article_number)}
                  target="_blank"
                  rel="noreferrer"
                  className={cn(
                    "group flex items-start gap-2.5 rounded-xl border p-2.5 text-xs transition-colors",
                    cited
                      ? "border-zellige-300 bg-zellige-50 hover:bg-zellige-100"
                      : "border-zellige-100 bg-white hover:bg-zellige-50"
                  )}
                  dir="auto"
                >
                  <span
                    className={cn(
                      "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md font-bold",
                      cited ? "bg-zellige-700 text-white" : "bg-zellige-100 text-zellige-600"
                    )}
                  >
                    {index + 1}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-1.5">
                      <FileText className="h-3 w-3 text-zellige-400" />
                      <span className="font-bold text-zellige-800">{hit.law_title}</span>
                      <Badge variant={cited ? "domain" : "outline"}>
                        {locale === "fr" ? `Art. ${hit.article_number}` : `المادة ${hit.article_number}`}
                      </Badge>
                    </span>
                    <span className="mt-1 line-clamp-2 block text-zellige-500">{hit.text}</span>
                  </span>
                </a>
              );
            })}
          </div>
        </div>
      )}

      {message.disclaimer && !message.error && (
        <p className="text-[11px] text-zellige-400" dir="auto">
          {message.disclaimer}
        </p>
      )}
    </div>
  );
}
