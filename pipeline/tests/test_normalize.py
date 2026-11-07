from qanoun_pipeline.normalize import normalize, tokenize


def test_normalize_folds_alef_variants_and_taa_marbuta():
    assert normalize("أحمد") == normalize("احمد") == "احمد"
    assert normalize("مدرسة") == "مدرسه"


def test_normalize_strips_diacritics_and_tatweel():
    assert normalize("مُحَمَّـد") == "محمد"


def test_normalize_folds_presentation_forms():
    # ﷺ and ligatures like لا from PDF extraction are folded by NFKC.
    assert normalize("لا") == "لا"
    assert normalize("ﻻ") == "لا"


def test_normalize_arabic_indic_digits_to_ascii():
    assert normalize("المادة ١٢") == "الماده 12"
    assert normalize("٤") == "4"


def test_tokenize_strips_definite_article_and_stopwords():
    tokens = tokenize("في المدونة الأسرة")
    assert "المدونه" not in tokens  # ال stripped
    assert "في" not in tokens  # stopword
    assert "اسره" in tokens  # ت→ه and ال stripped


def test_tokenize_matches_across_spellings():
    assert tokenize("المدرسة") == tokenize("مدرسة")
