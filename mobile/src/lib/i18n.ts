/** Arabic (default, right to left), French and English, like the web app.
 * The language follows the device unless chosen in Settings (stored on the device). */
import { getLocales } from "expo-localization";
import * as SecureStore from "expo-secure-store";

export type Lang = "ar" | "fr" | "en";
const KEY = "qanoun.language";

const messages = {
  ar: {
    ask: "اسأل", laws: "القوانين", settings: "الإعدادات",
    placeholder: "اطرح سؤالك عن القانون المغربي…", send: "إرسال", stop: "إيقاف",
    welcome: "اسأل بالعربية أو الدارجة أو الفرنسية. الجواب من النصوص الرسمية، مع ذكر المواد.",
    examples: ["ما هي شروط الزواج؟", "شحال مدة الكونجي ديال الولادة؟", "Quel est le salaire minimum ?"],
    rewriting: "فهم السؤال…", searching: "البحث في النصوص…", answering: "كتابة الجواب…",
    sources: "المصادر", noAnswer: "لا جواب في النصوص المتوفرة.",
    rateLimited: "أسئلة كثيرة في وقت قصير. حاول بعد دقيقة.", failed: "تعذر الحصول على جواب. حاول مرة أخرى.",
    newChat: "محادثة جديدة", searchLaws: "ابحث عن قانون…", articles: "مادة", article: "المادة",
    loading: "جار التحميل…", offline: "تعذر الاتصال بالخادم.", retry: "إعادة المحاولة",
    language: "اللغة", languageHint: "تغيير اللغة يعيد تشغيل التطبيق لقلب اتجاه الكتابة.",
    about: "حول قانون", disclaimer: "معلومات قانونية وليست استشارة قانونية. الجريدة الرسمية هي المرجع.",
    openWeb: "فتح الموقع", implements: "مرسوم تطبيقي",
  },
  fr: {
    ask: "Demander", laws: "Lois", settings: "Réglages",
    placeholder: "Posez votre question sur le droit marocain…", send: "Envoyer", stop: "Arrêter",
    welcome: "Posez votre question en arabe, en darija ou en français : la réponse cite les articles des textes officiels.",
    examples: ["Quelles sont les conditions du mariage ?", "Quelle est la durée du congé de maternité ?", "ما هي شروط الزواج؟"],
    rewriting: "Compréhension de la question…", searching: "Recherche dans les textes…", answering: "Rédaction de la réponse…",
    sources: "Sources", noAnswer: "Pas de réponse dans les textes disponibles.",
    rateLimited: "Trop de questions : réessayez dans une minute.", failed: "Impossible d'obtenir une réponse. Réessayez.",
    newChat: "Nouvelle conversation", searchLaws: "Chercher une loi…", articles: "articles", article: "Article",
    loading: "Chargement…", offline: "Impossible de joindre le serveur.", retry: "Réessayer",
    language: "Langue", languageHint: "Changer de langue redémarre l'application pour changer le sens d'écriture.",
    about: "À propos", disclaimer: "Information juridique, pas un conseil juridique. Le Bulletin officiel fait foi.",
    openWeb: "Ouvrir le site", implements: "Décret d'application",
  },
  en: {
    ask: "Ask", laws: "Laws", settings: "Settings",
    placeholder: "Ask about Moroccan law…", send: "Send", stop: "Stop",
    welcome: "Ask in Arabic, Darija, French or English: answers cite the articles of the official texts.",
    examples: ["What are the conditions for marriage?", "How long is maternity leave?", "ما هي شروط الزواج؟"],
    rewriting: "Understanding the question…", searching: "Searching the texts…", answering: "Writing the answer…",
    sources: "Sources", noAnswer: "No answer in the available texts.",
    rateLimited: "Too many questions: try again in a minute.", failed: "Couldn't get an answer. Try again.",
    newChat: "New conversation", searchLaws: "Search a law…", articles: "articles", article: "Article",
    loading: "Loading…", offline: "Couldn't reach the server.", retry: "Retry",
    language: "Language", languageHint: "Changing the language restarts the app to switch the writing direction.",
    about: "About", disclaimer: "Legal information, not legal advice. The Official Bulletin is the reference.",
    openWeb: "Open the website", implements: "Implementing decree",
  },
};

export type Messages = (typeof messages)["ar"];

function deviceLanguage(): Lang {
  const code = getLocales()[0]?.languageCode;
  return code === "fr" || code === "en" ? code : "ar"; // Arabic for any other language, like the web
}

export function storedLanguage(): Lang {
  const saved = SecureStore.getItem(KEY);
  return saved === "ar" || saved === "fr" || saved === "en" ? saved : deviceLanguage();
}

export function saveLanguage(lang: Lang): void {
  SecureStore.setItem(KEY, lang);
}

export const LANG: Lang = storedLanguage();
export const t: Messages = messages[LANG];
export const isRtl = (lang: Lang) => lang === "ar";
