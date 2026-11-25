/** Where the app talks to. Override at build time with EXPO_PUBLIC_API_URL / EXPO_PUBLIC_WEB_URL. */
export const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? "https://qanoun-api.vercel.app").replace(/\/$/, "");
export const WEB_URL = (process.env.EXPO_PUBLIC_WEB_URL ?? "https://qanoun-ma.vercel.app").replace(/\/$/, "");
