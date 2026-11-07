"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";
import { CheckCircle2, CircleAlert, KeyRound, Loader2, Settings, X, Zap } from "lucide-react";
import {
  llmApi,
  loadChoice,
  saveChoice,
  type LlmChoice,
  type ProviderInfo,
  type TestResult,
} from "@/lib/settings";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export function SettingsDialog() {
  const t = useTranslations("settings");
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [providers, setProviders] = useState<ProviderInfo[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [selected, setSelected] = useState<string>(""); // provider shown in the form
  const [model, setModel] = useState("");
  const [models, setModels] = useState<string[] | null>(null);
  const [modelsError, setModelsError] = useState(false);
  const [test, setTest] = useState<TestResult | "running" | null>(null);
  const [saved, setSaved] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => setMounted(true), []);

  // Open: read the saved choice and the server's provider list.
  useEffect(() => {
    if (!open) return;
    const choice = loadChoice();
    setSaved(false);
    setTest(null);
    setLoadError(false);
    llmApi
      .providers()
      .then((data) => {
        setProviders(data.providers);
        const keep = data.providers.find((p) => p.id === choice.provider && p.configured);
        setSelected(keep ? keep.id : data.default);
        setModel(keep ? choice.model : "");
      })
      .catch(() => setLoadError(true));
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    dialogRef.current?.focus();
    return () => {
      window.removeEventListener("keydown", onKey);
      triggerRef.current?.focus();
    };
  }, [open]);

  const current = providers?.find((p) => p.id === selected);

  // Cloud providers: load their live model list (the recommended one comes first).
  useEffect(() => {
    setModels(null);
    setModelsError(false);
    if (!current?.configured || current.local) return;
    llmApi
      .models(current.id)
      .then((data) => setModels(data.models))
      .catch(() => setModelsError(true));
  }, [current?.id, current?.configured, current?.local]);

  const choose = (provider: ProviderInfo) => {
    setSelected(provider.id);
    setModel("");
    setTest(null);
  };

  const choice: LlmChoice = { provider: selected, model };

  const runTest = async () => {
    setTest("running");
    try {
      setTest(await llmApi.test(choice));
    } catch {
      setTest({ ok: false, provider: selected, code: "network" });
    }
  };

  const save = () => {
    if (!current?.configured) return;
    saveChoice(choice);
    setSaved(true);
    setTimeout(() => setOpen(false), 600);
  };

  const dialog = open ? (
    <div
      className="fixed inset-0 z-50 overflow-y-auto overscroll-contain bg-black/50 p-4 backdrop-blur-sm"
      onClick={(e) => e.target === e.currentTarget && setOpen(false)}
    >
      <div
        ref={dialogRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        className="mx-auto mt-[8vh] w-full max-w-md rounded-2xl border border-zellige-100 bg-white p-5 shadow-2xl outline-none dark:border-zellige-800 dark:bg-[#12201a]"
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 id="settings-title" className="text-base font-bold text-zellige-900 dark:text-white">
            {t("title")}
          </h2>
          <button
            onClick={() => setOpen(false)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-zellige-500 hover:bg-zellige-100 focus-visible:ring-2 focus-visible:ring-zellige-500 dark:hover:bg-zellige-800"
            aria-label={t("close")}
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        <p className="mb-4 text-xs leading-5 text-zellige-600 dark:text-zellige-300">{t("intro")}</p>

        {loadError && (
          <p role="alert" className="rounded-xl bg-red-50 p-3 text-xs text-red-800 dark:bg-red-950/60 dark:text-red-300">
            {t("loadError")}
          </p>
        )}
        {!providers && !loadError && (
          <Loader2 className="mx-auto my-6 h-5 w-5 animate-spin text-zellige-400" aria-label={t("testing")} />
        )}

        {providers && (
          <>
            <div className="mb-1.5 text-xs font-semibold text-zellige-700 dark:text-zellige-200" id="provider-label">
              {t("provider")}
            </div>
            <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-labelledby="provider-label">
              {providers.map((p) => {
                const active = p.id === selected;
                return (
                  <button
                    key={p.id}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    onClick={() => choose(p)}
                    className={cn(
                      "flex flex-col items-start gap-0.5 rounded-xl border px-3 py-2 text-start text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zellige-500",
                      active
                        ? "border-zellige-600 bg-zellige-700 text-white dark:bg-zellige-600"
                        : "border-zellige-200 text-zellige-700 hover:bg-zellige-50 dark:border-zellige-700 dark:text-zellige-200 dark:hover:bg-zellige-800/60"
                    )}
                  >
                    <span className="font-semibold">{p.label}</span>
                    <span
                      className={cn(
                        "flex items-center gap-1 text-[11px]",
                        active ? "text-zellige-100" : p.configured ? "text-zellige-500" : "text-sand-700 dark:text-sand-300"
                      )}
                    >
                      {p.configured ? (
                        <CheckCircle2 className="h-3 w-3" aria-hidden />
                      ) : (
                        <KeyRound className="h-3 w-3" aria-hidden />
                      )}
                      {p.configured ? t("ready") : t("needsKey")}
                    </span>
                  </button>
                );
              })}
            </div>

            {current && !current.configured && (
              <div className="mt-3 rounded-xl border border-sand-200 bg-sand-50 p-3 text-xs leading-5 text-sand-900 dark:border-sand-800 dark:bg-sand-950/40 dark:text-sand-100">
                <p>{t("addKeyHint", { env: current.key_env })}</p>
                <code className="mt-1.5 block rounded-md bg-white px-2 py-1 font-mono dark:bg-black/30" dir="ltr" translate="no">
                  {current.key_env}=…
                </code>
                {current.key_url && (
                  <a
                    href={current.key_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1.5 inline-block font-medium text-zellige-700 underline-offset-2 hover:underline dark:text-zellige-300"
                  >
                    {t("getKey")}
                  </a>
                )}
              </div>
            )}

            {current?.configured && (
              <div className="mt-4 space-y-3">
                {current.local && (
                  <p className="text-xs text-zellige-500 dark:text-zellige-400">
                    {t("localHint")}{" "}
                    <span className="font-mono" dir="ltr" translate="no">
                      {current.base_url}
                    </span>
                  </p>
                )}
                <div>
                  <label htmlFor="llm-model" className="mb-1 block text-xs font-semibold text-zellige-700 dark:text-zellige-200">
                    {t("model")}
                  </label>
                  {current.local || modelsError ? (
                    <Input
                      id="llm-model"
                      name="llm-model"
                      autoComplete="off"
                      spellCheck={false}
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      placeholder={current.model || t("modelAuto")}
                      className="h-9 font-mono text-xs"
                      dir="ltr"
                    />
                  ) : (
                    <select
                      id="llm-model"
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      disabled={!models}
                      className="h-9 w-full rounded-xl border border-zellige-200 bg-white px-3 text-xs text-zellige-900 dark:border-zellige-700 dark:bg-[#0f1b16] dark:text-zellige-100"
                      dir="ltr"
                    >
                      <option value="">
                        {models?.[0] ? `${models[0]} (${t("recommended")})` : t("modelAuto")}
                      </option>
                      {models?.slice(1).map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  )}
                  {modelsError && <p className="mt-1 text-[11px] text-red-700 dark:text-red-300">{t("modelsError")}</p>}
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <Button variant="outline" size="sm" onClick={() => void runTest()} disabled={test === "running"}>
                    {test === "running" ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : <Zap className="h-3.5 w-3.5" aria-hidden />}
                    {test === "running" ? t("testing") : t("test")}
                  </Button>
                  <span aria-live="polite" className="min-w-0 flex-1 text-[11px]">
                    {test && test !== "running" &&
                      (test.ok ? (
                        <span className="flex items-center gap-1 text-zellige-600 dark:text-zellige-300" dir="ltr">
                          <CheckCircle2 className="h-3.5 w-3.5 shrink-0" aria-hidden />
                          <span className="truncate">{t("testOk", { model: test.model ?? "", ms: test.latency_ms ?? 0 })}</span>
                        </span>
                      ) : (
                        <span className="flex items-start gap-1 text-red-700 dark:text-red-300">
                          <CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                          <span className="break-words">
                            {t("testFail")}
                            {test.message ? ` — ${test.message.slice(0, 160)}` : ""}
                          </span>
                        </span>
                      ))}
                  </span>
                </div>
                <p className="text-[11px] leading-4 text-zellige-400 dark:text-zellige-500">{t("fallback")}</p>
              </div>
            )}
          </>
        )}

        <div className="mt-5 flex items-center justify-end gap-2">
          <Button variant="outline" size="sm" onClick={() => setOpen(false)}>
            {t("cancel")}
          </Button>
          <Button size="sm" onClick={save} disabled={!current?.configured}>
            {saved ? t("saved") : t("save")}
          </Button>
        </div>
      </div>
    </div>
  ) : null;

  return (
    <>
      <button
        ref={triggerRef}
        onClick={() => setOpen(true)}
        aria-label={t("title")}
        title={t("title")}
        className="flex h-9 w-9 items-center justify-center rounded-lg border border-zellige-200 text-zellige-600 transition-colors hover:bg-zellige-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zellige-500 dark:border-zellige-700 dark:text-zellige-300 dark:hover:bg-zellige-800"
      >
        <Settings className="h-4 w-4" aria-hidden />
      </button>
      {mounted ? createPortal(dialog, document.body) : null}
    </>
  );
}
