// Release builds signed with the upload key from the environment, when it is set:
//   ANDROID_KEYSTORE_PATH, ANDROID_KEYSTORE_PASSWORD, ANDROID_KEY_ALIAS, ANDROID_KEY_PASSWORD
// Without it they fall back to the debug key (fine for sideloading, refused by the Play Store).
const { withAppBuildGradle } = require("expo/config-plugins");

const RELEASE = `
        release {
            if (System.getenv("ANDROID_KEYSTORE_PATH")) {
                storeFile file(System.getenv("ANDROID_KEYSTORE_PATH"))
                storePassword System.getenv("ANDROID_KEYSTORE_PASSWORD")
                keyAlias System.getenv("ANDROID_KEY_ALIAS")
                keyPassword System.getenv("ANDROID_KEY_PASSWORD")
            }
        }`;
const RELEASE_BUILD = /(release \{\n(?:\s*\/\/.*\n)*\s*)signingConfig signingConfigs\.debug/;

module.exports = (config) =>
  withAppBuildGradle(config, (config) => {
    let gradle = config.modResults.contents;
    if (gradle.includes('System.getenv("ANDROID_KEYSTORE_PATH")')) return config;
    if (!gradle.includes("signingConfigs {") || !RELEASE_BUILD.test(gradle))
      throw new Error("with-release-signing: app/build.gradle layout changed, update the plugin");
    gradle = gradle.replace("signingConfigs {", `signingConfigs {${RELEASE}`);
    gradle = gradle.replace(
      RELEASE_BUILD,
      '$1signingConfig System.getenv("ANDROID_KEYSTORE_PATH") ? signingConfigs.release : signingConfigs.debug',
    );
    config.modResults.contents = gradle;
    return config;
  });
