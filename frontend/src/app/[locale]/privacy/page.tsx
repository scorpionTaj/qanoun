import { getTranslations } from "next-intl/server";
import { apiUrl } from "@/lib/api-url";

/** What this server reports about its own processing (GET /api/privacy). */
interface PrivacyFacts {
  controller: string | null;
  contact: string | null;
  cndp_receipt: string | null;
  processors: { id: string; name: string; country: string }[];
  local_model: boolean;
  accounts: boolean;
  query_log: { question_text: boolean; retention_days: number };
  session_days: number;
}

async function facts(): Promise<PrivacyFacts | null> {
  try {
    const response = await fetch(`${apiUrl()}/api/privacy`, { cache: "no-store" });
    return response.ok ? ((await response.json()) as PrivacyFacts) : null;
  } catch {
    return null;
  }
}

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="flex flex-col gap-3">
    <h2 className="text-xl font-semibold">{title}</h2>
    {children}
  </section>
);

/** Privacy notice required by Law 09-08 (art. 5): who, what, why, who receives it, how long, rights. */
export default async function PrivacyPage({ params }: { params: Promise<{ locale: string }> }) {
  await params;
  const t = await getTranslations("privacy");
  const f = await facts();
  const days = f?.session_days ?? 30;
  const logDays = f?.query_log.retention_days ?? 90;

  return (
    <article className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-10 leading-relaxed">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <p className="text-sm text-muted">{t("updated")}</p>
        <p>{t("intro")}</p>
        {!f && <p className="text-sm text-warning">{t("unavailable")}</p>}
      </header>

      <Section title={t("controllerTitle")}>
        <p>{f?.controller ?? t("controllerUnset")}</p>
        {f?.contact && <p>{t("contact")} : <span dir="ltr">{f.contact}</span></p>}
        <p>{t("cndpReceipt")} : {f?.cndp_receipt ? <span dir="ltr">{f.cndp_receipt}</span> : t("cndpPending")}</p>
      </Section>

      <Section title={t("collectTitle")}>
        <p>{t("collectNoAccount")}</p>
        <p>{t("collectAccount", { days })}</p>
        <p>{t("collectLogs", { logged: f?.query_log.question_text ? t("logged") : t("notLogged"), days: logDays })}</p>
        <p>{t("collectAbuse")}</p>
      </Section>

      <Section title={t("transferTitle")}>
        {f && f.processors.length > 0 ? (
          <>
            <p>{t("transferIntro")}</p>
            <ul className="list-disc ps-6" data-testid="processors">
              {f.processors.map((p) => (
                <li key={p.id}><span dir="ltr">{p.name} — {p.country}</span></li>
              ))}
            </ul>
            {f.local_model && <p>{t("transferLocal")}</p>}
            <p className="rounded-xl border border-warning/40 bg-warning/10 p-3 font-medium">{t("transferWarning")}</p>
          </>
        ) : (
          <p>{f ? t("transferNone") : t("transferWarning")}</p>
        )}
        <p>{t("noSale")}</p>
      </Section>

      <Section title={t("retentionTitle")}>
        <p>{t("retention", { days, logDays })}</p>
      </Section>

      <Section title={t("rightsTitle")}>
        <p>{t("rights")}</p>
        <p>{t("rightsHow")}</p>
        <p>{t("complaint")}</p>
      </Section>

      <Section title={t("securityTitle")}>
        <p>{t("security")}</p>
      </Section>
    </article>
  );
}
