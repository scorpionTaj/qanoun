"use client";

import { Disclosure } from "@heroui/react";
import { useTranslations } from "next-intl";
import { History } from "lucide-react";
import type { Amendments as AmendmentsData } from "@/lib/types";

/** Amending texts named in the law's own footnotes, each linking to the articles it changed. */
export function Amendments({ data }: { data: AmendmentsData }) {
  const t = useTranslations("reader");
  if (!data.laws.length) return null;
  return (
    <Disclosure className="mt-4 rounded-[var(--radius)] border border-separator bg-surface">
      <Disclosure.Heading>
        <Disclosure.Trigger className="flex w-full items-center justify-between gap-2 px-5 py-4 text-start font-semibold">
          <span className="flex items-center gap-2">
            <History className="size-4 text-accent" aria-hidden />
            {t("amendments", { count: data.laws.length })}
          </span>
          <Disclosure.Indicator />
        </Disclosure.Trigger>
      </Disclosure.Heading>
      <Disclosure.Content>
        <Disclosure.Body className="flex flex-col gap-3 px-5 pb-5">
          <p className="text-sm text-muted">{t("amendmentsHint")}</p>
          <ul className="flex flex-col divide-y divide-separator">
            {data.laws.map((law) => (
              <li key={law.ref} className="flex flex-col gap-1.5 py-2.5 sm:flex-row sm:items-baseline sm:gap-4">
                <span className="shrink-0 font-semibold tabular-nums sm:w-40" dir="ltr">
                  {t("amendingText", { ref: law.ref })}
                </span>
                {law.articles.length ? (
                  <span className="flex flex-wrap gap-1.5">
                    {law.articles.map((number) => (
                      <a
                        key={number}
                        href={`#article-${encodeURIComponent(number)}`}
                        className="rounded-md bg-accent/10 px-1.5 py-0.5 text-xs font-medium tabular-nums text-accent hover:bg-accent/20"
                      >
                        {number}
                      </a>
                    ))}
                  </span>
                ) : (
                  <span className="text-sm text-muted">{t("amendmentsGeneral")}</span>
                )}
              </li>
            ))}
          </ul>
        </Disclosure.Body>
      </Disclosure.Content>
    </Disclosure>
  );
}
