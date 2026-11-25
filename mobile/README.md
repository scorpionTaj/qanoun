# Qanoun mobile (Expo)

The Qanoun app for iOS and Android: ask about Moroccan law and get a streamed answer that
cites the articles, browse the laws, read them article by article. Same API as the web app.

- **Ask**: the answer streams in («searching the texts…» → text), with the cited articles
  under it; tap one to open the law at that article. Follow-up questions keep the context.
- **Laws**: every law and implementing decree, searchable by title or number. **Save** a law
  to read it with no connection (the saved copy refreshes when online); long-press an article
  to share it with its link.
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

`ios/` and `android/` are generated from `app.json` (`npx expo prebuild`), never edited by hand.

## Release builds

Pushing a tag `v1.2.3` builds the Android app in GitHub Actions (`.github/workflows/release.yml`)
and attaches `qanoun-1.2.3.apk` (install directly) and `qanoun-1.2.3.aab` (Play Store) to the
GitHub release. The build number is the workflow run number, so it always goes up.

They are signed with your upload key when these repository secrets are set, otherwise with the
debug key (installs fine, refused by the Play Store):

```bash
keytool -genkeypair -v -storetype PKCS12 -keystore qanoun-upload.jks -alias qanoun \
  -keyalg RSA -keysize 2048 -validity 10000          # keep this file and its password safe
gh secret set ANDROID_KEYSTORE_BASE64 < <(base64 -i qanoun-upload.jks)
gh secret set ANDROID_KEYSTORE_PASSWORD
gh secret set ANDROID_KEY_ALIAS --body qanoun
gh secret set ANDROID_KEY_PASSWORD                  # same as the keystore password for PKCS12
```

The same build locally (the plugin in `plugins/with-release-signing.js` reads the same
variables; without them it uses the debug key):

```bash
npx expo prebuild --platform android
ANDROID_KEYSTORE_PATH=$PWD/qanoun-upload.jks ANDROID_KEYSTORE_PASSWORD=… ANDROID_KEY_ALIAS=qanoun \
  ANDROID_KEY_PASSWORD=… ./android/gradlew -p android assembleRelease
```

iOS needs an Apple developer account; build it with EAS (`npx eas-cli@latest build -p ios`).

## Notes

- Streaming uses `expo/fetch` (its body is a readable stream on iOS and Android); the parser
  in `src/lib/sse.ts` is the web app's.
- Not yet: push notifications, iOS release builds in CI.
