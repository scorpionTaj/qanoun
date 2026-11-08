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
    ("judges-statute-ar", "judicial-organization", "النظام الأساسي للقضاة", None, "1-16-41", 2016, "justice", "ar",
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
    ("joint-stock-companies-ar", "companies", "قانون شركات المساهمة", None, "17-95", 1996, "commercial", "ar",
     "uploads/2024/02/05/شركات المساهمة-1707139691684.pdf"),
    ("competition-ar", "competition", "قانون حرية الأسعار والمنافسة", None, "104-12", 2014, "commercial", "ar",
     "uploads/2026/02/23/ظهير شريف رقم 1.14.116 بتنفيذ القانون رقم 104.12 المتعلق بحرية الأسعار والمنافسة-1771857502394.pdf"),
    ("self-entrepreneur-ar", "companies", "نظام المقاول الذاتي", None, "114-13", 2015, "commercial", "ar",
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
    ("higher-education-ar", "education", "قانون التعليم العالي", None, "01-00", 2000, "education", "ar",
     "uploads/2026/03/06/ظهير شريف رقم 1.00.199 بتنفيذ القانون رقم  01.00-1772808846692.pdf"),
    ("nurseries-ar", "education", "النظام الأساسي لدور الحضانة الخاصة", None, "40-04", 2008, "education", "ar",
     "uploads/2026/04/08/ظهير شريف رقم 1.08.77 بتنفيذ القانون رقم 40.04-1775656091525.pdf"),
    # ── transport ─────────────────────────────────────────────────────────
    ("traffic-code-ar", "traffic", "مدونة السير على الطرق", None, "52-05", 2010, "transport", "ar",
     "uploads/2025/06/11/ظهير شريف 1.10.07 بتنفيذ القانون رقم 52.05 المتعلق بمدونة السير على الطرق -1749642259749.pdf"),
    # ── property ──────────────────────────────────────────────────────────
    ("real-rights-ar", "property", "مدونة الحقوق العينية", None, "39-08", 2011, "property", "ar",
     "uploads/2026/07/28/ظهير شريف رقم 1.11.178  39.08 المتعلق بمدونة الحقوق العينية-1785250244908.pdf"),
    ("urbanism-ar", "property", "قانون التعمير", None, "12-90", 1992, "property", "ar",
     "uploads/2026/10/15/مرسوم رقم 2.92.832 لتطبيق القانون رقم 12.90 المتعلق بالتعمير-1792066720715.pdf"),
    ("joint-ownership-ar", "property", "قانون الملكية المشتركة للعقارات المبنية", None, "18-00", 2002, "property", "ar",
     "uploads/2026/07/29/ظهير شريف رقم  1.02.298بتنفيذ القانون رقم 18.00-1785318450026.pdf"),
    ("expropriation-ar", "property", "قانون نزع الملكية لأجل المنفعة العامة", None, "7-81", 1981, "property", "ar",
     "uploads/2024/12/12/مرسوم يتعلق بنزع الملكية لأجل المنفعة العامة وبالاحتلال المؤقت-1734012635282.pdf"),
    # ── governance ────────────────────────────────────────────────────────
    ("associations-ar", "governance", "ظهير حق تأسيس الجمعيات", None, "1-58-376", 1958, "governance", "ar",
     "uploads/2024/07/15/ظهير شريف رقم 1.58.376 يضبط بموجبه حق تأسيس الجمعيات-1721056242579.pdf"),
    ("press-code-ar", "governance", "قانون الصحافة والنشر", None, "88-13", 2016, "governance", "ar",
     "uploads/2024/07/26/الصحافة والنشر-1721982145338.pdf"),
    ("data-protection-ar", "governance", "قانون حماية الأشخاص الذاتيين تجاه معالجة المعطيات ذات الطابع الشخصي", None, "09-08", 2009, "governance", "ar",
     "uploads/2024/09/05/ظهير شريف رقم 1.09.15 بتنفيذ القانون رقم 09.08 المتعلق بحماية الأشخاص ال.._-1725534598486.pdf"),
    ("unions-ar", "governance", "ظهير النقابات المهنية", None, "1-57-119", 1957, "governance", "ar",
     "uploads/2024/12/10/ظهير شريف رقم 1.57.119 بشأن النقابات المهنية-1733827092413.pdf"),
    ("public-debt-collection-ar", "governance", "قانون تحصيل الديون العمومية", None, "15-97", 2000, "governance", "ar",
     "uploads/2026/10/05/ظـهير شـريف رقم 1.00.175 بتنفيذ القانون رقم 15.97-1791213329814.pdf"),
    ("waqf-code-ar", "governance", "مدونة الأوقاف", None, "1-09-236", 2010, "governance", "ar",
     "uploads/2024/02/20/مدونة الأوقاف-1708419195028.pdf"),
    ("foreigners-ar", "governance", "قانون دخول وإقامة الأجانب بالمملكة المغربية", None, "02-03", 2003, "governance", "ar",
     "uploads/2024/11/28/مرسوم رقم 2.09.607 بتطبيق القانون رقم 02.03 المتعلق بدخول وإقامة الأجانب.._-1732801280633.pdf"),
    # ── added from the roadmap (2026-11) ──────────────────────────────────
    ("private-education-ar", "private-education", "النظام الأساسي للتعليم المدرسي الخصوصي", None, "06-00", 2000, "education", "ar",
     "uploads/2026/03/09/ظهير شريف رقم 1.00.202 بتنفيذ القانون رقم 06.00-1773067031215.pdf"),
    ("investment-charter-ar", "investment-charter", "القانون الإطار بمثابة ميثاق الاستثمار", None, "03-22", 2022, "commercial", "ar",
     "uploads/2026/02/12/ظـهـيـر شريف رقم 1.22.76 بتنفيذ القانون - الإطار رقم 03.22 بمثابة ميثاق الاستثمار-1770890118949.pdf"),
    ("land-registration-ar", "land-registration", "ظهير التحفيظ العقاري", None, "1913", 1913, "property", "ar",
     "uploads/2026/03/19/ظهير شريف  المتعلق بالتحفيظ العقاري-1773931844340.pdf"),
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
