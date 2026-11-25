import { Stack, useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, View } from "react-native";

import { useTheme } from "@/hooks/use-theme";
import { getLaw, type LawDetail } from "@/lib/api";
import { t } from "@/lib/i18n";

/** A whole law, article by article; opened from a citation it starts at that article. */
export default function LawReader() {
  const colors = useTheme();
  const { slug, article } = useLocalSearchParams<{ slug: string; article?: string }>();
  const [law, setLaw] = useState<LawDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const list = useRef<FlatList>(null);

  useEffect(() => {
    getLaw(slug).then(setLaw, () => setFailed(true));
  }, [slug]);
  const retry = () => {
    setFailed(false);
    getLaw(slug).then(setLaw, () => setFailed(true));
  };

  const start = law && article ? Math.max(0, law.articles.findIndex((a) => a.number === article)) : 0;
  const title = law ? (law.language === "fr" ? law.title_fr ?? law.title_ar : law.title_ar) : "";
  const word = law?.language === "fr" ? "Article" : t.article;

  if (failed) {
    return (
      <Pressable onPress={retry} style={[styles.center, { backgroundColor: colors.background }]}>
        <Text style={{ color: colors.textSecondary }}>{t.offline}</Text>
        <Text style={{ color: colors.accent, marginTop: 8 }}>{t.retry}</Text>
      </Pressable>
    );
  }
  return (
    <View style={[styles.screen, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ title }} />
      {!law ? (
        <ActivityIndicator style={styles.center} color={colors.accent} />
      ) : (
        <FlatList
          ref={list}
          data={law.articles}
          keyExtractor={(a) => String(a.id)}
          initialScrollIndex={start}
          onScrollToIndexFailed={({ index }) => setTimeout(() => list.current?.scrollToIndex({ index }), 100)}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <View style={[styles.article, {
              backgroundColor: colors.backgroundElement,
              borderColor: item.number === article ? colors.accent : "transparent",
            }]}>
              <Text style={[styles.number, { color: colors.accent }]}>{word} {item.number}</Text>
              <Text selectable style={[styles.text, { color: colors.text }]}>{item.text}</Text>
            </View>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  list: { padding: 16, gap: 10 },
  article: { padding: 14, borderRadius: 14, borderWidth: 2, gap: 6 },
  number: { fontWeight: "700" },
  text: { fontSize: 16, lineHeight: 26 },
});
