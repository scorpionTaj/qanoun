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
        # French (accented + unaccented forms: OCR drops accents)
        "mariage", "divorce", "fiancailles", "fiançailles", "filiation", "garde de l enfant",
        "pension alimentaire", "succession", "heritier", "héritier", "legataire",
    ),
    "labour": (
        "اجير", "مشغل", "عقد شغل", "اجر", "عطله", "اشغاق", "مقاوله", "نقابه", "شغل", "خصم",
        "شبه مستقل",
        "salarie", "salarié", "employeur", "licenciement", "conge", "congé",
        "contrat de travail", "salaire", "greve", "grève", "delegue des salaries",
        "inspection du travail", "medecin du travail",
    ),
    "civil": (
        "التزام", "عقد", "بيع", "ايجار", "ضرر", "تعويض", "مسؤوليه", "دعني", "رهن", "فسخ",
        "obligation", "contrat", "vente", "dommage", "reparation", "réparation",
        "responsabilite", "responsabilité", "creance", "créance", "debiteur", "débiteur",
        "solidarite", "solidarité",
    ),
    "housing": (
        "كراء", "مكتري", "مكري", "عينه", "كراء عقار", "خصم الايدي",
        "bail", "baux", "bailleur", "locataire", "loyer", "louage",
    ),
    "education": (
        "تعليم", "مدرسه", "ثانويه", "جامعه", "تلميذ", "استاذ", "مجلس تدريس", "امتحان", "منهاج",
        "مؤسسه تعليميه", "انتداب",
        "ecole", "école", "enseignement", "etablissement scolaire", "eleve", "élève",
        "enseignant", "lycee", "lycée", "universite", "université", "academie", "académie",
    ),
    "penal": (
        "جريمه", "عقابه", "سجن", "حبس", "نيابه عامه", "قاضي تحقيق", "شكوى", "متحدث",
        "infraction", "emprisonnement", "amende", "prevenu", "prévenu", "ministere public",
        "ministère public",
    ),
    "nationality": (
        "جنسيه", "تطبيع", "مواطنه", "تجنيس",
        "nationalite", "nationalité", "naturalisation",
    ),
    "social": (
        "ضمان اجتماعي", "تقاعد", "معاش", "حماه اجتماعيه", "تعويضات عائله", "بطاله",
        "securite sociale", "sécurité sociale", "prestation sociale", "retraite", "allocation",
    ),
    "commercial": (
        "شركه", "تاجر", "افلاس", "محل تجاري", "سماره", "سجل تجاري", "شرطه",
        "fonds de commerce", "commerce", "bail commercial", "registre du commerce",
    ),
    "justice": (
        "محكمه", "محكمه النقض", "دعوي", "مرافعات", "قاضي", "رئيس المحكمه", "مجلس القضاء",
        "tribunal", "cour", "juge", "procedure", "procédure", "audience", "greffe",
    ),
    "transport": (
        "سياقه", "رخصة السياقه", "طريق", "طرق سياره", "مرور", "سير على الطرق", "مخالفه سير",
        "plaque", "permis de conduire", "circulation", "code de la route", "automobile",
        "contravention",
    ),
    "property": (
        "تحفيظ عقاري", "سجل عقاري", "حقوق عينيه", "تعمير", "تجزئة", "ملكيه مشتركه", "نزع ملكيه",
        "immatriculation", "foncier", "cadastre", "urbanisme", "lotissement", "copropriete",
        "copropriété", "expropriation", "conservation foncière", "conservation fonciere",
    ),
    "governance": (
        "جمعيه", "نقابه", "صحافي", "نشر", "معطيات شخصيه", "اجتماعي عمومي", "صفقات عموميه",
        "ديون عموميه", "association", "syndicat", "presse", "donnees personnelles",
        "données personnelles", "CNPD",
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
