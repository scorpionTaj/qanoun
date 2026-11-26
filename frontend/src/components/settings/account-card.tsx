"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { Alert, Button, Input, Label, TextField, ToggleButton, ToggleButtonGroup } from "@heroui/react";
import { CloudCheck, Download, LogOut, Trash2, UserRound } from "lucide-react";
import { accountApi, mergeConversations, type Me } from "@/lib/account";
import { loadConversations, saveConversations } from "@/lib/conversations";
import { ApiKeys } from "./api-keys";

/** Optional account: sign in to sync conversations across devices. The app works without it. */
export function AccountCard({ onSynced }: { onSynced?: (count: number) => void }) {
  const t = useTranslations("account");
  const [me, setMe] = useState<Me | null>(null);
  const [offline, setOffline] = useState(false);
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [consent, setConsent] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmPassword, setConfirmPassword] = useState("");
  const locale = useLocale();

  useEffect(() => {
    accountApi.me().then(setMe, () => setOffline(true));
  }, []);

  // Right after signing in: upload this browser's conversations and pull the account's.
  const sync = async () => {
    const remote = await accountApi.conversations();
    const merged = mergeConversations(loadConversations(), remote);
    saveConversations(merged);
    const remoteAt = new Map(remote.map((c) => [c.id, c.updatedAt]));
    await Promise.all(merged.filter((c) => (remoteAt.get(c.id) ?? -1) < c.updatedAt).map((c) => accountApi.put(c)));
    onSynced?.(merged.length);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (mode === "signup" && !consent) {
      setError(t("consentRequired"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await (mode === "signup" ? accountApi.signup(email, password) : accountApi.login(email, password));
      setMe(await accountApi.me());
      setPassword("");
      await sync().catch(() => {});
    } catch (e) {
      const status = (e as { status?: number }).status;
      setError(
        status === 401 ? t("wrongCredentials")
        : status === 409 ? t("emailTaken")
        : status === 403 ? t("signupClosed")
        : status === 422 ? t("invalid")
        : status === 429 ? t("tooMany")
        : t("failed"),
      );
    } finally {
      setBusy(false);
    }
  };

  const download = async () => {
    const data = await accountApi.exportData();
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "qanoun-my-data.json" });
    a.click();
    URL.revokeObjectURL(url);
  };

  const deleteAccount = async () => {
    setBusy(true);
    setError(null);
    try {
      await accountApi.deleteAccount(confirmPassword);
      setMe((prev) => (prev ? { ...prev, user: null } : prev));
      setDeleting(false);
      setConfirmPassword("");
    } catch (e) {
      setError((e as { status?: number }).status === 401 ? t("wrongPassword") : t("failed"));
    } finally {
      setBusy(false);
    }
  };

  const logout = async () => {
    await accountApi.logout().catch(() => {});
    setMe((prev) => (prev ? { ...prev, user: null } : prev));
  };

  if (offline) return null; // API down: nothing to sign in to
  if (!me) return <div className="h-24 animate-pulse rounded-3xl bg-surface" aria-hidden />;

  return (
    <section className="rounded-3xl border border-separator bg-surface p-6 shadow-sm" aria-labelledby="account-title">
      <div className="flex items-start gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent">
          <UserRound className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <h2 id="account-title" className="text-lg font-semibold">{t("title")}</h2>
          <p className="text-sm text-muted">{me.user ? t("syncedHint") : t("hint")}</p>
        </div>
      </div>

      {me.user ? (
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-separator pt-5">
          <div className="flex min-w-0 items-center gap-2">
            <CloudCheck className="size-4 shrink-0 text-success" aria-hidden />
            <span className="truncate font-medium" dir="ltr">{me.user.email}</span>
          </div>
          <Button variant="secondary" size="sm" onPress={logout}>
            <LogOut className="size-4" aria-hidden />
            {t("logout")}
          </Button>
        </div>
      ) : null}
      {me.user ? (
        <>
          <ApiKeys />
          <div className="mt-5 flex flex-col gap-3 border-t border-separator pt-5">
            <h3 className="text-sm font-semibold">{t("myData")}</h3>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" size="sm" onPress={() => void download().catch(() => setError(t("failed")))}>
                <Download className="size-4" aria-hidden />
                {t("download")}
              </Button>
              <Button variant="danger-soft" size="sm" onPress={() => setDeleting(true)}>
                <Trash2 className="size-4" aria-hidden />
                {t("delete")}
              </Button>
            </div>
            {deleting && (
              <div className="flex flex-col gap-3 rounded-2xl border border-danger/40 p-4" role="alertdialog" aria-label={t("delete")}>
                <p className="text-sm">{t("deleteConfirm")}</p>
                <TextField value={confirmPassword} onChange={setConfirmPassword} type="password" name="confirm-password">
                  <Label>{t("password")}</Label>
                  <Input autoComplete="current-password" dir="ltr" />
                </TextField>
                <div className="flex gap-2">
                  <Button variant="danger" size="sm" isPending={busy} isDisabled={!confirmPassword} onPress={deleteAccount}>{t("deleteAction")}</Button>
                  <Button variant="secondary" size="sm" onPress={() => { setDeleting(false); setConfirmPassword(""); setError(null); }}>{t("cancel")}</Button>
                </div>
              </div>
            )}
            {error && <p className="text-sm text-danger" role="alert">{error}</p>}
          </div>
        </>
      ) : (
        <form onSubmit={submit} className="mt-5 flex flex-col gap-4 border-t border-separator pt-5">
          {me.signup_allowed && (
            <ToggleButtonGroup
              aria-label={t("title")}
              selectionMode="single"
              disallowEmptySelection
              selectedKeys={[mode]}
              onSelectionChange={(keys) => {
                const key = [...keys][0];
                if (key) setMode(key as typeof mode);
                setError(null);
              }}
              className="self-start"
            >
              <ToggleButton id="login">{t("login")}</ToggleButton>
              <ToggleButton id="signup">
                <ToggleButtonGroup.Separator />
                {t("signup")}
              </ToggleButton>
            </ToggleButtonGroup>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField value={email} onChange={setEmail} type="email" isRequired name="email">
              <Label>{t("email")}</Label>
              <Input autoComplete="email" dir="ltr" />
            </TextField>
            <TextField value={password} onChange={setPassword} type="password" isRequired minLength={8} name="password">
              <Label>{t("password")}</Label>
              <Input autoComplete={mode === "signup" ? "new-password" : "current-password"} dir="ltr" />
            </TextField>
          </div>
          {mode === "signup" && <p className="text-xs text-muted">{t("passwordHint")}</p>}
          {mode === "signup" && (
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" name="accept-privacy" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1 size-4 accent-current" />
              <span>
                {t.rich("consent", {
                  privacy: () => (
                    <Link href={`/${locale}/privacy`} target="_blank" className="text-accent underline underline-offset-2">{t("privacyLink")}</Link>
                  ),
                })}
              </span>
            </label>
          )}
          {error && (
            <Alert status="danger">
              <Alert.Indicator />
              <Alert.Content>
                <Alert.Description>{error}</Alert.Description>
              </Alert.Content>
            </Alert>
          )}
          <Button type="submit" isPending={busy} className="self-start">
            {mode === "signup" ? t("signupAction") : t("loginAction")}
          </Button>
        </form>
      )}
    </section>
  );
}
