"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export function SearchBar({
  locale,
  initialValue,
  placeholder,
  buttonLabel,
  domain,
}: {
  locale: string;
  initialValue: string;
  placeholder: string;
  buttonLabel: string;
  domain?: string;
}) {
  const router = useRouter();
  const [query, setQuery] = useState(initialValue);

  const go = () => {
    const q = query.trim();
    const qs = new URLSearchParams();
    if (q) qs.set("q", q);
    if (domain) qs.set("domain", domain);
    const suffix = qs.size ? `?${qs}` : "";
    router.push(`/${locale}/laws${suffix}`);
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        go();
      }}
      className="flex gap-2"
    >
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute start-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zellige-400" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          className="ps-10"
        />
      </div>
      <Button type="submit" className="px-6">
        {buttonLabel}
      </Button>
    </form>
  );
}
