"use client";

/** HeroUI for Server Components. @heroui/react imports `client-only`, so server pages and
 * layouts import the components they need from here: this boundary makes them client
 * references. Compound parts (Card.Header…) must be used inside client components. */
export { Card, Chip, Separator } from "@heroui/react";
