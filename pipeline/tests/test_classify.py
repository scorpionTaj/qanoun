from qanoun_pipeline.classify import domain_votes, suggest_domain
from qanoun_pipeline.normalize import normalize


def test_family_text_suggests_family():
    text = "يتم الزواج بعقد، وإذا حدث الطلاق فتكون الحضانة للأم والصداق للزوجة."
    assert suggest_domain(text) == "family"


def test_labour_text_suggests_labour():
    text = "عقد الشغل يبرره بين الأجير والمشغل، وينظم الأجر والعطلة السنوية."
    assert suggest_domain(text) == "labour"


def test_ambiguous_text_returns_none():
    assert suggest_domain("هذا نص عام بدون مصطلحات قانونية محددة واضحة.") is None


def test_votes_breakdown_used_in_notebooks():
    votes = domain_votes("الزواج والطلاق والحضانة")
    assert votes["family"] >= 3


def test_keywords_go_through_normalizer():
    # "المدرسة" normalizes to "مدرسه": the keyword list must match that form.
    assert domain_votes("المدرسة الثانوية والتلميذ")["education"] >= 1


def test_french_text_suggests_family():
    text = (
        "Le mariage est conclu devant les parties. En cas de divorce, la garde de l enfant "
        "et la pension alimentaire sont fixées par le tribunal."
    )
    assert suggest_domain(text) == "family"


def test_french_text_suggests_labour():
    text = (
        "Le contrat de travail lie le salarié et l employeur. Le licenciement et le salaire "
        "sont régis par le code."
    )
    assert suggest_domain(text) == "labour"
