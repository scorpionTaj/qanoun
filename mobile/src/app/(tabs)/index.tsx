import { router } from "expo-router";
import { useRef, useState } from "react";
import {
  ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, type ScrollViewInstance, StyleSheet, Text,
  TextInput, View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useTheme } from "@/hooks/use-theme";
import { ask, type Source, type Turn } from "@/lib/api";
import { t } from "@/lib/i18n";

interface Message {
  role: "user" | "assistant";
  text: string;
  stage?: string;
  sources?: Source[];
  cited?: number[]; // 0-based indexes into sources: «[2]» in the text is 1
  disclaimer?: string;
  error?: boolean;
  streaming?: boolean;
}

const STAGE: Record<string, string> = { rewriting: t.rewriting, searching: t.searching, answering: t.answering };

export default function AskScreen() {
  const colors = useTheme();
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const abort = useRef<AbortController | null>(null);
  const scroll = useRef<ScrollViewInstance>(null);
  const busy = messages.at(-1)?.streaming ?? false;

  const update = (patch: Partial<Message> | ((m: Message) => Partial<Message>)) =>
    setMessages((list) => {
      const last = list[list.length - 1];
      return [...list.slice(0, -1), { ...last, ...(typeof patch === "function" ? patch(last) : patch) }];
    });

  const send = async (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    const history: Turn[] = messages.filter((m) => !m.error && m.text).map(({ role, text }) => ({ role, text }));
    setMessages((list) => [...list, { role: "user", text: q }, { role: "assistant", text: "", streaming: true }]);
    setQuestion("");
    abort.current = new AbortController();
    try {
      for await (const u of ask(q, history, "auto", abort.current.signal)) {
        if (u.kind === "stage") update({ stage: u.stage });
        else if (u.kind === "meta") update({ disclaimer: u.disclaimer });
        else if (u.kind === "sources") update({ sources: u.sources });
        else if (u.kind === "token") update((m) => ({ text: m.text + u.text, stage: undefined }));
        else if (u.kind === "done") update({ text: u.text, cited: u.cited, streaming: false, stage: undefined });
        else if (u.kind === "error")
          update({ text: u.code === "rate_limited" ? t.rateLimited : t.failed, error: true, streaming: false });
      }
    } catch {
      update((m) => (abort.current?.signal.aborted ? { streaming: false } : { text: t.failed, error: true, streaming: false }));
    } finally {
      update({ streaming: false, stage: undefined });
    }
  };

  const openSource = (source: Source) =>
    router.push({ pathname: "/law/[slug]", params: { slug: source.law_slug, article: source.article_number ?? "" } });

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.background }]} edges={["top"]}>
      <KeyboardAvoidingView style={styles.screen} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <View style={styles.header}>
          <Text style={[styles.brand, { color: colors.text }]}>قانون · Qanoun</Text>
          {messages.length > 0 && !busy && (
            <Pressable onPress={() => setMessages([])} accessibilityRole="button">
              <Text style={{ color: colors.accent }}>{t.newChat}</Text>
            </Pressable>
          )}
        </View>
        <ScrollView
          ref={scroll}
          contentContainerStyle={styles.thread}
          onContentSizeChange={() => scroll.current?.scrollToEnd({ animated: true })}
          keyboardShouldPersistTaps="handled">
          {messages.length === 0 ? (
            <View style={styles.empty}>
              <Text style={[styles.welcome, { color: colors.textSecondary }]}>{t.welcome}</Text>
              {t.examples.map((example) => (
                <Pressable key={example} onPress={() => send(example)}
                  style={[styles.example, { backgroundColor: colors.backgroundElement }]}>
                  <Text style={{ color: colors.text }}>{example}</Text>
                </Pressable>
              ))}
            </View>
          ) : (
            messages.map((m, i) => (
              <Bubble key={i} message={m} onSource={openSource} />
            ))
          )}
        </ScrollView>
        <View style={[styles.composer, { borderColor: colors.backgroundSelected, backgroundColor: colors.background }]}>
          <TextInput
            value={question}
            onChangeText={setQuestion}
            placeholder={t.placeholder}
            placeholderTextColor={colors.textSecondary}
            style={[styles.input, { color: colors.text, backgroundColor: colors.backgroundElement }]}
            multiline
            maxLength={1000}
          />
          <Pressable
            onPress={() => (busy ? abort.current?.abort() : send(question))}
            accessibilityRole="button"
            style={[styles.send, { backgroundColor: busy ? colors.danger : colors.accent }]}>
            <Text style={{ color: colors.onAccent, fontWeight: "600" }}>{busy ? t.stop : t.send}</Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function Bubble({ message: m, onSource }: { message: Message; onSource: (s: Source) => void }) {
  const colors = useTheme();
  if (m.role === "user") {
    return (
      <View style={[styles.user, { backgroundColor: colors.accent }]}>
        <Text style={{ color: colors.onAccent }}>{m.text}</Text>
      </View>
    );
  }
  const cited = (m.cited ?? []).filter((i) => m.sources?.[i]).map((i) => ({ n: i + 1, source: m.sources![i] }));
  return (
    <View style={[styles.answer, { backgroundColor: colors.backgroundElement }]}>
      {m.streaming && !m.text && (
        <View style={styles.stage}>
          <ActivityIndicator color={colors.accent} />
          <Text style={{ color: colors.textSecondary }}>{STAGE[m.stage ?? "searching"] ?? t.searching}</Text>
        </View>
      )}
      {!!m.text && <Text selectable style={{ color: m.error ? colors.danger : colors.text, lineHeight: 22 }}>{m.text}</Text>}
      {cited.length > 0 && (
        <View style={styles.sources}>
          <Text style={[styles.sourcesTitle, { color: colors.textSecondary }]}>{t.sources}</Text>
          {cited.map(({ n, source }) => (
            <Pressable key={n} onPress={() => onSource(source)} accessibilityRole="link"
              style={[styles.source, { borderColor: colors.backgroundSelected }]}>
              <Text style={{ color: colors.accent }}>
                [{n}] {source.language === "fr" ? source.law_title_fr ?? source.law_title : source.law_title}
                {source.article_number ? ` — ${source.language === "fr" ? "Article" : "المادة"} ${source.article_number}` : ""}
              </Text>
            </Pressable>
          ))}
        </View>
      )}
      {!m.streaming && !m.error && !!m.disclaimer && (
        <Text style={[styles.disclaimer, { color: colors.textSecondary }]}>{m.disclaimer}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: 16, paddingVertical: 10 },
  brand: { fontSize: 20, fontWeight: "700" },
  thread: { padding: 16, gap: 12, flexGrow: 1 },
  empty: { flex: 1, justifyContent: "center", gap: 10 },
  welcome: { fontSize: 16, lineHeight: 24, marginBottom: 8, textAlign: "center" },
  example: { padding: 14, borderRadius: 14 },
  user: { alignSelf: "flex-end", maxWidth: "85%", padding: 12, borderRadius: 16 },
  answer: { alignSelf: "stretch", padding: 14, borderRadius: 16, gap: 10 },
  stage: { flexDirection: "row", gap: 8, alignItems: "center" },
  sources: { gap: 6 },
  sourcesTitle: { fontSize: 12, fontWeight: "600" },
  source: { borderWidth: StyleSheet.hairlineWidth, borderRadius: 10, padding: 10 },
  disclaimer: { fontSize: 12 },
  composer: { flexDirection: "row", gap: 8, padding: 12, borderTopWidth: StyleSheet.hairlineWidth, alignItems: "flex-end" },
  input: { flex: 1, minHeight: 44, maxHeight: 140, borderRadius: 14, paddingHorizontal: 14, paddingVertical: 10, fontSize: 16 },
  send: { height: 44, paddingHorizontal: 16, borderRadius: 14, justifyContent: "center" },
});
