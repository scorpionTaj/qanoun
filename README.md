# قانون — Qanoun

**Moroccan laws, explored and question-ready.** Qanoun ingests the official texts of
Moroccan law (Family Code, Labour Code, the D.O.C., rental law…), structures them
article-by-article into Postgres/pgvector, and serves a trilingual (العربية RTL / Français /
English) web app where you can browse every article or ask questions in Darija, Arabic or
French — answered only from the retrieved sources, with citations to the exact article.

> المشروع يجمع هندسة البيانات والذكاء الاصطناعي في خدمة القانون المغربي: جلب النصوص الرسمية،
> هيكلتها إلى مواد، فهرستها دلاليا، ثم الإجابة عن الأسئلة (حتى بالدارجة) مع الإحالة إلى المادة.
>
> Ce projet combine data engineering, IA et droit marocain : ingestion des textes officiels,
> structuration en articles, indexation vectorielle et réponses sourcées.

**Informational only — not legal advice.** The official Bulletin remains the reference.

## The three layers

| Layer | What it does | Where |
|---|---|---|
| **Data engineering** | fetch (sha256-verified) → Arabic PDF parse + OCR fallback → article segmentation (footnote-glue repair, sub-numbers, sequence checks) → chunking → BGE-M3 embeddings → Postgres/pgvector | `pipeline/` |
| **AI** | hybrid retrieval (pgvector cosine + Arabic FTS, RRF fusion), Darija/Arabizi query rewriting via glossary + LLM, grounded answering with `[n]` citations and explicit abstention, streaming SSE | `backend/src/qanoun_api/rag/` |
| **Data science** | corpus EDA, keyword-domain classification experiments, embedding-space map, retrieval + LLM-as-judge evaluation | `notebooks/`, `backend/src/qanoun_api/eval/` |

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker, Node 20+, and for the chat one
LLM: the quickest is a free [Google AI Studio key](https://aistudio.google.com/apikey) in
`.env` (`QANOUN_GEMINI_KEY=…`); OpenRouter, NVIDIA NIM, LM Studio and Ollama work too. Keys
stay on the server; the ⚙ dialog picks among configured providers, tests the connection, and
questions fall back automatically to the next model/provider when one is busy.

```bash
cp .env.example .env           # add QANOUN_GEMINI_KEY (or another provider)
make db                        # postgres + pgvector on :5433

make ingest                    # full pipeline: fetch → parse → structure → embed → load
# (no model download yet? `make ingest-smoke` proves the plumbing with hash embeddings)

make api                       # FastAPI on :8000
cd frontend && npm install && npm run dev   # Next.js on :3000
```

Open http://localhost:3000 → you land on `/ar` (RTL). Switch to FR/EN in the header.

### Try it

- **Ask**: «ما هي شروط الزواج؟», «شنو هي حالات الفصل المشروع؟», «Quels sont les cas de
  divorce ?» — answers cite `مدونة الأسرة — المادة 12` and deep-link into the reader.
- **Scope & AI**: under the question box, «Search in» limits answers to one domain or one law
  (type to filter), «AI» picks the provider; «Ask about this law» preselects the law.
- **Follow up**: «and for women?», «until what age?» — the conversation is taken into account.
- **Browse**: filter by domain (family, labour, housing…), read any law article-by-article.
- **Insights**: corpus statistics and keyword frequencies per domain.

## The corpus

Ingested from the Ministry of Justice's official legal portal ([adala.justice.gov.ma](https://adala.justice.gov.ma)),
**42 documents / 11,600+ articles across 13 domains**, each verified by sha256
(see `data/catalog/laws.yaml`):

| Domain | Laws (examples) |
|---|---|
| civil | قانون الالتزامات والعقود (D.O.C., ar+fr) |
| family | مدونة الأسرة (ar+fr), صندوق التكافل العائلي |
| penal | مجموعة القانون الجنائي (ar+fr), مكافحة غسل الأموال |
| justice | المسطرة المدنية (ar+fr), المسطرة الجنائية, التنظيم القضائي, قضاء القرب, المحاكم المالية |
| labour | مدونة الشغل (ar+fr), العمال المنزليين, حوادث الشغل |
| commercial | مدونة التجارة (ar+fr), شركات المساهمة, المنافسة, المقاول الذاتي |
| education | التعليم العالي, دور الحضانة الخاصة |
| nationality | قانون الجنسية (ar+fr) |
| social | مدونة التأمينات |
| housing | القانون 67.12 المتعلق بالكراء, كراء المحلات التجارية |
| transport | مدونة السير على الطرق (52.05) |
| property | الحقوق العينية, التعمير, الملكية المشتركة, التحفيظ العقاري* |
| governance | الجمعيات, الصحافة والنشر, النقابات, حماية المعطيات الشخصية, الأوقاف, الأجانب, تحصيل الديون العمومية |

Bilingual laws carry both AR and FR editions as separate documents (`group` links them in
the UI). Scanned PDFs (الجنسية، الجمعيات، النقابات، التنظيم القضائي) are OCR'd
automatically at ingest. To add more laws: search the portal
(`adala.justice.gov.ma/search?term=…`), download the PDF into `data/raw/`, and add one YAML
entry — the pipeline handles fetch/verify/OCR/segmentation. Still-wanted texts: الحالة
المدنية 37.10, التعليم الإجباري/الخصوصي (04.00/06.00), مدونة التغطية الصحية 65.00, ميثاق
الاستثمارات 03.22, مدونة الانتخابات.

\* التحفيظ العقاري entry currently holds the application decree; the 1913 dahir text is a
follow-up.

## Architecture

![How Qanoun works: laws are prepared once into Postgres, then each question is searched and answered with citations](docs/figures/architecture.svg)

| Folder | Role |
|---|---|
| `data/catalog/laws.yaml` | the list of laws: slugs, sha256, official source URLs |
| `pipeline/` | fetch → parse (OCR fallback) → split into articles → chunk → embed → load |
| `backend/` | FastAPI: `/api/laws`, `/api/search`, `/api/chat` (SSE), `/api/analytics`; RAG in `rag/` |
| `frontend/` | Next.js 16 + HeroUI v3 + Tailwind 4 + next-intl (ar RTL default, fr, en) |
| `notebooks/`, `backend/.../eval/` | EDA, classification, embedding map, retrieval + LLM-judge eval |

More detail in [docs/architecture.md](docs/architecture.md).

## Testing & evaluation

```bash
make test          # offline unit tests (models faked) + frontend typecheck
make eval-retrieval  # hit@10 / MRR on data/eval/questions.jsonl (needs ingest)
make eval          # + grounded answers judged by the LLM (needs ingest + LLM)
```

The seed eval set covers MSA, Darija, Arabizi and French questions plus abstention probes.

## Common tasks

```bash
make ingest-smoke                      # full pipeline without the embedding model download
uv run --project pipeline python -m qanoun_pipeline.cli summary   # what's in the DB
docker compose up --build              # full stack in containers (api :8000, web :3000)
```

## Status & roadmap

### Done (November 2026)

**Corpus & pipeline**
- [x] 42 documents · 11,624 articles · 13,702 indexed passages · 13 domains · 1913–2023
- [x] 7 laws in both Arabic and French (35 AR + 7 FR documents), linked as one law in the UI
- [x] sha256-verified fetch, OCR fallback for scanned PDFs, article segmentation with
      footnote/sub-article repair, BGE-M3 embeddings, Postgres/pgvector load

**Search & answers**
- [x] Hybrid retrieval (vectors + Arabic full-text, RRF fusion), scoped to a domain or a law
- [x] Darija / Arabizi detection and rewriting to MSA, run in parallel with the first search
- [x] Grounded answers with `[n]` citations to the exact article, explicit abstention
- [x] LLM providers configured in `.env` (Gemini, OpenRouter, NVIDIA NIM, LM Studio/Ollama):
      keys never reach the browser, `.env` changes apply without restart, current models
      picked from each provider's live list, automatic fallback across models and providers,
      busy / out-of-quota / unavailable models remembered and skipped
- [x] ~1.5 s per answer end to end with Gemini flash-lite (progress stages + timings shown)
- [x] Follow-up questions: recent turns are sent with each question; a follow-up («and for
      women?») is rewritten into a standalone question for search, and the answer prompt sees
      the conversation

**Web app** (Next.js 16 · React 19 · HeroUI v3 · Tailwind 4 · TypeScript 7)
- [x] Arabic (RTL) / French / English, light and dark Majorelle theme
- [x] Ask workspace: saved conversations (in the browser), clickable citations opening the
      full article beside the answer, Stop, mobile drawers
- [x] Composer controls: «Search in» (searchable list of 13 domains and 24 laws with article
      counts, Arabic-normalized filtering, one-click reset) and «AI» (Automatic or any
      provider configured in `.env`; unconfigured ones show the key they need)
- [x] Laws: one card per law with its editions, sticky filters; reader with Arabic-normalized
      in-law search, text size, deep links to `#article-N`, copy citation
- [x] Insights: corpus statistics and keyword frequencies per domain
- [x] Phone layout with bottom tab bar; skip link, labelled controls, reduced-motion support

**Quality**
- [x] 65 backend + 47 pipeline tests (offline, models faked), ruff clean, strict typecheck
- [x] CI on every push / pull request: ruff, both test suites, typecheck, production build
      (`.github/workflows/ci.yml`)
- [x] Eval harness: 29 questions (MSA, Darija, Arabizi, French, abstention probes) —
      retrieval hit@k / MRR and LLM-as-judge

### Known limitations

- **Missing texts answer «not found»**: e.g. child *kafala* (law 15.01) is not in the corpus
  yet, so such questions abstain rather than guess.
- **Homonyms** (كفالة = guarantee in the D.O.C. vs. child kafala) can pull the wrong articles
  unless the question is scoped to a domain or law.
- **Single-user by design**: no accounts, no rate limiting, conversations live in one
  browser. Do not expose the API publicly as is.
- **Retrieval misses some short exact articles**: «and for a pregnant woman?» is understood
  correctly, but المادة 133 («تنتهي عدة الحامل بوضع حملها») ranks 20th. Tried and measured on
  `data/eval`: OR-ing keywords (alone, length-normalized, or as a third fused channel) lowers
  hit@10 from 0.923 to 0.846, so it was not shipped — this needs a reranker (below).
- **Free cloud tiers** have daily per-model quotas; fallback absorbs them, heavy use needs a
  paid key or a local model.
- A few old or OCR'd PDFs carry digit / text-direction artifacts in their preambles.

### Roadmap

Next
- [ ] Corpus: كفالة الأطفال المهملين (15.01), الحالة المدنية (37.10), التعليم الإجباري والخصوصي
      (04.00 / 06.00), مدونة التغطية الصحية (65.00), ميثاق الاستثمارات (03.22), مدونة الانتخابات,
      full 1913 التحفيظ العقاري dahir
- [ ] Cross-encoder reranker (e.g. BGE-reranker-v2-m3) over the top ~30 fused candidates,
      opt-in via `.env`; accept only if `make eval-retrieval` beats hit@10 0.923 / MRR 0.759
- [ ] Article-level eval set (expected article numbers, not just laws) so ranking changes
      like the one above are measured precisely
- [ ] Scheduled `make eval` with a history of hit@k / MRR / judge scores

Later
- [ ] Public deployment: authentication, rate limiting, production CORS, Docker image publish
- [ ] Amendment history: which version of an article applies on a given date
- [ ] Export an answer with its cited articles (PDF / print)
- [ ] Accounts with synced conversations

Built by [scorpiontaj](https://github.com/scorpiontaj) — retrieval/eval patterns inherited
from [darija-rag](https://github.com/scorpiontaj/darija-rag).
