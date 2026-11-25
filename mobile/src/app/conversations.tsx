import { router } from "expo-router";
import { Alert, FlatList, Pressable, StyleSheet, Text, View } from "react-native";

import { useTheme } from "@/hooks/use-theme";
import { useApp } from "@/lib/app-state";
import { LANG, t } from "@/lib/i18n";

/** Saved conversations, newest first: tap to reopen, long-press to delete. */
export default function ConversationsScreen() {
  const colors = useTheme();
  const { conversations, deleteConversation } = useApp();
  const date = (ms: number) => new Date(ms).toLocaleDateString(LANG, { day: "numeric", month: "short" });

  const confirmDelete = (id: string, title: string) =>
    Alert.alert(title || t.history, undefined, [
      { text: t.cancel, style: "cancel" },
      { text: t.delete, style: "destructive", onPress: () => deleteConversation(id) },
    ]);

  return (
    <FlatList
      style={{ backgroundColor: colors.background }}
      contentContainerStyle={styles.list}
      data={conversations.filter((c) => c.messages.length)}
      keyExtractor={(c) => c.id}
      ListEmptyComponent={<Text style={[styles.empty, { color: colors.textSecondary }]}>{t.noConversations}</Text>}
      renderItem={({ item }) => (
        <Pressable
          onPress={() => router.navigate({ pathname: "/", params: { id: item.id } })}
          onLongPress={() => confirmDelete(item.id, item.title)}
          style={[styles.row, { backgroundColor: colors.backgroundElement }]}>
          <Text numberOfLines={2} style={[styles.title, { color: colors.text }]}>{item.title || "…"}</Text>
          <View style={styles.meta}>
            <Text style={{ color: colors.textSecondary, fontSize: 12 }}>{date(item.updatedAt)}</Text>
            <Text style={{ color: colors.textSecondary, fontSize: 12 }}>{Math.ceil(item.messages.length / 2)} ✦</Text>
          </View>
        </Pressable>
      )}
    />
  );
}

const styles = StyleSheet.create({
  list: { padding: 16, gap: 8 },
  empty: { textAlign: "center", marginTop: 48 },
  row: { padding: 14, borderRadius: 14, gap: 6 },
  title: { fontSize: 16, fontWeight: "500" },
  meta: { flexDirection: "row", justifyContent: "space-between" },
});
