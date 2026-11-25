import { router } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, TextInput } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useTheme } from "@/hooks/use-theme";
import { listLaws, type LawSummary } from "@/lib/api";
import { LANG, t } from "@/lib/i18n";

export default function LawsScreen() {
  const colors = useTheme();
  const [laws, setLaws] = useState<LawSummary[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [query, setQuery] = useState("");

  const load = () => listLaws().then(setLaws, () => setFailed(true));
  useEffect(() => {
    load();
  }, []);
  const retry = () => {
    setFailed(false);
    load();
  };

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    // French titles first in French and English, Arabic first in Arabic
    const sorted = [...(laws ?? [])].sort((a, b) => Number(a.language !== LANG.slice(0, 2) && LANG !== "en"));
    return q
      ? sorted.filter((l) => `${l.title_ar} ${l.title_fr ?? ""} ${l.law_number ?? ""}`.toLowerCase().includes(q))
      : sorted;
  }, [laws, query]);

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.background }]} edges={["top"]}>
      <Text style={[styles.title, { color: colors.text }]}>{t.laws}</Text>
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder={t.searchLaws}
        placeholderTextColor={colors.textSecondary}
        style={[styles.search, { color: colors.text, backgroundColor: colors.backgroundElement }]}
      />
      {failed ? (
        <Pressable onPress={retry} style={styles.center}>
          <Text style={{ color: colors.textSecondary }}>{t.offline}</Text>
          <Text style={{ color: colors.accent, marginTop: 8 }}>{t.retry}</Text>
        </Pressable>
      ) : !laws ? (
        <ActivityIndicator style={styles.center} color={colors.accent} />
      ) : (
        <FlatList
          data={shown}
          keyExtractor={(l) => l.slug}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <Pressable
              onPress={() => router.push({ pathname: "/law/[slug]", params: { slug: item.slug } })}
              style={[styles.row, { backgroundColor: colors.backgroundElement }]}>
              <Text style={[styles.lawTitle, { color: colors.text }]}>
                {item.language === "fr" ? item.title_fr ?? item.title_ar : item.title_ar}
              </Text>
              <Text style={{ color: colors.textSecondary, fontSize: 13 }}>
                {[item.parent_group ? t.implements : null, item.law_number, item.year, `${item.article_count} ${t.articles}`,
                  item.language.toUpperCase()].filter(Boolean).join(" · ")}
              </Text>
            </Pressable>
          )}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  title: { fontSize: 28, fontWeight: "700", paddingHorizontal: 16, paddingTop: 8 },
  search: { margin: 16, marginBottom: 8, borderRadius: 12, paddingHorizontal: 14, height: 44, fontSize: 16 },
  list: { padding: 16, paddingTop: 8, gap: 8 },
  row: { padding: 14, borderRadius: 14, gap: 4 },
  lawTitle: { fontSize: 16, fontWeight: "600" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
});
