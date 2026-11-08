/** Print / save as PDF: one answer with its question and the articles it cited. */

import type { SearchHit } from "./types";

const escape = (s: string) =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

export interface AnswerExport {
  question: string;
  answer: string;
  sources: SearchHit[];
  cited: number[]; // 0-based indexes into sources
  disclaimer?: string;
  locale: string;
  labels: { title: string; question: string; answer: string; sources: string; article: string; page: string; exported: string };
}

export function answerHtml(a: AnswerExport): string {
  const dir = a.locale === "ar" ? "rtl" : "ltr";
  const indexes = a.cited.length ? a.cited : a.sources.map((_, i) => i);
  const sources = indexes
    .filter((i) => a.sources[i])
    .map((i) => {
      const hit = a.sources[i];
      const title = a.locale !== "ar" && hit.law_title_fr ? hit.law_title_fr : hit.law_title;
      return `<li value="${i + 1}"><h3>${escape(title)} — ${escape(a.labels.article)} ${escape(hit.article_number)} <small>(${escape(a.labels.page)} ${hit.page})</small></h3><p dir="auto">${escape(hit.text)}</p></li>`;
    })
    .join("");
  const date = new Date().toLocaleString(a.locale);
  return `<!doctype html><html lang="${a.locale}" dir="${dir}"><head><meta charset="utf-8"><title>${escape(a.labels.title)}</title>
<style>
body{font:15px/1.8 system-ui,"Noto Naskh Arabic",sans-serif;max-width:46rem;margin:2rem auto;padding:0 1rem;color:#111}
h1{font-size:1.4rem;margin:0 0 .25rem}h2{font-size:1rem;margin:1.5rem 0 .5rem;color:#2d3fa6;text-transform:uppercase;letter-spacing:.04em}
h3{font-size:.95rem;margin:0}small{color:#666;font-weight:normal}.meta{color:#666;font-size:.8rem}
blockquote{margin:0;padding:.75rem 1rem;border-inline-start:3px solid #2d3fa6;background:#f4f5fb;white-space:pre-wrap}
.answer{white-space:pre-wrap}ol{padding-inline-start:1.5rem}li{margin-bottom:1rem;break-inside:avoid}li p{margin:.25rem 0 0;white-space:pre-wrap}
.disclaimer{margin-top:2rem;padding-top:.75rem;border-top:1px solid #ddd;font-size:.8rem;color:#555}
</style></head><body>
<h1>${escape(a.labels.title)}</h1><p class="meta">${escape(a.labels.exported)} ${escape(date)}</p>
<h2>${escape(a.labels.question)}</h2><blockquote dir="auto">${escape(a.question)}</blockquote>
<h2>${escape(a.labels.answer)}</h2><div class="answer" dir="auto">${escape(a.answer)}</div>
${sources ? `<h2>${escape(a.labels.sources)}</h2><ol>${sources}</ol>` : ""}
${a.disclaimer ? `<p class="disclaimer" dir="auto">${escape(a.disclaimer)}</p>` : ""}
</body></html>`;
}

/** Opens the browser's print dialog (which also offers "Save as PDF"). */
export function printAnswer(a: AnswerExport): boolean {
  const win = window.open("", "_blank");
  if (!win) return false; // popup blocked
  win.document.write(answerHtml(a));
  win.document.close();
  win.focus();
  win.print();
  return true;
}
