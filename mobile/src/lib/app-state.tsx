/** App-wide state: settings, the signed-in account, saved conversations, and their sync.
 *
 * Signed out, everything stays on the device. Signing in pulls the account's settings (they
 * win: they follow the user from another device; an account without any takes the device's)
 * and merges conversations both ways. While signed in, each change is pushed. */
import { reloadAppAsync } from "expo";
import { createContext, type ReactNode, use, useCallback, useEffect, useMemo, useState } from "react";
import { Appearance } from "react-native";

import { accountApi, type User } from "./api";
import { type Conversation, loadConversations, mergeConversations, saveConversations, storable } from "./conversations";
import { getSession, setSession } from "./session";
import { loadSettings, saveSettings, type Settings } from "./settings";

interface AppState {
  settings: Settings;
  updateSettings: (patch: Partial<Settings>) => void;
  user: User | null;
  signupAllowed: boolean;
  signIn: (mode: "login" | "signup", email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  conversations: Conversation[];
  saveConversation: (c: Conversation) => void;
  deleteConversation: (id: string) => void;
}

const Context = createContext<AppState | null>(null);

export function useApp(): AppState {
  const state = use(Context);
  if (!state) throw new Error("useApp outside AppProvider");
  return state;
}

const applyTheme = (theme: Settings["theme"]) => Appearance.setColorScheme(theme === "system" ? "unspecified" : theme);

export function AppProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(loadSettings);
  const [user, setUser] = useState<User | null>(null);
  const [signupAllowed, setSignupAllowed] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>(loadConversations);

  useEffect(() => applyTheme(settings.theme), [settings.theme]);

  // Apply settings that came from elsewhere (the account); a new language needs a restart.
  const adopt = useCallback((next: Settings) => {
    const languageChanged = next.ui_language !== loadSettings().ui_language;
    saveSettings(next);
    setSettings(next);
    if (languageChanged) reloadAppAsync("language");
  }, []);

  const sync = useCallback(async () => {
    const [remoteSettings, remoteConversations] = await Promise.all([accountApi.settings(), accountApi.conversations()]);
    const local = loadSettings();
    if (Object.keys(remoteSettings).length) adopt({ ...local, ...remoteSettings });
    else await accountApi.saveSettings(local);
    const merged = mergeConversations(loadConversations(), remoteConversations as Conversation[]);
    saveConversations(merged);
    setConversations(merged);
    const remoteAt = new Map(remoteConversations.map((c) => [c.id, c.updatedAt]));
    await Promise.all(
      merged.filter((c) => (remoteAt.get(c.id) ?? -1) < c.updatedAt).map((c) => accountApi.saveConversation(c)),
    );
  }, [adopt]);

  useEffect(() => {
    accountApi.me().then(
      ({ user, signup_allowed }) => {
        setSignupAllowed(signup_allowed);
        if (user && getSession()) {
          setUser(user);
          sync().catch(() => {});
        } else if (getSession()) {
          setSession(null); // expired or signed out elsewhere
        }
      },
      () => {}, // offline: keep working from the device
    );
  }, [sync]);

  const updateSettings = useCallback(
    (patch: Partial<Settings>) => {
      const next = { ...settings, ...patch };
      saveSettings(next);
      setSettings(next);
      if (user) accountApi.saveSettings(next).catch(() => {});
      if (patch.ui_language && patch.ui_language !== settings.ui_language) reloadAppAsync("language");
    },
    [settings, user],
  );

  const signIn = useCallback(
    async (mode: "login" | "signup", email: string, password: string) => {
      const { token } = await accountApi.signIn(mode, email, password);
      setSession(token);
      setUser((await accountApi.me()).user);
      await sync();
    },
    [sync],
  );

  const signOut = useCallback(async () => {
    await accountApi.signOut().catch(() => {});
    setSession(null);
    setUser(null);
  }, []);

  const saveConversation = useCallback(
    (c: Conversation) => {
      const kept = storable(c);
      setConversations((list) => {
        const next = [kept, ...list.filter((x) => x.id !== c.id)];
        saveConversations(next);
        return next;
      });
      if (user) accountApi.saveConversation(kept).catch(() => {});
    },
    [user],
  );

  const deleteConversation = useCallback(
    (id: string) => {
      setConversations((list) => {
        const next = list.filter((x) => x.id !== id);
        saveConversations(next);
        return next;
      });
      if (user) accountApi.deleteConversation(id).catch(() => {});
    },
    [user],
  );

  const value = useMemo(
    () => ({ settings, updateSettings, user, signupAllowed, signIn, signOut, conversations, saveConversation, deleteConversation }),
    [settings, updateSettings, user, signupAllowed, signIn, signOut, conversations, saveConversation, deleteConversation],
  );
  return <Context value={value}>{children}</Context>;
}
