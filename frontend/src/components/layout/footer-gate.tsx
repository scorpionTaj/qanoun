"use client";

import { usePathname } from "next/navigation";

/** The Ask page is a full-height workspace: no page footer under it. */
export function FooterGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "";
  return pathname.split("/")[2] === "chat" ? null : <>{children}</>;
}
