# Qanoun mobile (Expo)

The Qanoun app for iOS and Android: ask about Moroccan law and get a streamed answer that
cites the articles, browse the laws, read them article by article. Same API as the web app.

- **Ask**: the answer streams in («searching the texts…» → text), with the cited articles
  under it; tap one to open the law at that article. Follow-up questions keep the context.
- **Laws**: every law and implementing decree, searchable by title or number.
- **Settings**: Arabic (right to left), French or English. The device language is the
  default; switching restarts the app, because React Native applies a layout direction at start.

## Run it

```bash
cd mobile
npm ci
npx expo start          # scan the QR code with Expo Go (SDK 58) on your phone
```

It talks to the live API by default. Point it elsewhere at build time:
`EXPO_PUBLIC_API_URL=http://<your-lan-ip>:8000 EXPO_PUBLIC_WEB_URL=http://<ip>:3000 npx expo start`.

Checks: `npm run typecheck`, `npm run lint`, `npm test` (the SSE parser).

Builds for the stores go through EAS (`npx eas-cli@latest build`); `ios/` and `android/`
are generated from `app.json`, never edited by hand.

## Notes

- Streaming uses `expo/fetch` (its body is a readable stream on iOS and Android); the parser
  in `src/lib/sse.ts` is the web app's.
- Not yet: accounts and synced conversations, saved laws offline, push notifications.
