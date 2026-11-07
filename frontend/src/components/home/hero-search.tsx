"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export function HeroSearch({
  locale,
  placeholder,
  askLabel,
}: {
  locale: string;
  placeholder: string;
  askLabel: string;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");

  const ask = () => {
    const q = query.trim();
    router.push(q ? `/${locale}/chat?q=${encodeURIComponent(q)}` : `/${locale}/chat`);
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        ask();
      }}
      className="flex flex-col gap-2 sm:flex-row"
    >
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute start-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zellige-400" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          className="h-12 border-transparent bg-white/95 ps-10 text-zellige-950 shadow-lg backdrop-blur"
        />
      </div>
      <Button type="submit" variant="sand" size="lg" className="h-12 shadow-lg">
        {askLabel}
      </Button>
    </form>
  );
}
