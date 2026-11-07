"""Lightweight domain classifier: keyword evidence for which legal domain a text belongs to.

The catalog assigns domains authoritatively for known laws; this module is the data-science
hook for the scraper era, when newly downloaded Bulletin Officiel texts must be routed
automatically before a human confirms them. Matching goes through the same normalizer as
the rest of the pipeline and strips the definite article (ال) from both sides, so a keyword
"حضانه" matches "الحضانة" and the phrase "عقد شغل" matches "عقد الشغل".
"""

import re
from collections import Counter

from qanoun_pipeline.normalize import normalize, strip_article

_WORD = re.compile(r"\w+")

# fmt: off
KEYWORDS: dict[str, tuple[str, ...]] = {
    "family": (
        "زواج", "طلاق", "اسره", "صداق", "حضانه", "نفقه", "خطبه", "ارث", "وصيه", "زوج", "زوجه",
        "عهد اطفال", "كرشه",
    ),
    "labour": (
        "اجير", "مشغل", "عقد شغل", "اجر", "عطله", "اشغاق", "مقاوله", "نقابه", "شغل", "خصم",
        "شبه مستقل",
    ),
    "civil": (
        "التزام", "عقد", "بيع", "ايجار", "ضرر", "تعويض", "مسؤوليه", "دعني", "رهن", "فسخ",
    ),
    "housing": (
        "كراء", "مكتري", "مكري", "عينه", "كراء عقار", "خصم الايدي",
    ),
    "education": (
        "تعليم", "مدرسه", "ثانويه", "جامعه", "تلميذ", "استاذ", "مجلس تدريس", "امتحان", "منهاج",
        "مؤسسه تعليميه", "انتداب",
    ),
    "penal": (
        "جريمه", "عقابه", "سجن", "حبس", "نيابه عامه", "قاضي تحقيق", "شكوى", "متحدث",
    ),
    "nationality": (
        "جنسيه", "تطبيع", "مواطنه", "تجنيس",
    ),
    "social": (
        "ضمان اجتماعي", "تقاعد", "معاش", "حماه اجتماعيه", "تعويضات عائله", "بطاله",
    ),
    "commercial": (
        "شركه", "تاجر", "افلاس", "محل تجاري", "سماره", "سجل تجاري", "شرطه",
    ),
    "justice": (
        "محكمه", "محكمه النقض", "دعوي", "مرافعات", "قاضي", "رئيس المحكمه", "مجلس القضاء",
    ),
}
# fmt: on


def _stripped_phrase(keyword: str) -> str:
    return " ".join(strip_article(w) for w in normalize(keyword).split())


def _evidence(text: str) -> tuple[str, dict[str, int]]:
    stripped = " " + " ".join(strip_article(w) for w in _WORD.findall(normalize(text))) + " "
    votes: dict[str, int] = {}
    for domain, keywords in KEYWORDS.items():
        votes[domain] = sum(1 for keyword in keywords if f" {_stripped_phrase(keyword)} " in stripped)
    return stripped, votes


def suggest_domain(text: str, min_hits: int = 3) -> str | None:
    """Return the domain with the most keyword hits, or None below the evidence threshold."""
    votes = domain_votes(text)
    if not votes:
        return None
    domain, count = max(votes.items(), key=lambda kv: kv[1])
    return domain if count >= min_hits else None


def domain_votes(text: str) -> dict[str, int]:
    """Raw hit counts per domain — used in the classification notebook."""
    return _evidence(text)[1]
