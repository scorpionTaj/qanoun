import { getTranslations } from "next-intl/server";
import { Github, ShieldAlert } from "lucide-react";

export async function Footer() {
  const t = await getTranslations("app");
  const h = await getTranslations("home");

  return (
    <footer className="border-t border-zellige-100 bg-white dark:border-zellige-800 dark:bg-[#0e1915]">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 md:flex-row md:items-center md:justify-between">
        <div className="flex items-start gap-2 text-sm text-zellige-600 dark:text-zellige-300">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-sand-600 dark:text-sand-400" />
          <p className="max-w-xl">{h("disclaimer")}</p>
        </div>
        <div className="flex items-center gap-3 text-sm text-zellige-500 dark:text-zellige-400">
          <p>{t("footer")}</p>
          <Github className="h-4 w-4" />
        </div>
      </div>
    </footer>
  );
}
