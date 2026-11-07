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

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker, Node 20+, and for the chat an
OpenAI-compatible LLM endpoint ([LM Studio](https://lmstudio.ai) at `localhost:1234/v1` or
Ollama — see `.env.example`).

```bash
cp .env.example .env           # adjust QANOUN_LLM_URL if needed
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
- **Browse**: filter by domain (family, labour, housing…), read any law article-by-article.
- **Insights**: corpus statistics and keyword frequencies per domain.

## The corpus

Seeded from the Ministry of Justice portal ([adala.justice.gov.ma](https://adala.justice.gov.ma)),
8 documents / 6 laws, each verified by sha256 (see `data/catalog/laws.yaml` — add entries to
grow the corpus; candidate education/penal/nationality laws are listed there):

| Law | Number | Year | Domain | Editions |
|---|---|---|---|---|
| مدونة الأسرة (Moudawana) | 70-03 | 2004 | family | ar + fr |
| مدونة الشغل | 65-99 | 2004 | labour | ar + fr |
| قانون الالتزامات والعقود (D.O.C.) | DOC | 1913 | civil | ar + fr |
| القانون 67.12 المتعلق بالكراء | 67-12 | 2023 | housing | ar |
| كراء المحلات التجارية | — | 1962 | commercial | ar |

## Architecture

```
data/catalog/laws.yaml        seed catalog: slugs, sha256, official source URLs
pipeline/                     DE package (uv, src-layout)
  sources/fetch.py            catalog-driven downloads with integrity checks
  parse.py / ocr.py           PyMuPDF text layer; tesseract Arabic/French OCR fallback
  structure.py                article segmentation (the citation unit)
  chunk.py / embed.py         overlapping chunks; BGE-M3 with per-text cache
  load_db.py / schema.py      Postgres/pgvector loader; DDL single source of truth
backend/                      FastAPI
  rag/retrieval.py            hybrid search: pgvector + FTS fused by RRF
  rag/rewrite.py              Darija/Arabizi detection + LLM rewriting to MSA
  rag/answer.py               grounded answering, citation parsing, abstention
  routers/                    /api/laws, /api/search, /api/chat (SSE), /api/analytics
  eval/run.py                 retrieval metrics + LLM-as-judge → docs/eval-report.md
frontend/                     Next.js 15 + Tailwind + next-intl (ar RTL default, fr, en)
notebooks/                    EDA, classification experiment, embedding map (percent-format)
```

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

- [x] Pipeline: 8/8 seed documents segment cleanly (4.5k+ articles)
- [x] Hybrid retrieval + Darija rewriting + grounded streaming chat
- [x] Trilingual UI with RTL and citation deep-links
- [x] Eval harness + notebooks
- [ ] Grow corpus: education (51.17), penal code, nationality (scraper for the Bulletin Officiel)
- [ ] Retrieval reranker (cross-encoder) and answer quality eval dashboard
- [ ] Auth + saved conversations

Built by [scorpiontaj](https://github.com/scorpiontaj) — retrieval/eval patterns inherited
from [darija-rag](https://github.com/scorpiontaj/darija-rag).
