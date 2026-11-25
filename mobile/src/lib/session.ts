/** The account session token (from sign-in with "client": "app"), kept in the keychain and
 * sent as X-Qanoun-Session. Synchronous reads: every API call needs it. */
import * as SecureStore from "expo-secure-store";

const KEY = "qanoun.session";

export const getSession = (): string | null => SecureStore.getItem(KEY);
export const setSession = (token: string | null): void =>
  token ? SecureStore.setItem(KEY, token) : void SecureStore.deleteItemAsync(KEY);
