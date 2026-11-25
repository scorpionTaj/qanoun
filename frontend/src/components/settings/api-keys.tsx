"use client";

import { useEffect, useState } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { Alert, Button, Input, Label, TextField } from "@heroui/react";
import { Check, Copy, KeyRound, Trash2 } from "lucide-react";
import { accountApi, type ApiKey } from "@/lib/account";
import { apiUrl } from "@/lib/api-url";

/** The signed-in user's API keys: create (the key is shown once), list, revoke. */
export function ApiKeys() {
  const t = useTranslations("apiKeys");
  const format = useFormatter();
  const [keys, setKeys] = useState<ApiKey[] | null>(null);
  const [name, setName] = useState("");
  const [fresh, setFresh] = useState<ApiKey | null>(null); // just created: its key, shown once
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    accountApi.keys().then(setKeys, () => setError(t("failed")));
  }, [t]);

  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const key = await accountApi.createKey(name.trim());
      setFresh(key);
      setCopied(false);
      setName("");
      setKeys(await accountApi.keys());
    } catch (e) {
      setError((e as { status?: number }).status === 409 ? t("tooMany") : t("failed"));
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (key: ApiKey) => {
    setError(null);
    try {
      await accountApi.revokeKey(key.id);
      setKeys((prev) => prev?.filter((k) => k.id !== key.id) ?? null);
      if (fresh?.id === key.id) setFresh(null);
    } catch {
      setError(t("failed"));
    }
  };

  const copy = async () => {
    if (!fresh?.key) return;
    await navigator.clipboard.writeText(fresh.key).then(() => setCopied(true), () => {});
  };

  const date = (iso: string) => format.dateTime(new Date(iso), { dateStyle: "medium" });

  return (
    <div className="mt-5 flex flex-col gap-4 border-t border-separator pt-5" aria-labelledby="api-keys-title">
      <div className="flex items-start gap-2">
        <KeyRound className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
        <div>
          <h3 id="api-keys-title" className="font-semibold">{t("title")}</h3>
          <p className="text-sm text-muted">{t("hint")}</p>
        </div>
      </div>

      {fresh?.key && (
        <Alert status="success">
          <Alert.Indicator />
          <Alert.Content className="min-w-0">
            <Alert.Title>{t("createdTitle", { name: fresh.name })}</Alert.Title>
            <Alert.Description>{t("createdHint")}</Alert.Description>
            <div className="mt-2 flex items-center gap-2">
              <code dir="ltr" className="min-w-0 flex-1 truncate rounded-lg bg-surface px-2 py-1 font-mono text-xs" data-testid="new-api-key">
                {fresh.key}
              </code>
              <Button size="sm" variant="secondary" onPress={copy} aria-label={t("copy")}>
                {copied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />}
                {copied ? t("copied") : t("copy")}
              </Button>
            </div>
            <pre dir="ltr" className="mt-2 overflow-x-auto rounded-lg bg-surface px-2 py-1 font-mono text-xs">
              {`curl -H "Authorization: Bearer ${fresh.key.slice(0, 7)}…" \\\n  -H "Content-Type: application/json" -d '{"q":"…"}' ${apiUrl()}/api/search`}
            </pre>
          </Alert.Content>
        </Alert>
      )}

      {keys && keys.length > 0 && (
        <ul className="flex flex-col divide-y divide-separator rounded-2xl border border-separator">
          {keys.map((key) => (
            <li key={key.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
              <div className="min-w-0">
                <p className="truncate font-medium">{key.name}</p>
                <p className="text-xs text-muted">
                  <span dir="ltr" className="font-mono">{key.prefix}…</span>
                  {" · "}
                  {t("created", { date: date(key.created_at) })}
                  {" · "}
                  {key.last_used_at ? t("lastUsed", { date: date(key.last_used_at) }) : t("neverUsed")}
                </p>
              </div>
              <Button size="sm" variant="danger-soft" onPress={() => revoke(key)} aria-label={t("revokeNamed", { name: key.name })}>
                <Trash2 className="size-4" aria-hidden />
                {t("revoke")}
              </Button>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={create} className="flex flex-wrap items-end gap-3">
        <TextField value={name} onChange={setName} isRequired maxLength={60} name="key-name" className="min-w-48 flex-1">
          <Label>{t("name")}</Label>
          <Input placeholder={t("namePlaceholder")} />
        </TextField>
        <Button type="submit" isPending={busy}>{t("create")}</Button>
      </form>

      {error && (
        <Alert status="danger">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Description>{error}</Alert.Description>
          </Alert.Content>
        </Alert>
      )}
    </div>
  );
}
