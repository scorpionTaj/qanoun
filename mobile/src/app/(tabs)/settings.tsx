import { reloadAppAsync } from "expo";
import * as WebBrowser from "expo-web-browser";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useTheme } from "@/hooks/use-theme";
import { WEB_URL } from "@/lib/config";
import { LANG, type Lang, saveLanguage, t } from "@/lib/i18n";

const LANGUAGES: { id: Lang; label: string }[] = [
  { id: "ar", label: "العربية" },
  { id: "fr", label: "Français" },
  { id: "en", label: "English" },
];

export default function SettingsScreen() {
  const colors = useTheme();
  const choose = (lang: Lang) => {
    if (lang === LANG) return;
    saveLanguage(lang);
    reloadAppAsync("language"); // the root layout flips the layout direction on the way up
  };
  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.background }]} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={[styles.title, { color: colors.text }]}>{t.settings}</Text>
        <View style={[styles.card, { backgroundColor: colors.backgroundElement }]}>
          <Text style={[styles.label, { color: colors.text }]}>{t.language}</Text>
          <View style={styles.choices}>
            {LANGUAGES.map(({ id, label }) => (
              <Pressable key={id} onPress={() => choose(id)} accessibilityRole="radio" accessibilityState={{ selected: id === LANG }}
                style={[styles.choice, { backgroundColor: id === LANG ? colors.accent : colors.background }]}>
                <Text style={{ color: id === LANG ? colors.onAccent : colors.text, fontWeight: "600" }}>{label}</Text>
              </Pressable>
            ))}
          </View>
          <Text style={{ color: colors.textSecondary, fontSize: 13 }}>{t.languageHint}</Text>
        </View>
        <View style={[styles.card, { backgroundColor: colors.backgroundElement }]}>
          <Text style={[styles.label, { color: colors.text }]}>{t.about}</Text>
          <Text style={{ color: colors.textSecondary, lineHeight: 20 }}>{t.disclaimer}</Text>
          <Pressable onPress={() => WebBrowser.openBrowserAsync(`${WEB_URL}/${LANG}`)} accessibilityRole="link">
            <Text style={{ color: colors.accent }}>{t.openWeb}</Text>
          </Pressable>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  content: { padding: 16, gap: 16 },
  title: { fontSize: 28, fontWeight: "700" },
  card: { padding: 16, borderRadius: 16, gap: 12 },
  label: { fontSize: 17, fontWeight: "600" },
  choices: { flexDirection: "row", gap: 8 },
  choice: { flex: 1, paddingVertical: 10, borderRadius: 12, alignItems: "center" },
});
