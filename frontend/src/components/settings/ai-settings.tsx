"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Alert,
  Button,
  Chip,
  Input,
  Label,
  ListBox,
  Select,
  Spinner,
  TextField,
} from "@heroui/react";
import { CheckCircle2, KeyRound, Zap } from "lucide-react";
import {
  llmApi,
  loadChoice,
  saveChoice,
  type LlmChoice,
  type ProviderInfo,
  type TestResult,
} from "@/lib/settings";
import { cn } from "@/lib/utils";

const RECOMMENDED = "__recommended__";

/** Provider, model and connection test — the AI section of the settings page. */
export function AiSettings() {
  const t = useTranslations("settings");
  const [saved, setSaved] = useState(false);
  const [providers, setProviders] = useState<ProviderInfo[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [selected, setSelected] = useState("");
  const [model, setModel] = useState("");
  const [models, setModels] = useState<string[] | null>(null);
  const [modelsError, setModelsError] = useState(false);
  const [test, setTest] = useState<TestResult | "running" | null>(null);

  // The saved choice + the server's providers (re-read on mount: .env may have changed).
  useEffect(() => {
    const choice = loadChoice();
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
  }, []);

  const current = providers?.find((p) => p.id === selected);

  // Cloud providers: their live model list, recommended first.
  useEffect(() => {
    setModels(null);
    setModelsError(false);
    if (!current?.configured || current.local) return;
    llmApi
      .models(current.id)
      .then((data) => setModels(data.models))
      .catch(() => setModelsError(true));
  }, [current?.id, current?.configured, current?.local]);

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
    setTimeout(() => setSaved(false), 1600);
  };

  return (
    <div className="flex flex-col gap-4">
      {loadError && (
        <Alert status="danger">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Description>{t("loadError")}</Alert.Description>
          </Alert.Content>
        </Alert>
      )}
      {!providers && !loadError && <Spinner className="mx-auto my-6" aria-label={t("testing")} />}

      {providers && (
        <>
          <div role="radiogroup" aria-label={t("provider")} className="grid grid-cols-2 gap-2">
            {providers.map((p) => {
              const active = p.id === selected;
              return (
                <button
                  key={p.id}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  onClick={() => {
                    setSelected(p.id);
                    setModel("");
                    setTest(null);
                  }}
                  className={cn(
                    "flex flex-col items-start gap-1 rounded-[var(--radius)] border p-3 text-start transition-colors",
                    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus",
                    active ? "border-accent bg-accent/8" : "border-border hover:bg-default"
                  )}
                >
                  <span className="text-sm font-semibold">{p.label}</span>
                  <Chip size="sm" variant="soft" color={p.configured ? "success" : "warning"}>
                    {p.configured ? <CheckCircle2 className="size-3" aria-hidden /> : <KeyRound className="size-3" aria-hidden />}
                    {p.configured ? t("ready") : t("needsKey")}
                  </Chip>
                </button>
              );
            })}
          </div>

          {current && !current.configured && (
            <Alert status="warning">
              <Alert.Indicator />
              <Alert.Content>
                <Alert.Title>{t("needsKey")}</Alert.Title>
                <Alert.Description>
                  {t("addKeyHint", { env: current.key_env })}
                  <code className="mt-2 block rounded-md bg-surface px-2 py-1 font-mono text-xs" dir="ltr" translate="no">
                    {current.key_env}=…
                  </code>
                  {current.key_url && (
                    <a
                      href={current.key_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-2 inline-block font-medium text-accent underline-offset-2 hover:underline"
                    >
                      {t("getKey")}
                    </a>
                  )}
                </Alert.Description>
              </Alert.Content>
            </Alert>
          )}

          {current?.configured && (
            <>
              {current.local && (
                <p className="text-xs text-muted">
                  {t("localHint")}{" "}
                  <span className="font-mono" dir="ltr" translate="no">
                    {current.base_url}
                  </span>
                </p>
              )}

              {current.local || modelsError ? (
                <TextField value={model} onChange={setModel} name="llm-model">
                  <Label>{t("model")}</Label>
                  <Input placeholder={current.model || t("modelAuto")} className="font-mono text-xs" dir="ltr" autoComplete="off" spellCheck={false} />
                  {modelsError && <p className="text-xs text-danger">{t("modelsError")}</p>}
                </TextField>
              ) : (
                <Select
                  selectedKey={model || RECOMMENDED}
                  onSelectionChange={(key) => setModel(key == null || key === RECOMMENDED ? "" : String(key))}
                  isDisabled={!models}
                >
                  <Label>{t("model")}</Label>
                  <Select.Trigger>
                    <Select.Value className="font-mono text-xs" />
                    {models ? <Select.Indicator /> : <Spinner size="sm" />}
                  </Select.Trigger>
                  <Select.Popover>
                    <ListBox className="max-h-72">
                      <ListBox.Item id={RECOMMENDED} textValue={models?.[0] ?? t("modelAuto")}>
                        <span className="font-mono text-xs" dir="ltr">
                          {models?.[0] ?? t("modelAuto")}
                        </span>
                        <Chip size="sm" color="accent" variant="soft">
                          {t("recommended")}
                        </Chip>
                        <ListBox.ItemIndicator />
                      </ListBox.Item>
                      {(models ?? []).slice(1).map((m) => (
                        <ListBox.Item key={m} id={m} textValue={m}>
                          <span className="font-mono text-xs" dir="ltr">
                            {m}
                          </span>
                          <ListBox.ItemIndicator />
                        </ListBox.Item>
                      ))}
                    </ListBox>
                  </Select.Popover>
                </Select>
              )}

              <div className="flex flex-col gap-2">
                <Button variant="secondary" size="sm" className="self-start" isPending={test === "running"} onPress={() => void runTest()}>
                  {test !== "running" && <Zap className="size-3.5" aria-hidden />}
                  {test === "running" ? t("testing") : t("test")}
                </Button>
                <div aria-live="polite">
                  {test && test !== "running" && (
                    <Alert status={test.ok ? "success" : "danger"}>
                      <Alert.Indicator />
                      <Alert.Content>
                        <Alert.Title>
                          {test.ok
                            ? t("testOk", { model: test.model ?? "", ms: test.latency_ms ?? 0 })
                            : t("testFail")}
                        </Alert.Title>
                        {test.ok && test.failed && test.failed.length > 0 && (
                          <Alert.Description>
                            {t("testSkipped", { models: test.failed.map((f) => f.model).join(", ") })}
                          </Alert.Description>
                        )}
                        {!test.ok && test.message && (
                          <Alert.Description className="break-words text-xs" dir="ltr">
                            {test.message.slice(0, 240)}
                          </Alert.Description>
                        )}
                      </Alert.Content>
                    </Alert>
                  )}
                </div>
              </div>
              <p className="text-xs leading-5 text-muted">{t("fallback")}</p>
            </>
          )}
        </>
      )}

    <div className="flex justify-end gap-2">
      <Button onPress={save} isDisabled={!current?.configured}>
        {saved ? t("saved") : t("save")}
      </Button>
    </div>
    </div>
  );
}
