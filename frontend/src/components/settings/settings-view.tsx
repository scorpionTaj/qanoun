"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Button, Card, Label, ListBox, Select, ToggleButton, ToggleButtonGroup } from "@heroui/react";
import { Check, Cpu, Database, Download, Library, MessageSquareText, Trash2 } from "lucide-react";
import { loadConversations, saveConversations } from "@/lib/conversations";
import { DEFAULT_PREFERENCES, loadPreferences, savePreferences, type Preferences } from "@/lib/preferences";
import { AiSettings } from "./ai-settings";
import { AccountCard } from "./account-card";
import { accountApi } from "@/lib/account";
import { ScopeSelect, loadScope, saveScope, type Scope } from "@/components/chat/scope-select";

export function SettingsView({ locale }: { locale: string }) {
  const t = useTranslations("settings");
  const [prefs, setPrefs] = useState<Preferences>(DEFAULT_PREFERENCES);
  const [scope, setScope] = useState<Scope>({});
  const [count, setCount] = useState(0);
  const [saved, setSaved] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  useEffect(() => {
    setPrefs(loadPreferences());
    setScope(loadScope());
    setCount(loadConversations().length);
  }, []);

  const flash = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 1400);
  };
  const update = (patch: Partial<Preferences>) => {
    const next = { ...prefs, ...patch };
    setPrefs(next);
    savePreferences(next);
    flash();
  };

  const exportHistory = () => {
    const blob = new Blob([JSON.stringify(loadConversations(), null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: "qanoun-conversations.json" });
    a.click();
    URL.revokeObjectURL(url);
  };

  const clearHistory = () => {
    saveConversations([]);
    void accountApi.removeAll().catch(() => {}); // signed out: 401, nothing on the server
    setCount(0);
    setConfirmClear(false);
  };

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-10">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">{t("pageTitle")}</h1>
          <p className="mt-1 text-muted">{t("pageSubtitle")}</p>
        </div>
        <span aria-live="polite" className="flex items-center gap-1 text-sm text-success">
          {saved && (
            <>
              <Check className="size-4" aria-hidden />
              {t("saved")}
            </>
          )}
        </span>
      </header>

      <AccountCard onSynced={setCount} />

      <Section icon={<Cpu className="size-5" aria-hidden />} title={t("aiSection")} description={t("intro")}>
        <AiSettings />
      </Section>

      <Section icon={<MessageSquareText className="size-5" aria-hidden />} title={t("answersSection")} description={t("answersHint")}>
        <Row label={t("style")} hint={t("styleHint")}>
          <ToggleButtonGroup
            aria-label={t("style")}
            selectionMode="single"
            disallowEmptySelection
            selectedKeys={[prefs.style]}
            onSelectionChange={(keys) => {
              const key = [...keys][0];
              if (key) update({ style: key as Preferences["style"] });
            }}
          >
            <ToggleButton id="concise">{t("styleConcise")}</ToggleButton>
            <ToggleButton id="detailed">
              <ToggleButtonGroup.Separator />
              {t("styleDetailed")}
            </ToggleButton>
          </ToggleButtonGroup>
        </Row>
        <Row label={t("answerLanguage")} hint={t("answerLanguageHint")}>
          <Select
            aria-label={t("answerLanguage")}
            selectedKey={prefs.answerLanguage}
            onSelectionChange={(key) => key != null && update({ answerLanguage: key as Preferences["answerLanguage"] })}
            className="w-56"
          >
            <Label className="sr-only">{t("answerLanguage")}</Label>
            <Select.Trigger>
              <Select.Value />
              <Select.Indicator />
            </Select.Trigger>
            <Select.Popover>
              <ListBox>
                {(["auto", "ar", "fr", "en"] as const).map((lang) => (
                  <ListBox.Item key={lang} id={lang} textValue={t(`lang_${lang}`)}>
                    {t(`lang_${lang}`)}
                    <ListBox.ItemIndicator />
                  </ListBox.Item>
                ))}
              </ListBox>
            </Select.Popover>
          </Select>
        </Row>
        <Row label={t("sourcesCount")} hint={t("sourcesHint")}>
          <ToggleButtonGroup
            aria-label={t("sourcesCount")}
            selectionMode="single"
            disallowEmptySelection
            selectedKeys={[String(prefs.sources)]}
            onSelectionChange={(keys) => {
              const key = [...keys][0];
              if (key) update({ sources: Number(key) as Preferences["sources"] });
            }}
          >
            {["3", "5", "8"].map((n, i) => (
              <ToggleButton key={n} id={n}>
                {i > 0 && <ToggleButtonGroup.Separator />}
                {n}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
        </Row>
      </Section>

      <Section icon={<Library className="size-5" aria-hidden />} title={t("searchSection")} description={t("searchHint")}>
        <Row label={t("defaultScope")} hint={t("defaultScopeHint")}>
          <ScopeSelect
            locale={locale}
            scope={scope}
            onChange={(next) => {
              setScope(next);
              saveScope(next);
              flash();
            }}
          />
        </Row>
      </Section>

      <Section icon={<Database className="size-5" aria-hidden />} title={t("dataSection")} description={t("dataHint")}>
        <Row label={t("conversations")} hint={t("conversationsCount", { count })}>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onPress={exportHistory} isDisabled={count === 0}>
              <Download className="size-4" aria-hidden />
              {t("export")}
            </Button>
            <Button
              variant={confirmClear ? "danger" : "secondary"}
              size="sm"
              onPress={() => (confirmClear ? clearHistory() : setConfirmClear(true))}
              onBlur={() => setConfirmClear(false)}
              isDisabled={count === 0}
            >
              <Trash2 className="size-4" aria-hidden />
              {confirmClear ? t("clearConfirm") : t("clear")}
            </Button>
          </div>
        </Row>
      </Section>
    </div>
  );
}

function Section({
  icon,
  title,
  description,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="gap-5 p-6">
      <Card.Header className="flex-row items-start gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent">{icon}</span>
        <div>
          <Card.Title className="text-lg">{title}</Card.Title>
          <Card.Description>{description}</Card.Description>
        </div>
      </Card.Header>
      <Card.Content className="flex flex-col gap-5">{children}</Card.Content>
    </Card>
  );
}

function Row({ label, hint, children }: { label: string; hint: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2 border-t border-separator pt-5 first:border-0 first:pt-0 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <div className="font-medium">{label}</div>
        <p className="text-sm text-muted">{hint}</p>
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}
