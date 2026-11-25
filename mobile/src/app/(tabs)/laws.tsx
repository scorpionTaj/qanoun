import { router, useFocusEffect } from "expo-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useTheme } from "@/hooks/use-theme";
import type { LawSummary } from "@/lib/api";
import { LANG, t } from "@/lib/i18n";
import { loadLaws, savedSlugs } from "@/lib/offline";

export default function LawsScreen() {
  const colors = useTheme();
  const [laws, setLaws] = useState<LawSummary[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [offline, setOffline] = useState(false);
  const [query, setQuery] = useState("");
  const [onlySaved, setOnlySaved] = useState(false);
  const [saved, setSaved] = useState<string[]>(savedSlugs);
  useFocusEffect(useCallback(() => setSaved(savedSlugs()), [])); // saving happens in the reader

  const load = () =>
    loadLaws().then(
      (result) => {
        setLaws(result.laws);
        setOffline(result.offline);
      },
      () => setFailed(true),
    );
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
    const pool = onlySaved ? (laws ?? []).filter((l) => saved.includes(l.slug)) : laws ?? [];
    const sorted = [...pool].sort((a, b) => Number(a.language !== LANG.slice(0, 2) && LANG !== "en"));
    return q
      ? sorted.filter((l) => `${l.title_ar} ${l.title_fr ?? ""} ${l.law_number ?? ""}`.toLowerCase().includes(q))
      : sorted;
  }, [laws, query, onlySaved, saved]);

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
      <View style={styles.filters}>
        {([[false, t.all], [true, `${t.saved} (${saved.length})`]] as const).map(([value, label]) => (
          <Pressable key={label} onPress={() => setOnlySaved(value)} accessibilityRole="button"
            accessibilityState={{ selected: onlySaved === value }}
            style={[styles.chip, { backgroundColor: onlySaved === value ? colors.accent : colors.backgroundElement }]}>
            <Text style={{ color: onlySaved === value ? colors.onAccent : colors.text }}>{label}</Text>
          </Pressable>
        ))}
      </View>
      {offline && <Text style={[styles.note, { color: colors.textSecondary }]}>{t.offlineList}</Text>}
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
          ListEmptyComponent={onlySaved && !query ? (
            <Text style={[styles.note, { color: colors.textSecondary }]}>{t.noSaved}</Text>
          ) : undefined}
          renderItem={({ item }) => (
            <Pressable
              onPress={() => router.push({ pathname: "/law/[slug]", params: { slug: item.slug } })}
              style={[styles.row, { backgroundColor: colors.backgroundElement }]}>
              <Text style={[styles.lawTitle, { color: colors.text }]}>
                {item.language === "fr" ? item.title_fr ?? item.title_ar : item.title_ar}
              </Text>
              <Text style={{ color: colors.textSecondary, fontSize: 13 }}>
                {[item.parent_group ? t.implements : null, item.law_number, item.year, `${item.article_count} ${t.articles}`,
                  item.language.toUpperCase(), saved.includes(item.slug) ? t.savedOffline : null].filter(Boolean).join(" · ")}
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
  filters: { flexDirection: "row", gap: 8, paddingHorizontal: 16 },
  chip: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 16 },
  note: { fontSize: 13, paddingHorizontal: 16, paddingTop: 8, textAlign: "center" },
  list: { padding: 16, paddingTop: 8, gap: 8 },
  row: { padding: 14, borderRadius: 14, gap: 4 },
  lawTitle: { fontSize: 16, fontWeight: "600" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
});
