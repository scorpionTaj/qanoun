import { reloadAppAsync } from "expo";
import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from "expo-router";
import { useEffect } from "react";
import { I18nManager, Platform, useColorScheme } from "react-native";

import { AppProvider } from "@/lib/app-state";
import { isRtl, LANG, t } from "@/lib/i18n";

/** Arabic lays the whole app out right to left. React Native applies a direction change only
 * after a restart, so when the language and the layout disagree, flip and reload once. */
function useLayoutDirection() {
  useEffect(() => {
    const rtl = isRtl(LANG);
    if (Platform.OS !== "web" && I18nManager.isRTL !== rtl) {
      I18nManager.allowRTL(rtl);
      I18nManager.forceRTL(rtl);
      reloadAppAsync("layout direction");
    }
  }, []);
}

export default function RootLayout() {
  useLayoutDirection();
  return (
    <AppProvider>
      <Themed />
    </AppProvider>
  );
}

function Themed() {
  const scheme = useColorScheme(); // follows the Appearance setting (app-state applies it)
  return (
    <ThemeProvider value={scheme === "dark" ? DarkTheme : DefaultTheme}>
      <Stack>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="law/[slug]" options={{ title: "" }} />
        <Stack.Screen name="conversations" options={{ title: t.history }} />
      </Stack>
    </ThemeProvider>
  );
}
