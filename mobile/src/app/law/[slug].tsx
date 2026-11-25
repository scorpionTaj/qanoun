import { Stack, useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, Share, StyleSheet, Text, View } from "react-native";

import { useTheme } from "@/hooks/use-theme";
import type { Article, LawDetail } from "@/lib/api";
import { WEB_URL } from "@/lib/config";
import { t } from "@/lib/i18n";
import { fetchLaw, removeLaw, saveLaw, savedLaw, savedSlugs } from "@/lib/offline";

/** A whole law, article by article; opened from a citation it starts at that article.
 * A saved law shows its stored copy at once (and with no connection), refreshed when online. */
export default function LawReader() {
  const colors = useTheme();
  const { slug, article } = useLocalSearchParams<{ slug: string; article?: string }>();
  const [law, setLaw] = useState<LawDetail | null>(() => savedLaw(slug));
  const [saved, setSaved] = useState(() => savedSlugs().includes(slug));
  const [state, setState] = useState<"loading" | "online" | "offline">("loading");
  const list = useRef<FlatList<Article>>(null);

  const refresh = () =>
    fetchLaw(slug).then(
      (fresh) => {
        setLaw(fresh);
        setState("online");
      },
      () => setState("offline"),
    );
  useEffect(() => {
    refresh();
  }, [slug]); // eslint-disable-line react-hooks/exhaustive-deps
  const retry = () => {
    setState("loading");
    refresh();
  };

  const toggleSave = () => {
    if (!law) return;
    if (saved) removeLaw(slug);
    else saveLaw(law);
    setSaved(!saved);
  };

  const start = law && article ? Math.max(0, law.articles.findIndex((a) => a.number === article)) : 0;
  const jumped = useRef(false);
  const jumpToArticle = () => {
    if (jumped.current || !start) return;
    jumped.current = true;
    list.current?.scrollToIndex({ index: start, animated: false });
  };
  const title = law ? (law.language === "fr" ? law.title_fr ?? law.title_ar : law.title_ar) : "";
  const word = law?.language === "fr" ? "Article" : t.article;
  const share = (a: Article) =>
    Share.share({
      message: `${title} — ${word} ${a.number}\n\n${a.text}\n\n${WEB_URL}/${law?.language === "fr" ? "fr" : "ar"}/laws/${slug}#article-${a.number}`,
    });

  if (!law && state === "offline") {
    return (
      <Pressable onPress={retry} style={[styles.center, { backgroundColor: colors.background }]}>
        <Text style={{ color: colors.textSecondary }}>{t.offline}</Text>
        <Text style={{ color: colors.accent, marginTop: 8 }}>{t.retry}</Text>
      </Pressable>
    );
  }
  return (
    <View style={[styles.screen, { backgroundColor: colors.background }]}>
      <Stack.Screen
        options={{
          title,
          headerRight: () =>
            law && (
              <Pressable onPress={toggleSave} accessibilityRole="button" hitSlop={10}>
                <Text style={{ color: colors.accent, fontWeight: "600" }}>{saved ? t.savedOffline : t.saveOffline}</Text>
              </Pressable>
            ),
        }}
      />
      {!law ? (
        <ActivityIndicator style={styles.center} color={colors.accent} />
      ) : (
        <FlatList
          ref={list}
          data={law.articles}
          keyExtractor={(a) => String(a.id)}
          onContentSizeChange={jumpToArticle}
          onScrollToIndexFailed={({ index, averageItemLength }) => {
            // not rendered yet (articles vary in height): get close, then retry once it is
            list.current?.scrollToOffset({ offset: index * averageItemLength, animated: false });
            setTimeout(() => list.current?.scrollToIndex({ index, animated: false }), 150);
          }}
          contentContainerStyle={styles.list}
          ListHeaderComponent={
            <Text style={[styles.hint, { color: colors.textSecondary }]}>
              {state === "offline" ? t.offlineCopy : t.shareHint}
            </Text>
          }
          renderItem={({ item }) => (
            <Pressable
              onLongPress={() => share(item)}
              accessibilityHint={t.shareHint}
              style={[styles.article, {
                backgroundColor: colors.backgroundElement,
                borderColor: item.number === article ? colors.accent : "transparent",
              }]}>
              <Text style={[styles.number, { color: colors.accent }]}>{word} {item.number}</Text>
              <Text style={[styles.text, { color: colors.text }]}>{item.text}</Text>
            </Pressable>
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
  hint: { fontSize: 12, textAlign: "center" },
  article: { padding: 14, borderRadius: 14, borderWidth: 2, gap: 6 },
  number: { fontWeight: "700" },
  text: { fontSize: 16, lineHeight: 26 },
});
