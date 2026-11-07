"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Eye, EyeOff, Settings, X } from "lucide-react";
import { PRESETS, loadSettings, saveSettings, type LlmSettings } from "@/lib/settings";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export function SettingsDialog({ locale, onChange }: { locale: string; onChange?: (s: LlmSettings) => void }) {
  const t = useTranslations("settings");
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<LlmSettings | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);

  // Load once on open so other tabs' writes don't clobber the form.
  useEffect(() => {
    if (open) {
      setDraft(loadSettings());
      setSaved(false);
    }
  }, [open]);

  const preset = PRESETS.find((p) => p.baseUrl === draft?.baseUrl) ?? PRESETS[0];

  const applyPreset = (id: string) => {
    const p = PRESETS.find((x) => x.id === id);
    if (!p || !draft) return;
    setDraft({
      ...draft,
      baseUrl: p.baseUrl,
      model: p.models[0] ?? "",
      apiKey: p.id === "lmstudio" ? "" : draft.apiKey,
    });
  };

  const save = () => {
    if (!draft) return;
    saveSettings(draft);
    onChange?.(draft);
    setSaved(true);
    setTimeout(() => setOpen(false), 700);
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-label={t("title")}
        title={t("title")}
        className="flex h-9 w-9 items-center justify-center rounded-lg border border-zellige-200 text-zellige-600 transition-colors hover:bg-zellige-50 dark:border-zellige-700 dark:text-zellige-300 dark:hover:bg-zellige-800"
      >
        <Settings className="h-4 w-4" />
      </button>

      {open && draft && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
          onClick={(e) => e.target === e.currentTarget && setOpen(false)}
        >
          <div
            className={cn(
              "w-full max-w-lg rounded-2xl border border-zellige-100 bg-white p-6 shadow-2xl dark:border-zellige-800 dark:bg-[#12201a]",
              "max-h-[90vh] overflow-y-auto thin-scroll"
            )}
            role="dialog"
            aria-modal="true"
            aria-label={t("title")}
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold text-zellige-900 dark:text-white">{t("title")}</h2>
              <button
                onClick={() => setOpen(false)}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-zellige-500 hover:bg-zellige-100 dark:hover:bg-zellige-800"
                aria-label="close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="mb-5 text-sm text-zellige-600 dark:text-zellige-300">{t("intro")}</p>

            {/* Provider toggle */}
            <label className="mb-5 flex cursor-pointer items-center justify-between rounded-xl border border-zellige-200 p-3 dark:border-zellige-700">
              <div>
                <div className="text-sm font-semibold text-zellige-900 dark:text-white">{t("useCustom")}</div>
                <div className="text-xs text-zellige-500 dark:text-zellige-400">{t("useCustomHint")}</div>
              </div>
              <input
                type="checkbox"
                checked={draft.enabled}
                onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
                className="h-5 w-5 accent-zellige-700"
              />
            </label>

            <div className={cn("space-y-4", !draft.enabled && "opacity-50 pointer-events-none")}>
              {/* Presets */}
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-zellige-700 dark:text-zellige-200">{t("provider")}</label>
                <div className="grid grid-cols-2 gap-2">
                  {PRESETS.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => applyPreset(p.id)}
                      className={cn(
                        "rounded-xl border px-3 py-2 text-xs font-medium transition-colors",
                        preset.id === p.id
                          ? "border-zellige-600 bg-zellige-700 text-white dark:bg-zellige-600"
                          : "border-zellige-200 text-zellige-700 hover:bg-zellige-50 dark:border-zellige-700 dark:text-zellige-200 dark:hover:bg-zellige-800/60"
                      )}
                    >
                      {p.label[locale as "ar" | "fr" | "en"]}
                    </button>
                  ))}
                </div>
                <p className="mt-2 text-xs text-zellige-500 dark:text-zellige-400">{preset.hint[locale as "ar" | "fr" | "en"]}</p>
              </div>

              {/* Base URL */}
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-zellige-700 dark:text-zellige-200">{t("baseUrl")}</label>
                <Input
                  value={draft.baseUrl}
                  onChange={(e) => setDraft({ ...draft, baseUrl: e.target.value })}
                  placeholder="https://…/v1"
                  className="h-9 font-mono text-xs"
                  dir="ltr"
                />
              </div>

              {/* Model */}
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-zellige-700 dark:text-zellige-200">
                  {t("model")} <span className="font-normal text-zellige-400">({t("optional")})</span>
                </label>
                {preset.models.length > 0 ? (
                  <select
                    value={draft.model}
                    onChange={(e) => setDraft({ ...draft, model: e.target.value })}
                    className="h-9 w-full rounded-xl border border-zellige-200 bg-white px-3 text-xs dark:border-zellige-700 dark:bg-[#0f1b16] dark:text-zellige-100"
                    dir="ltr"
                  >
                    <option value="">{t("modelAuto")}</option>
                    {preset.models.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                ) : (
                  <Input
                    value={draft.model}
                    onChange={(e) => setDraft({ ...draft, model: e.target.value })}
                    placeholder={t("modelAuto")}
                    className="h-9 font-mono text-xs"
                    dir="ltr"
                  />
                )}
              </div>

              {/* API key */}
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-zellige-700 dark:text-zellige-200">
                  {t("apiKey")}
                  {preset.needsKey && preset.keyUrl && (
                    <a
                      href={preset.keyUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="ms-2 font-normal text-zellige-600 underline-offset-2 hover:underline dark:text-zellige-300"
                    >
                      {t("getKey")}
                    </a>
                  )}
                </label>
                <div className="relative">
                  <Input
                    type={showKey ? "text" : "password"}
                    value={draft.apiKey}
                    onChange={(e) => setDraft({ ...draft, apiKey: e.target.value })}
                    placeholder={preset.needsKey ? "sk-…" : t("notNeeded")}
                    className="h-9 pe-10 font-mono text-xs"
                    dir="ltr"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="absolute end-2 top-1/2 -translate-y-1/2 text-zellige-400 hover:text-zellige-700 dark:hover:text-zellige-200"
                    aria-label="show/hide key"
                  >
                    {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                <p className="mt-2 text-[11px] leading-4 text-zellige-400 dark:text-zellige-500">{t("privacy")}</p>
              </div>
            </div>

            <div className="mt-6 flex items-center justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setOpen(false)}>
                {t("cancel")}
              </Button>
              <Button size="sm" onClick={save}>
                {saved ? t("saved") : t("save")}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
