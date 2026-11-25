/** Laws kept on the phone so they open without a connection. The laws list is cached too, so
 * the Laws tab still shows what exists (and what is saved) when the server can't be reached. */
import { getLaw, type LawDetail, listLaws, type LawSummary } from "./api";
import { readJson, removeKey, writeJson } from "./storage";

const LIST = "qanoun.laws";
const SAVED = "qanoun.saved"; // slugs, in the order they were saved
const lawKey = (slug: string) => `qanoun.law.${slug}`;

export const savedSlugs = () => readJson<string[]>(SAVED, []);
export const savedLaw = (slug: string) => readJson<LawDetail | null>(lawKey(slug), null);

export function saveLaw(law: LawDetail): void {
  writeJson(lawKey(law.slug), law);
  const slugs = savedSlugs();
  if (!slugs.includes(law.slug)) writeJson(SAVED, [...slugs, law.slug]);
}

export function removeLaw(slug: string): void {
  removeKey(lawKey(slug));
  writeJson(SAVED, savedSlugs().filter((s) => s !== slug));
}

/** The list from the server (cached for next time), or the cached one when offline. */
export async function loadLaws(): Promise<{ laws: LawSummary[]; offline: boolean }> {
  try {
    const laws = await listLaws();
    writeJson(LIST, laws);
    return { laws, offline: false };
  } catch (error) {
    const cached = readJson<LawSummary[] | null>(LIST, null);
    if (cached) return { laws: cached, offline: true };
    throw error;
  }
}

/** A law from the server; a saved copy is refreshed with it (amended texts reach the phone). */
export async function fetchLaw(slug: string): Promise<LawDetail> {
  const law = await getLaw(slug);
  if (savedSlugs().includes(slug)) saveLaw(law);
  return law;
}
