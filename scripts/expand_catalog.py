"""One-off catalog expansion helper: download curated laws from the adala portal
(adala.justice.gov.ma/api/uploads/...), validate each is a real, segmentable law PDF,
and print catalog-ready YAML entries.

    uv run --project pipeline python scripts/expand_catalog.py [--validate-only]

URLs were discovered via the portal's own search (adala.justice.gov.ma/search?term=…);
nothing enters the catalog until the PDF opens, has pages, and yields article headers.
"""

import argparse
import sys
import urllib.parse
from pathlib import Path

import httpx
import yaml

from qanoun_pipeline.catalog import file_sha256
from qanoun_pipeline.parse import read_pages
from qanoun_pipeline.structure import segment

RAW = Path("data/raw")
BASE = "https://adala.justice.gov.ma/api/"

# slug, group, title_ar, title_fr, law_number, year, domain, language, path on adala
CANDIDATES = [
    # ── penal ─────────────────────────────────────────────────────────────
    ("penal-code-ar", "penal-code", "مجموعة القانون الجنائي", "Code pénal", "1-59-413", 1962, "penal", "ar",
     "uploads/2025/03/14/ظـهير شـريف رقم 1.59.413 بالمصادقة على مجموعة القانون الجنائي-1741952873602.pdf"),
    ("penal-code-fr", "penal-code", "مجموعة القانون الجنائي", "Code pénal", "1-59-413", 1962, "penal", "fr",
     "uploads/2025/04/03/Dahir n° 1-59-413 portant approbation du texte du code penal-1743685280109.pdf"),
    ("money-laundering-ar", "penal", "قانون مكافحة غسل الأموال", None, "43-05", 2007, "penal", "ar",
     "uploads/2026/03/27/ظهير شريف رقم 1.07.79 بتنفيذ القانون رقم 43.05 المتعلق بمكافحة غسل الأموال-1774622209154.pdf"),
    # ── justice ───────────────────────────────────────────────────────────
    ("civil-procedure-ar", "civil-procedure", "قانون المسطرة المدنية", "Code de procédure civile", "1-74-447", 1974, "justice", "ar",
     "uploads/2026/08/27/ظهير شريف بمثابة قانون رقم 1.74.447 بالمصادقة على-1787838360852.pdf"),
    ("civil-procedure-fr", "civil-procedure", "قانون المسطرة المدنية", "Code de procédure civile", "1-74-447", 1974, "justice", "fr",
     "uploads/2024/02/28/Code de procédure civile-1709129409071.pdf"),
    ("criminal-procedure-ar", "criminal-procedure", "قانون المسطرة الجنائية", "Code de procédure pénale", "22-01", 2002, "justice", "ar",
     "uploads/2026/09/09/ظهير شريف رقم 1.02.255 بتنفيذ القانون رقم 22.01 المتعلق بالم)-1788960852357.pdf"),
    ("judicial-organization-ar", "judicial-organization", "قانون التنظيم القضائي للمملكة", None, "1-74-338", 1974, "justice", "ar",
     "uploads/2025/01/08/التنظيم القضائي سنة 1974  (نسخ)-1736333137814.pdf"),
    ("judges-statute-ar", "judges-statute", "النظام الأساسي للقضاة", None, "1-16-41", 2016, "justice", "ar",
     "uploads/2025/11/11/ظهير شريف رقم 1.16.41 بتنفيذه للقانون التنظيمي رقم 09.25-1762851653532.pdf"),
    ("neighborhood-justice-ar", "neighborhood-justice", "قانون قضاء القرب", None, "42-10", 2011, "justice", "ar",
     "uploads/2026/08/27/ظهير شريف رقم 1.11.151 بتنفيذ القانون رقم 42.10 المتعلق-1787838999894.pdf"),
    ("financial-courts-ar", "financial-courts", "قانون المحاكم المالية", None, "62-99", 2002, "justice", "ar",
     "uploads/2025/12/17/ظهير شريف رقم 1.02.124 بتنفيذ القانون رقم 62.99-1765983670947.pdf"),
    # ── commercial ────────────────────────────────────────────────────────
    ("commercial-code-ar", "commercial-code", "مدونة التجارة", "Code de commerce", "15-95", 1996, "commercial", "ar",
     "uploads/2026/05/25/ظــهــيــر شــريــف رقــم 1.96.83 بتنفيذ القانون رقم 15.95-1779718527894.pdf"),
    ("commercial-code-fr", "commercial-code", "مدونة التجارة", "Code de commerce", "15-95", 1996, "commercial", "fr",
     "uploads/2024/03/01/Code de commerce_compressed-1709282723074.pdf"),
    ("joint-stock-companies-ar", "joint-stock-companies", "قانون شركات المساهمة", None, "17-95", 1996, "commercial", "ar",
     "uploads/2024/02/05/شركات المساهمة-1707139691684.pdf"),
    ("competition-ar", "competition", "قانون حرية الأسعار والمنافسة", None, "104-12", 2014, "commercial", "ar",
     "uploads/2026/02/23/ظهير شريف رقم 1.14.116 بتنفيذ القانون رقم 104.12 المتعلق بحرية الأسعار والمنافسة-1771857502394.pdf"),
    ("self-entrepreneur-ar", "self-entrepreneur", "نظام المقاول الذاتي", None, "114-13", 2015, "commercial", "ar",
     "uploads/2024/07/09/ظهير شريف بتنفيذ القانون رقم 114.13 المتعلق بنظام المقاول الذاتي-1720535300284.pdf"),
    # ── family / nationality ──────────────────────────────────────────────
    ("nationality-ar", "nationality", "قانون الجنسية المغربية", "Code de la nationalité marocaine", "1-58-250", 1958, "nationality", "ar",
     "uploads/2025/12/18/ظهير شريف رقم 1.58.250 بسن قانون الجنسية المغربية صيغة مراجعة-1766047195269.pdf"),
    ("nationality-fr", "nationality", "قانون الجنسية المغربية", "Code de la nationalité marocaine", "1-58-250", 1958, "nationality", "fr",
     "uploads/2025/11/28/Dahir n° 1-58-250 portant code de la nationalité marocaine-1764341585221.pdf"),
    # Not kafala law 15.01 itself: the portal's only «كفالة الأطفال المهملين» PDFs are ministry
    # circulars (this one: a 2002 letter to the courts), so OCR finds no articles. Kept out.
    ("family-solidarity-ar", "family-solidarity", "قانون صندوق التكافل العائلي", None, "41-10", 2010, "family", "ar",
     "uploads/2024/02/07/صندوق التكافل العائلي-1707305363226.pdf"),
    # ── labour & social ───────────────────────────────────────────────────
    ("domestic-workers-ar", "domestic-workers", "قانون العاملات والعمال المنزليين", None, "19-12", 2016, "labour", "ar",
     "uploads/2026/08/12/ظهير شريف رقم 1.16.121  بتنفيذ القانون رقم 19.12-1786523202602.pdf"),
    ("work-accidents-ar", "work-accidents", "قانون حوادث الشغل والأمراض المهنية", None, "18-12", 2014, "labour", "ar",
     "uploads/2025/12/16/ظــهــيـر شـريـف رقـم 1.14.190 بتنفيذ القانون رقم 18.12 المتعلق-1765874452213.pdf"),
    ("insurance-code-ar", "insurance-code", "مدونة التأمينات", "Code des assurances", "17-99", 2002, "social", "ar",
     "uploads/2025/11/26/ظــهــير شريف رقم 1.02.238 بتنفيذ القانون رقم 17.99 المتعلق بمدونة التأمينات-1764168111488.pdf"),
    # ── education ─────────────────────────────────────────────────────────
    ("higher-education-ar", "higher-education", "قانون التعليم العالي", None, "01-00", 2000, "education", "ar",
     "uploads/2026/03/06/ظهير شريف رقم 1.00.199 بتنفيذ القانون رقم  01.00-1772808846692.pdf"),
    ("nurseries-ar", "nurseries", "النظام الأساسي لدور الحضانة الخاصة", None, "40-04", 2008, "education", "ar",
     "uploads/2026/04/08/ظهير شريف رقم 1.08.77 بتنفيذ القانون رقم 40.04-1775656091525.pdf"),
    # ── transport ─────────────────────────────────────────────────────────
    ("traffic-code-ar", "traffic", "مدونة السير على الطرق", None, "52-05", 2010, "transport", "ar",
     "uploads/2025/06/11/ظهير شريف 1.10.07 بتنفيذ القانون رقم 52.05 المتعلق بمدونة السير على الطرق -1749642259749.pdf"),
    # ── property ──────────────────────────────────────────────────────────
    ("real-rights-ar", "real-rights", "مدونة الحقوق العينية", None, "39-08", 2011, "property", "ar",
     "uploads/2026/07/28/ظهير شريف رقم 1.11.178  39.08 المتعلق بمدونة الحقوق العينية-1785250244908.pdf"),
    ("urbanism-ar", "urbanism", "قانون التعمير", None, "12-90", 1992, "property", "ar",
     "uploads/2026/10/15/مرسوم رقم 2.92.832 لتطبيق القانون رقم 12.90 المتعلق بالتعمير-1792066720715.pdf"),
    ("joint-ownership-ar", "joint-ownership", "قانون الملكية المشتركة للعقارات المبنية", None, "18-00", 2002, "property", "ar",
     "uploads/2026/07/29/ظهير شريف رقم  1.02.298بتنفيذ القانون رقم 18.00-1785318450026.pdf"),
    ("expropriation-ar", "property", "قانون نزع الملكية لأجل المنفعة العامة", None, "7-81", 1981, "property", "ar",
     "uploads/2024/12/12/مرسوم يتعلق بنزع الملكية لأجل المنفعة العامة وبالاحتلال المؤقت-1734012635282.pdf"),
    # ── governance ────────────────────────────────────────────────────────
    ("associations-ar", "associations", "ظهير حق تأسيس الجمعيات", None, "1-58-376", 1958, "governance", "ar",
     "uploads/2024/07/15/ظهير شريف رقم 1.58.376 يضبط بموجبه حق تأسيس الجمعيات-1721056242579.pdf"),
    ("press-code-ar", "press-code", "قانون الصحافة والنشر", None, "88-13", 2016, "governance", "ar",
     "uploads/2024/07/26/الصحافة والنشر-1721982145338.pdf"),
    ("data-protection-ar", "data-protection", "قانون حماية الأشخاص الذاتيين تجاه معالجة المعطيات ذات الطابع الشخصي", None, "09-08", 2009, "governance", "ar",
     "uploads/2024/09/05/ظهير شريف رقم 1.09.15 بتنفيذ القانون رقم 09.08 المتعلق بحماية الأشخاص ال.._-1725534598486.pdf"),
    ("unions-ar", "unions", "ظهير النقابات المهنية", None, "1-57-119", 1957, "governance", "ar",
     "uploads/2024/12/10/ظهير شريف رقم 1.57.119 بشأن النقابات المهنية-1733827092413.pdf"),
    ("public-debt-collection-ar", "public-debt-collection", "قانون تحصيل الديون العمومية", None, "15-97", 2000, "governance", "ar",
     "uploads/2026/10/05/ظـهير شـريف رقم 1.00.175 بتنفيذ القانون رقم 15.97-1791213329814.pdf"),
    ("waqf-code-ar", "waqf-code", "مدونة الأوقاف", None, "1-09-236", 2010, "governance", "ar",
     "uploads/2024/02/20/مدونة الأوقاف-1708419195028.pdf"),
    ("foreigners-ar", "foreigners", "قانون دخول وإقامة الأجانب بالمملكة المغربية", None, "02-03", 2003, "governance", "ar",
     "uploads/2024/11/28/مرسوم رقم 2.09.607 بتطبيق القانون رقم 02.03 المتعلق بدخول وإقامة الأجانب.._-1732801280633.pdf"),
    # ── added from the roadmap (2026-11) ──────────────────────────────────
    ("private-education-ar", "private-education", "النظام الأساسي للتعليم المدرسي الخصوصي", None, "06-00", 2000, "education", "ar",
     "uploads/2026/03/09/ظهير شريف رقم 1.00.202 بتنفيذ القانون رقم 06.00-1773067031215.pdf"),
    ("investment-charter-ar", "investment-charter", "القانون الإطار بمثابة ميثاق الاستثمار", None, "03-22", 2022, "commercial", "ar",
     "uploads/2026/02/12/ظـهـيـر شريف رقم 1.22.76 بتنفيذ القانون - الإطار رقم 03.22 بمثابة ميثاق الاستثمار-1770890118949.pdf"),
    ("land-registration-ar", "land-registration", "ظهير التحفيظ العقاري", None, "1913", 1913, "property", "ar",
     "uploads/2026/03/19/ظهير شريف  المتعلق بالتحفيظ العقاري-1773931844340.pdf"),
    # ── added 2026-11-23: constitution, consumers, companies, women, information, lawyers ──
    ("constitution-ar", "constitution", "دستور المملكة المغربية", "Constitution du Royaume du Maroc", "2011", 2011, "governance", "ar",
     "uploads/2024/01/30/الدستور-1706626006826.pdf"),
    ("constitution-fr", "constitution", "دستور المملكة المغربية", "Constitution du Royaume du Maroc", "2011", 2011, "governance", "fr",
     "uploads/2024/02/28/costitution-1709118294788.pdf"),
    ("consumer-protection-ar", "consumer-protection", "قانون تدابير حماية المستهلك", "Loi édictant des mesures de protection du consommateur", "31-08", 2011, "commercial", "ar",
     "uploads/2026/10/22/ظهير شريف رقم 1.11.03 بتنفيذ القانون رقم 31.08 ا (1)-1792665155973.pdf"),
    ("consumer-protection-fr", "consumer-protection", "قانون تدابير حماية المستهلك", "Loi édictant des mesures de protection du consommateur", "31-08", 2011, "commercial", "fr",
     "uploads/2024/03/01/protection de consommateur-1709283839988.pdf"),
    ("companies-ar", "companies-596", "قانون شركات التضامن والتوصية والمحاصة والشركة ذات المسؤولية المحدودة", "Loi relative aux SNC, SCS, SCA, SARL et sociétés en participation", "5-96", 1997, "commercial", "ar",
     "uploads/2025/12/03/ظهير شريف رقم 1.97.49-1764751267036.pdf"),
    ("companies-fr", "companies-596", "قانون شركات التضامن والتوصية والمحاصة والشركة ذات المسؤولية المحدودة", "Loi relative aux SNC, SCS, SCA, SARL et sociétés en participation", "5-96", 1997, "commercial", "fr",
     "uploads/2024/03/26/LA SOCIETE EN NOM COLLECTIF-1711463631100.pdf"),
    ("violence-women-ar", "violence-women", "قانون محاربة العنف ضد النساء", "Loi relative à la lutte contre les violences faites aux femmes", "103-13", 2018, "penal", "ar",
     "uploads/2026/10/20/ظهير شريف رقم 1.18.19 بتنفيذ القانون رقم 103.13 المتعلق بمحاربة العنف ضد النساء-1792507857329.pdf"),
    ("access-information-ar", "access-information", "قانون الحق في الحصول على المعلومات", "Loi relative au droit d'accès à l'information", "31-13", 2018, "governance", "ar",
     "uploads/2024/02/13/الحق في المعلومات-1707831482089.pdf"),
    ("access-information-fr", "access-information", "قانون الحق في الحصول على المعلومات", "Loi relative au droit d'accès à l'information", "31-13", 2018, "governance", "fr",
     "uploads/2025/10/27/Dahir n° 1-18-15 portant promulgation de la loi n° 31-13 relative au droit d'accès à l'information-1761558922160.pdf"),
    ("legal-profession-ar", "legal-profession", "قانون تنظيم مهنة المحاماة", "Loi organisant la profession d'avocat", "66-23", 2026, "justice", "ar",
     "uploads/2026/09/22/ظهير شريف رقم 1.26.75 بتنفيذ القانون رقم 66.23 المتعلق بتنظيم مهنة المحاماة-1790070416475.pdf"),
    # ── on the portal since 2026 (missing when searched in Nov 2026 by text; found by number) ──
    ("civil-status-ar", "civil-status", "قانون الحالة المدنية", "Loi relative à l'état civil", "36-21", 2021, "family", "ar",
     "uploads/2026/04/16/ظهير شريف رقم 1.21.81 بتنفيذ القانون رقم 36.21 المتعلق بالحالة المدنية (1)-1776328405081.pdf"),
    ("kafala-ar", "kafala", "قانون كفالة الأطفال المهملين", "Loi relative à la kafala des enfants abandonnés", "15-01", 2002, "family", "ar",
     "uploads/2026/07/29/ظهير شريف رقم 1.02.172 بتنفيذ القانون رقم 15.01 المتعلق بكفالة الأطفال المهملين-1785317078022.pdf"),
    ("health-coverage-ar", "health-coverage", "مدونة التغطية الصحية الأساسية", "Code de la couverture médicale de base", "65-00", 2002, "social", "ar",
     "uploads/2026/03/06/ظهير شريف رقم 1.02.296 صادر في (2)-1772789292321.pdf"),
    ("elections-code-ar", "elections-code", "مدونة الانتخابات", "Code électoral", "9-97", 1997, "governance", "ar",
     "uploads/2026/07/29/ظهير شريف رقم 1.97.83 بتنفيذ القانون رقم 9.97 المتعلق بمدونة الانتخابات-1785320564115.pdf"),
    # ── implementing decrees (catalog `parent`: the law each one applies), added 2026-11-24 ──
    ("working-hours-decree-ar", "working-hours-decree", "مرسوم تحديد إجراءات تطبيق المادة 184 من مدونة الشغل (مدة العمل)", "Décret fixant les modalités d'application de l'article 184 du Code du travail (durée du travail)", "2.04.569", 2004, "labour", "ar",
     "uploads/2024/09/09/مرسوم رقم  2.04.569  صادر في 16 من ذي القعدة  1425 -1725875800223.pdf"),
    ("weekly-rest-decree-ar", "weekly-rest-decree", "مرسوم تنظيم الراحة الأسبوعية", "Décret relatif au repos hebdomadaire", "2.04.513", 2004, "labour", "ar",
     "uploads/2024/09/11/مرسوم رقم 2.04.513 بتنظيم الراحة الأسبوعية-1726048239012.pdf"),
    ("women-night-work-decree-ar", "women-night-work-decree", "مرسوم شروط تشغيل النساء في الشغل الليلي", "Décret fixant les conditions du travail de nuit des femmes", "2.04.568", 2004, "labour", "ar",
     "uploads/2024/09/13/مرسوم رقم 2.04.568 صادر في 16من ذي القعدة ء في أي شغل ليلي-1726223570502.pdf"),
    ("prohibited-works-decree-ar", "prohibited-works-decree", "مرسوم لائحة الأشغال التي يمنع أن يشغل فيها بعض الفئات من الأشخاص", "Décret fixant la liste des travaux interdits à certaines catégories de personnes", "2.10.183", 2010, "labour", "ar",
     "uploads/2024/04/15/مرسوم 183-1713176716611.pdf"),
    ("minimum-wage-decree-ar", "minimum-wage-decree", "مرسوم تحديد مبلغ الحد الأدنى القانوني للأجر", "Décret fixant le salaire minimum légal", "2.24.1122", 2024, "labour", "ar",
     "uploads/2026/01/05/نسخ -مرسوم رقم 2.24.1122 بتحديد مبلغ الحد الأدنى القانوني للأجر-1767607929383.pdf"),
    ("consumer-protection-decree-ar", "consumer-protection-decree", "مرسوم تطبيق بعض أحكام قانون حماية المستهلك", "Décret d'application de la loi 31-08 sur la protection du consommateur", "2.12.503", 2013, "commercial", "ar",
     "uploads/2024/11/21/مرسوم رقم 2.12.503 بتطبيق بعتهلك-1732180751682.pdf"),
    ("data-protection-decree-ar", "data-protection-decree", "مرسوم تطبيق قانون حماية الأشخاص الذاتيين تجاه معالجة المعطيات ذات الطابع الشخصي", "Décret d'application de la loi 09-08 sur la protection des données personnelles", "2.09.165", 2009, "governance", "ar",
     "uploads/2024/07/31/مرسوم لتطبيق القانون رقم 09.08 المتعلق بحماية-1722420738987.pdf"),
    ("domestic-work-contract-decree-ar", "domestic-work-contract-decree", "مرسوم نموذج عقد العمل الخاص بالعاملة أو العامل المنزلي", "Décret fixant le modèle de contrat de travail des travailleurs domestiques", "2.17.355", 2017, "labour", "ar",
     "uploads/2025/11/17/مرسوم رقم 2.17.355 بتحديد نموذج عقد العمل الخاص بالعاملة أو العامل المنزلي-1763374049043.pdf"),
]


def url_for(path: str) -> str:
    return BASE + urllib.parse.quote(path)


def download(url: str, dest: Path) -> bool:
    try:
        r = httpx.get(url, timeout=180, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (Qanoun corpus fetch)"})
    except httpx.HTTPError as exc:
        print(f"    ✗ download failed ({exc.__class__.__name__})")
        return False
    if r.status_code != 200 or len(r.content) < 10_000 or not r.content.startswith(b"%PDF"):
        print(f"    ✗ HTTP {r.status_code}, {len(r.content)} bytes, magic={r.content[:5]!r}")
        return False
    dest.write_bytes(r.content)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--slugs", nargs="*", help="only these candidates (default: all)")
    args = parser.parse_args()

    entries, failures = [], []
    for slug, group, title_ar, title_fr, number, year, domain, language, path in CANDIDATES:
        if args.slugs and slug not in args.slugs:
            continue
        dest = RAW / f"{slug}.pdf"
        print(f"· {slug}")
        if not args.validate_only:
            if not download(url_for(path), dest):
                failures.append(slug)
                continue
        if not dest.exists():
            failures.append(slug)
            continue
        try:
            pages = list(read_pages(dest))
            report = segment(pages)
        except Exception as exc:
            print(f"    ✗ unusable ({exc.__class__.__name__}: {str(exc)[:60]}) — {len(dest.read_bytes())} bytes")
            failures.append(slug)
            continue
        print(f"    ✓ {len(pages)} pages, {len(report.articles)} articles, warnings: {len(report.warnings)}")
        entries.append(
            {
                "slug": slug, "group": group, "title_ar": title_ar, "title_fr": title_fr,
                "law_number": number, "year": year, "domain": domain, "language": language,
                "file": dest.name, "source_url": url_for(path), "sha256": file_sha256(dest),
                "_pages": len(pages), "_articles": len(report.articles),
            }
        )

    print(f"\n{len(entries)} usable, {len(failures)} failed: {failures}")
    out = Path("data/catalog/_expansion_candidates.yaml")
    out.write_text(yaml.safe_dump(entries, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"catalog-ready entries → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
