import Constants from "expo-constants";
import * as WebBrowser from "expo-web-browser";
import { type ReactNode, useEffect, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useTheme } from "@/hooks/use-theme";
import { ApiError, models as fetchModels, type Provider, providers as fetchProviders } from "@/lib/api";
import { useApp } from "@/lib/app-state";
import { WEB_URL } from "@/lib/config";
import { LANG, t } from "@/lib/i18n";
import type { Settings } from "@/lib/settings";

export default function SettingsScreen() {
  const colors = useTheme();
  const { settings, updateSettings, conversations, deleteConversation } = useApp();

  const clearAll = () =>
    Alert.alert(t.deleteConfirm, undefined, [
      { text: t.cancel, style: "cancel" },
      { text: t.delete, style: "destructive", onPress: () => conversations.forEach((c) => deleteConversation(c.id)) },
    ]);

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.background }]} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={[styles.title, { color: colors.text }]}>{t.settings}</Text>

        <AccountCard />

        <Card title={t.aiSection} hint={t.aiHint}>
          <ModelPicker settings={settings} update={updateSettings} />
        </Card>

        <Card title={t.answersSection}>
          <Label text={t.length} />
          <Choices value={settings.style} onChange={(style) => updateSettings({ style })}
            options={[["concise", t.concise], ["detailed", t.detailed]]} />
          <Label text={t.answerLanguage} />
          <Choices value={settings.answer_language} onChange={(answer_language) => updateSettings({ answer_language })}
            options={[["auto", t.sameAsQuestion], ["ar", "العربية"], ["fr", "Français"], ["en", "English"]]} wrap />
        </Card>

        <Card title={t.appearance}>
          <Choices value={settings.theme} onChange={(theme) => updateSettings({ theme })}
            options={[["system", t.system], ["light", t.light], ["dark", t.dark]]} />
          <Label text={t.language} />
          <Choices value={settings.ui_language} onChange={(ui_language) => updateSettings({ ui_language })}
            options={[["ar", "العربية"], ["fr", "Français"], ["en", "English"]]} />
          <Text style={[styles.hint, { color: colors.textSecondary }]}>{t.languageHint}</Text>
        </Card>

        <Card title={t.history}>
          <Text style={{ color: colors.textSecondary }}>{conversations.length}</Text>
          {conversations.length > 0 && (
            <Pressable onPress={clearAll} accessibilityRole="button">
              <Text style={{ color: colors.danger }}>{t.deleteAll}</Text>
            </Pressable>
          )}
        </Card>

        <Card title={t.about}>
          <Text style={{ color: colors.textSecondary, lineHeight: 20 }}>{t.disclaimer}</Text>
          <Pressable onPress={() => WebBrowser.openBrowserAsync(`${WEB_URL}/${LANG}`)} accessibilityRole="link">
            <Text style={{ color: colors.accent }}>{t.openWeb}</Text>
          </Pressable>
          <Text style={[styles.hint, { color: colors.textSecondary }]}>
            {t.version} {Constants.expoConfig?.version}
          </Text>
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

function AccountCard() {
  const colors = useTheme();
  const { user, signupAllowed, signIn, signOut } = useApp();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await signIn(mode, email.trim(), password);
      setPassword("");
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      setError(
        status === 401 ? t.wrongCredentials : status === 409 ? t.emailTaken : status === 403 ? t.signupClosed
        : status === 422 ? t.invalid : status === 429 ? t.tooMany : t.offline,
      );
    } finally {
      setBusy(false);
    }
  };

  if (user) {
    return (
      <Card title={t.account} hint={t.syncedHint}>
        <Text style={{ color: colors.text, fontWeight: "600" }}>{user.email}</Text>
        <Pressable onPress={signOut} accessibilityRole="button">
          <Text style={{ color: colors.danger }}>{t.signOut}</Text>
        </Pressable>
      </Card>
    );
  }
  return (
    <Card title={t.account} hint={t.accountHint}>
      {signupAllowed && (
        <Choices value={mode} onChange={(m) => { setMode(m); setError(null); }}
          options={[["login", t.signIn], ["signup", t.signUp]]} />
      )}
      <Field value={email} onChange={setEmail} placeholder={t.email} keyboard="email-address" autoComplete="email" />
      <Field value={password} onChange={setPassword} placeholder={t.password} secure
        autoComplete={mode === "signup" ? "new-password" : "current-password"} />
      {mode === "signup" && <Text style={[styles.hint, { color: colors.textSecondary }]}>{t.passwordHint}</Text>}
      {error && <Text style={{ color: colors.danger }}>{error}</Text>}
      <Pressable onPress={submit} disabled={busy || !email || password.length < 8} accessibilityRole="button"
        style={[styles.primary, { backgroundColor: colors.accent, opacity: busy || !email || password.length < 8 ? 0.5 : 1 }]}>
        {busy ? <ActivityIndicator color={colors.onAccent} />
          : <Text style={{ color: colors.onAccent, fontWeight: "600" }}>{mode === "signup" ? t.signUp : t.signIn}</Text>}
      </Pressable>
    </Card>
  );
}

/** Provider (from the server: only configured ones can be chosen) and its models. */
function ModelPicker({ settings, update }: { settings: Settings; update: (p: Partial<Settings>) => void }) {
  const colors = useTheme();
  const [list, setList] = useState<Provider[] | null>(null);
  const [serverDefault, setServerDefault] = useState("");
  const [modelList, setModelList] = useState<{ recommended: string | null; models: string[] } | null>(null);

  useEffect(() => {
    fetchProviders().then((r) => { setList(r.providers); setServerDefault(r.default); }, () => setList([]));
  }, []);
  const active = settings.provider || serverDefault;
  useEffect(() => {
    if (!active) return;
    let current = true;
    fetchModels(active).then((r) => current && setModelList(r), () => current && setModelList({ recommended: null, models: [] }));
    return () => { current = false; };
  }, [active]);

  if (!list) return <ActivityIndicator color={colors.accent} />;
  const usable = list.filter((p) => p.configured && !p.local); // a phone can't reach the server's localhost model
  return (
    <>
      <Label text={t.provider} />
      <Choices value={settings.provider} onChange={(provider) => update({ provider, model: "" })} wrap
        options={[["", `${t.serverDefault}`], ...usable.map((p): [string, string] => [p.id, p.label])]} />
      {!!modelList?.models.length && (
        <>
          <Label text={t.model} />
          <Choices value={settings.model} onChange={(model) => update({ model })} wrap
            options={[["", `${t.recommended}${modelList.recommended ? ` (${modelList.recommended})` : ""}`],
              ...modelList.models.slice(0, 12).map((m): [string, string] => [m, m])]} />
        </>
      )}
    </>
  );
}

function Card({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  const colors = useTheme();
  return (
    <View style={[styles.card, { backgroundColor: colors.backgroundElement }]}>
      <Text style={[styles.cardTitle, { color: colors.text }]}>{title}</Text>
      {hint && <Text style={[styles.hint, { color: colors.textSecondary }]}>{hint}</Text>}
      {children}
    </View>
  );
}

function Label({ text }: { text: string }) {
  const colors = useTheme();
  return <Text style={[styles.label, { color: colors.textSecondary }]}>{text}</Text>;
}

function Choices<T extends string>({ value, onChange, options, wrap }: {
  value: T; onChange: (v: T) => void; options: [T, string][]; wrap?: boolean;
}) {
  const colors = useTheme();
  return (
    <View style={[styles.choices, wrap && styles.wrap]} accessibilityRole="radiogroup">
      {options.map(([id, label]) => (
        <Pressable key={id || "default"} onPress={() => onChange(id)} accessibilityRole="radio"
          accessibilityState={{ selected: id === value }}
          style={[styles.choice, wrap && styles.wrapChoice, { backgroundColor: id === value ? colors.accent : colors.background }]}>
          <Text numberOfLines={1} style={{ color: id === value ? colors.onAccent : colors.text, fontWeight: "600" }}>{label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

function Field({ value, onChange, placeholder, secure, keyboard, autoComplete }: {
  value: string; onChange: (v: string) => void; placeholder: string; secure?: boolean;
  keyboard?: "email-address"; autoComplete?: "email" | "new-password" | "current-password";
}) {
  const colors = useTheme();
  return (
    <TextInput value={value} onChangeText={onChange} placeholder={placeholder} placeholderTextColor={colors.textSecondary}
      secureTextEntry={secure} keyboardType={keyboard} autoComplete={autoComplete} autoCapitalize="none" autoCorrect={false}
      style={[styles.field, { color: colors.text, backgroundColor: colors.background }]} />
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  content: { padding: 16, gap: 16, paddingBottom: 48 },
  title: { fontSize: 28, fontWeight: "700" },
  card: { padding: 16, borderRadius: 16, gap: 10 },
  cardTitle: { fontSize: 17, fontWeight: "600" },
  label: { fontSize: 13, fontWeight: "600", marginTop: 4 },
  hint: { fontSize: 13, lineHeight: 18 },
  choices: { flexDirection: "row", gap: 8 },
  wrap: { flexWrap: "wrap" },
  choice: { flex: 1, paddingVertical: 10, paddingHorizontal: 12, borderRadius: 12, alignItems: "center" },
  wrapChoice: { flex: 0 },
  field: { height: 46, borderRadius: 12, paddingHorizontal: 14, fontSize: 16 },
  primary: { height: 46, borderRadius: 12, alignItems: "center", justifyContent: "center" },
});
