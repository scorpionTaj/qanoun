"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button, SearchField } from "@heroui/react";

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

  const go = (value: string) => {
    const qs = new URLSearchParams();
    if (value.trim()) qs.set("q", value.trim());
    if (domain) qs.set("domain", domain);
    router.push(`/${locale}/laws${qs.size ? `?${qs}` : ""}`);
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        go(query);
      }}
      className="flex gap-2"
      role="search"
    >
      <SearchField
        aria-label={placeholder}
        className="flex-1"
        value={query}
        onChange={setQuery}
        onClear={() => go("")}
        name="q"
      >
        <SearchField.Group className="h-11">
          <SearchField.SearchIcon />
          <SearchField.Input placeholder={placeholder} />
          <SearchField.ClearButton />
        </SearchField.Group>
      </SearchField>
      <Button type="submit" className="h-11 px-6">
        {buttonLabel}
      </Button>
    </form>
  );
}
