"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Alert, Button, Input, Label, TextField, ToggleButton, ToggleButtonGroup } from "@heroui/react";
import { CloudCheck, LogOut, UserRound } from "lucide-react";
import { accountApi, mergeConversations, type Me } from "@/lib/account";
import { loadConversations, saveConversations } from "@/lib/conversations";

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
