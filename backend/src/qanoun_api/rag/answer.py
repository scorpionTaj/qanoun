"""Grounded answer generation: retrieve, prompt the LLM with numbered sources, parse
citations (ported from darija-rag, upgraded to article-level citations).

The model must answer only from the sources and cite them as [n]; when the sources do not
contain the answer it replies with a sentinel, which becomes an explicit abstention instead
of a guessed legal answer. Sources carry law + article + page so the UI can deep-link into
the reader.
"""

import re
from dataclasses import dataclass, field

from qanoun_api.rag.llm import ChatModel, strip_reasoning
from qanoun_api.rag.retrieval import Hit, RetrievalResult
from qanoun_api.rag.rewrite import QueryRewriter, detect_variety

NO_ANSWER = "NO_ANSWER"

_LANGUAGE_RULE = {
    "msa": "Answer in Modern Standard Arabic.",
    "darija": "Answer in simple Moroccan Darija written in Arabic script.",
    "arabizi": "Answer in Moroccan Darija written in Latin letters (Arabizi), like the question.",
    "other": "Answer in the language of the question.",
}

# The corpus names differ slightly from darija-rag's four-document set.
ABSTENTION = {
    "msa": "لا أجد جوابا لهذا السؤال في النصوص القانونية المتوفرة حاليا. جرِب صياغة السؤال "
    "بشكل آخر أو تصفح القوانين المتوفرة.",
    "darija": "ما لقيتش الجواب ديال هاد السؤال فالنصوص القانونية اللي عندي دابا. عاود صياغة "
    "السؤال ولا تصفح القوانين المتوفرة.",
    "arabizi": "Ma l9itch jawab dyal had so2al f nosos l9anouniya li 3ndi daba. 3awd sift "
    "so2al b tari9a okhra wla tsurf l9awanin lli kaynin.",
    "other": "Je ne trouve pas la réponse dans les textes juridiques actuellement disponibles. "
    "Essayez de reformuler ou parcourez les lois disponibles.",
}

DISCLAIMER = {
    "msa": "هذه المعلومات معلوماتية فقط ولا تشكل استشارة قانونية.",
    "darija": "هاد المعلومات غير معلوماتية، ماشي استشارة قانونية.",
    "arabizi": "Had lma3lomat ghir l-ma3loumatiya, machi istichara qanouniya.",
    "other": "Ces informations sont fournies à titre informatif uniquement et ne constituent "
    "pas un avis juridique.",
}

_SYSTEM = (
    "You are a careful assistant for Moroccan law. Answer ONLY with facts stated in the "
    "numbered sources. After each fact, cite its source like [1] or [2][3]. Mention article "
    "numbers when the source gives them. Be concise: at most 4 sentences. If the sources do "
    "not contain the answer, reply with exactly "
    f"{NO_ANSWER} and nothing else. Never use outside knowledge."
)


def source_label(hit: Hit, variety: str = "msa") -> str:
    """In the question's language, so the model cites "Code de la famille, art. 84" in a
    French answer instead of pasting the Arabic title into French prose."""
    if variety == "other" and hit.law_title_fr:
        return f"{hit.law_title_fr} — article {hit.article_number} (p. {hit.page})"
    return f"{hit.law_title} — المادة {hit.article_number} (ص{hit.page})"


def build_messages(question: str, sources: list[Hit], variety: str) -> list[dict]:
    blocks = [
        f"[{i}] ({source_label(hit, variety)})\n{hit.text}" for i, hit in enumerate(sources, start=1)
    ]
    # The language rule is repeated after the question: models follow the last instruction best,
    # and otherwise drift into the (MSA) language of the sources.
    user = (
        "Sources:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question}\n\n"
        f"{_LANGUAGE_RULE[variety]} Cite sources as [n]."
    )
    system = f"{_SYSTEM} {_LANGUAGE_RULE[variety]}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_citations(text: str, n_sources: int) -> list[int]:
    seen = []
    for match in re.finditer(r"\[(\d+)\]", text):
        index = int(match.group(1)) - 1
        if 0 <= index < n_sources and index not in seen:
            seen.append(index)
    return seen


@dataclass
class Answer:
    question: str
    text: str
    abstained: bool
    variety: str
    sources: list[Hit]
    cited: list[int] = field(default_factory=list)  # indexes into sources
    retrieval_query: str = ""
    disclaimer: str = ""

    @property
    def cited_hits(self) -> list[Hit]:
        return [self.sources[i] for i in self.cited]

    def as_dict(self) -> dict:
        return {
            "question": self.question,
            "text": self.text,
            "abstained": self.abstained,
            "variety": self.variety,
            "cited": self.cited,
            "retrieval_query": self.retrieval_query,
            "disclaimer": self.disclaimer or DISCLAIMER[self.variety],
            "sources": [hit.as_dict() for hit in self.sources],
        }


class Answerer:
    """Non-streaming variant used by the eval harness; the chat router streams instead."""

    def __init__(
        self,
        llm: ChatModel,
        k: int = 5,
        rewriter: QueryRewriter | None = None,
    ):
        self.llm = llm
        self.k = k
        self.rewriter = rewriter

    def retrieve(self, question: str, k: int | None = None) -> RetrievalResult:
        """Retrieve with both the original and (if Darija) the rewritten query, fused."""
        from qanoun_api.rag.retrieval import search

        result = search(question, k or self.k)
        if self.rewriter is None:
            return result
        rewritten = self.rewriter.rewrite(question)
        if rewritten == question:
            return result
        fused = search(question, k or self.k, search_query=rewritten)
        return merge(result, fused, k or self.k)

    def ask(self, question: str) -> Answer:
        question = question.strip()
        if not question:
            raise ValueError("empty question")
        variety = detect_variety(question)
        result = self.retrieve(question)
        sources = result.hits
        if not sources:
            return Answer(
                question, ABSTENTION[variety], True, variety, [], [], result.search_query,
                DISCLAIMER[variety],
            )
        reply = strip_reasoning(self.llm.chat(build_messages(question, sources, variety)))
        if NO_ANSWER in reply or not reply:
            return Answer(
                question, ABSTENTION[variety], True, variety, sources, [], result.search_query,
                DISCLAIMER[variety],
            )
        cited = parse_citations(reply, len(sources))
        return Answer(
            question, reply, False, variety, sources, cited, result.search_query,
            DISCLAIMER[variety],
        )


def merge(a: RetrievalResult, b: RetrievalResult, k: int) -> RetrievalResult:
    """Fuse two retrieval runs (original + rewritten query) by reciprocal rank sum."""
    scores: dict[tuple, float] = {}
    ranks: dict[tuple, tuple[int | None, int | None]] = {}
    for result, order in ((a, 0), (b, 1)):
        for rank, hit in enumerate(result.hits, start=1):
            key = (hit.law_slug, hit.article_number, hit.page, hit.text)
            scores[key] = scores.get(key, 0.0) + 1.0 / (60 + rank)
            dr, lr = ranks.get(key, (None, None))
            if hit.dense_rank is not None and dr is None:
                dr = hit.dense_rank
            if hit.lexical_rank is not None and lr is None:
                lr = hit.lexical_rank
            ranks[key] = (dr, lr)
    pool: dict[tuple, Hit] = {}
    for hit in [*a.hits, *b.hits]:
        key = (hit.law_slug, hit.article_number, hit.page, hit.text)
        pool.setdefault(key, hit)
    ordered = sorted(scores.items(), key=lambda kv: -kv[1])[:k]
    hits = []
    for key, score in ordered:
        hit = pool[key]
        hits.append(
            Hit(
                law_slug=hit.law_slug, law_title=hit.law_title, law_title_fr=hit.law_title_fr,
                group_slug=hit.group_slug, domain=hit.domain, language=hit.language,
                article_number=hit.article_number, article_id=hit.article_id, page=hit.page,
                text=hit.text, rrf=score, dense_rank=ranks[key][0], lexical_rank=ranks[key][1],
            )
        )
    return RetrievalResult(query=a.query, search_query=b.search_query, hits=hits)
