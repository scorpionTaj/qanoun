import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

// Next 16 "proxy" (formerly middleware): locale detection and /{locale} redirects.
export default createMiddleware(routing);

export const config = {
  // Skip API routes, Next internals and static files.
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
