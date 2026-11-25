/** Small on-device store (SQLite key-value) for settings and conversations, read synchronously
 * at start-up. The session token is not here: it lives in the keychain (session.ts). */
import Storage from "expo-sqlite/kv-store";

export function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = Storage.getItemSync(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function writeJson(key: string, value: unknown): void {
  Storage.setItemSync(key, JSON.stringify(value));
}

export function removeKey(key: string): void {
  Storage.removeItemSync(key);
}
