"use client";

import { Disclosure } from "@heroui/react";

export function Preamble({ title, text, isArabic }: { title: string; text: string; isArabic: boolean }) {
  return (
    <Disclosure className="mt-6 rounded-[var(--radius)] bg-saffron-50 text-saffron-900 dark:bg-saffron-900/20 dark:text-saffron-100">
      <Disclosure.Heading>
        <Disclosure.Trigger className="flex w-full items-center justify-between gap-2 px-5 py-4 text-start font-semibold">
          {title}
          <Disclosure.Indicator />
        </Disclosure.Trigger>
      </Disclosure.Heading>
      <Disclosure.Content>
        <Disclosure.Body className="px-5 pb-5">
          <p className="whitespace-pre-line leading-8 opacity-90" dir={isArabic ? "rtl" : "ltr"}>
            {text}
          </p>
        </Disclosure.Body>
      </Disclosure.Content>
    </Disclosure>
  );
}
