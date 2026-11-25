import { reloadAppAsync } from "expo";
import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from "expo-router";
import { useEffect } from "react";
import { I18nManager, Platform, useColorScheme } from "react-native";

import { isRtl, LANG } from "@/lib/i18n";

/** Arabic lays the whole app out right to left. React Native applies a direction change only
 * after a restart, so when the stored language and the layout disagree, flip and reload once. */
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
  const scheme = useColorScheme();
  useLayoutDirection();
  return (
    <ThemeProvider value={scheme === "dark" ? DarkTheme : DefaultTheme}>
      <Stack>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="law/[slug]" options={{ title: "" }} />
      </Stack>
    </ThemeProvider>
  );
}
