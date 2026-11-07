import { getTranslations } from "next-intl/server";
import { ShieldAlert } from "lucide-react";
import { Separator } from "@/components/ui/heroui";

export async function Footer() {
  const t = await getTranslations("app");
  const h = await getTranslations("home");

  return (
    <footer className="mt-16">
      <Separator />
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 text-sm md:flex-row md:items-center md:justify-between">
        <p className="flex max-w-xl items-start gap-2 text-muted">
          <ShieldAlert className="mt-0.5 size-4 shrink-0 text-saffron-700 dark:text-saffron-300" aria-hidden />
          {h("disclaimer")}
        </p>
        <p className="text-muted">{t("footer")}</p>
      </div>
    </footer>
  );
}
