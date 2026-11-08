"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Description, Label, ListBox, Select } from "@heroui/react";
import { Cpu, KeyRound } from "lucide-react";
import { llmApi, loadChoice, onChoiceChange, saveChoice, type LlmChoice, type ProviderInfo } from "@/lib/settings";

const AUTO = "auto";

/** Which AI writes the answer, right in the composer. "Automatic" = the server's preferred
 * provider with fallback; a provider = its recommended model (pick a specific model in ⚙). */
export function AiSourceSelect() {
  const t = useTranslations("chat");
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [choice, setChoice] = useState<LlmChoice>({ provider: "", model: "" });

  useEffect(() => {
    setChoice(loadChoice());
    llmApi.providers().then((data) => setProviders(data.providers)).catch(() => {});
    // the settings dialog may change it too
    return onChoiceChange(() => setChoice(loadChoice()));
  }, []);

  const current = providers.find((p) => p.id === choice.provider && p.configured);
  const label = current ? `${current.label}${choice.model ? ` · ${choice.model}` : ""}` : t("aiAuto");

  return (
    <Select
      aria-label={t("aiLabel")}
      selectedKey={current ? current.id : AUTO}
      disabledKeys={providers.filter((p) => !p.configured).map((p) => p.id)}
      onSelectionChange={(key) => {
        if (key == null) return;
        const next = { provider: key === AUTO ? "" : String(key), model: "" };
        setChoice(next);
        saveChoice(next);
      }}
      className="min-w-0 max-w-[14rem]"
    >
      <Label className="sr-only">{t("aiLabel")}</Label>
      {/* pe-8: room for the indicator, which HeroUI positions over the trigger's end */}
      <Select.Trigger className="h-8 min-h-8 gap-1.5 rounded-full border-0 bg-default ps-3 pe-8 text-xs shadow-none [&_[data-slot=select-value]]:text-xs">
        <Cpu className="size-3.5 shrink-0 text-accent" aria-hidden />
        <Select.Value className="min-w-0 flex-1 truncate">{label}</Select.Value>
        <Select.Indicator />
      </Select.Trigger>
      <Select.Popover className="min-w-64">
        <ListBox>
          <ListBox.Item id={AUTO} textValue={t("aiAuto")}>
            <div className="flex flex-col">
              <Label>{t("aiAuto")}</Label>
              <Description>{t("aiAutoHint")}</Description>
            </div>
            <ListBox.ItemIndicator />
          </ListBox.Item>
          {providers.map((p) => (
            <ListBox.Item key={p.id} id={p.id} textValue={p.label}>
              <div className="flex flex-col">
                <Label>{p.label}</Label>
                <Description className="flex items-center gap-1">
                  {p.configured ? (
                    p.local ? t("aiLocal") : t("aiCloud")
                  ) : (
                    <>
                      <KeyRound className="size-3" aria-hidden />
                      {p.key_env}
                    </>
                  )}
                </Description>
              </div>
              <ListBox.ItemIndicator />
            </ListBox.Item>
          ))}
        </ListBox>
      </Select.Popover>
    </Select>
  );
}
