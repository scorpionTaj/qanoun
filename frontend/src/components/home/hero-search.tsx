"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button, InputGroup, TextField } from "@heroui/react";
import { ArrowLeft, ArrowRight, Search } from "lucide-react";

export function HeroSearch({
  locale,
  placeholder,
  askLabel,
  examples,
}: {
  locale: string;
  placeholder: string;
  askLabel: string;
  examples: string[];
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const Arrow = locale === "ar" ? ArrowLeft : ArrowRight;

  const ask = (text: string) => {
    const q = text.trim();
    router.push(q ? `/${locale}/chat?q=${encodeURIComponent(q)}` : `/${locale}/chat`);
  };

  return (
    <div className="flex flex-col gap-4">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(query);
        }}
        className="flex flex-col gap-2 rounded-[1.5rem] bg-surface p-2 shadow-2xl shadow-black/20 sm:flex-row"
      >
        <TextField aria-label={placeholder} className="flex-1" value={query} onChange={setQuery} name="q">
          <InputGroup className="h-12 border-0 bg-transparent shadow-none">
            <InputGroup.Prefix>
              <Search className="size-5 text-muted" aria-hidden />
            </InputGroup.Prefix>
            <InputGroup.Input placeholder={placeholder} className="text-base" autoComplete="off" />
          </InputGroup>
        </TextField>
        <Button type="submit" size="lg" className="h-12 rounded-2xl px-6">
          {askLabel}
          <Arrow className="size-4" aria-hidden />
        </Button>
      </form>
      <div className="flex flex-wrap justify-center gap-2">
        {examples.map((example) => (
          <Button
            key={example}
            size="sm"
            variant="ghost"
            onPress={() => ask(example)}
            className="rounded-full bg-white/10 text-white/90 hover:bg-white/20"
          >
            <span dir="auto">{example}</span>
          </Button>
        ))}
      </div>
    </div>
  );
}
