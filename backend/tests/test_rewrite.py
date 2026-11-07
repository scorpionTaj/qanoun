from qanoun_api.rag.rewrite import (
    QueryRewriter,
    build_rewrite_messages,
    detect_variety,
    glossary_hints,
)


def test_detect_darija_script():
    assert detect_variety("واش خاصني نعرف شنو هو الصداق؟") == "darija"


def test_detect_darija_common_words():
    assert detect_variety("ديال الوالدين") == "darija"


def test_detect_arabizi():
    assert detect_variety("kifach kaytsayf li wrath؟") == "arabizi"
    assert detect_variety("bghit n3ref chhal dyal l3otla") == "arabizi"


def test_detect_msa():
    assert detect_variety("ما هي شروط الزواج في مدونة الأسرة؟") == "msa"


def test_detect_other_language():
    assert detect_variety("What are the conditions of marriage?") == "other"
    assert detect_variety("Quelles sont les conditions du mariage ?") == "other"


def test_glossary_hints_maps_legal_terms():
    hints = glossary_hints("شنو هو الصداق وكيفاش كيتحسب؟")
    assert any("صداق" in h for h in hints)


def test_rewrite_messages_attach_hints():
    messages = build_rewrite_messages("شنو هو الكونجي ديال الأجير؟")
    user = messages[1]["content"]
    assert "Glossary" in user
    assert "الكونجي" in user


def test_rewriter_uses_llm_only_for_darija(fake_llm):
    rewriter = QueryRewriter(fake_llm, cache_path=None)
    assert rewriter.rewrite("ما هي شروط الزواج؟") == "ما هي شروط الزواج؟"
    assert fake_llm.calls == []  # MSA question: no LLM call

    rewritten = rewriter.rewrite("شنو هو الصداق؟")
    assert rewritten and rewritten != ""
    assert len(fake_llm.calls) == 1
    # cached second time
    rewriter.rewrite("شنو هو الصداق؟")
    assert len(fake_llm.calls) == 1
