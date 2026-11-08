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
**45 documents / 11,700+ articles across 13 domains**, each verified by sha256
(see `data/catalog/laws.yaml`):

| Domain | Laws (examples) |
|---|---|
| civil | قانون الالتزامات والعقود (D.O.C., ar+fr) |
| family | مدونة الأسرة (ar+fr), صندوق التكافل العائلي |
| penal | مجموعة القانون الجنائي (ar+fr), مكافحة غسل الأموال |
| justice | المسطرة المدنية (ar+fr), المسطرة الجنائية, التنظيم القضائي, قضاء القرب, المحاكم المالية |
| labour | مدونة الشغل (ar+fr), العمال المنزليين, حوادث الشغل |
| commercial | مدونة التجارة (ar+fr), شركات المساهمة, المنافسة, المقاول الذاتي, ميثاق الاستثمار (03.22) |
| education | التعليم العالي, التعليم المدرسي الخصوصي (06.00), دور الحضانة الخاصة |
| nationality | قانون الجنسية (ar+fr) |
| social | مدونة التأمينات |
| housing | القانون 67.12 المتعلق بالكراء, كراء المحلات التجارية |
| transport | مدونة السير على الطرق (52.05) |
| property | الحقوق العينية, التعمير, الملكية المشتركة, ظهير التحفيظ العقاري (1913, consolidated) |
| governance | الجمعيات, الصحافة والنشر, النقابات, حماية المعطيات الشخصية, الأوقاف, الأجانب, تحصيل الديون العمومية |

Bilingual laws carry both AR and FR editions as separate documents (`group` links them in
the UI). Scanned PDFs (الجنسية، الجمعيات، النقابات، التنظيم القضائي) are OCR'd
automatically at ingest. To add more laws: search the portal
(`adala.justice.gov.ma/search?term=…`), download the PDF into `data/raw/`, and add one YAML
entry — the pipeline handles fetch/verify/OCR/segmentation (`scripts/expand_catalog.py
--slugs …` adds candidates). Not on the portal as a law text (searched November 2026):
child *kafala* 15.01 (only a ministry circular), الحالة المدنية 37.10, مدونة التغطية الصحية
65.00, مدونة الانتخابات.

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
make test          # offline unit tests (models faked) + frontend typecheck and unit tests
make eval-retrieval  # law- and article-level hit@10 / MRR (needs ingest)
make eval          # + grounded answers judged by the LLM (needs ingest + LLM)
```

The seed eval set covers MSA, Darija, Arabizi and French questions plus abstention probes;
`data/eval/articles.jsonl` adds 36 questions with the exact expected article. Every run
appends to `data/eval/history.jsonl` and the report (`docs/eval-report.md`) shows the trend.

| run | law hit@10 / MRR | article hit@10 / MRR |
|---|---|---|
| hybrid (default) | 0.923 / 0.759 | 0.833 / 0.668 |
| + reranker `BAAI/bge-reranker-v2-m3` | 0.923 / 0.767 | 0.889 / 0.623 |

The reranker finds more right articles but ranks them lower on average and adds latency, so
it stays opt-in (`QANOUN_RERANKER=BAAI/bge-reranker-v2-m3`).

## Common tasks

```bash
make ingest-smoke                      # full pipeline without the embedding model download
uv run --project pipeline python -m qanoun_pipeline.cli summary   # what's in the DB
docker compose up --build              # full stack in containers (api :8000, web :3000)
make user EMAIL=you@example.com        # create an account (asks for the password)
```

## Deploy

Accounts are optional: without one, everything works and conversations stay in the browser.
Signed in, conversations sync to the server (newest copy wins).

1. On the server, copy `.env.example` to `.env` and set at least one LLM key plus:
   `POSTGRES_PASSWORD`, `QANOUN_PUBLIC_API_URL=https://api.your-domain`,
   `QANOUN_CORS_ORIGINS=https://your-domain`.
2. Start the stack: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
   — the database is not exposed, API and web listen on 127.0.0.1 only, sign-up is closed,
   and the session cookie is HTTPS-only.
3. Put a TLS reverse proxy in front (Caddy: `your-domain { reverse_proxy localhost:3000 }`
   and `api.your-domain { reverse_proxy localhost:8000 }`). Keep both on one site
   (`example.com` + `api.example.com`) so the `SameSite=Lax` session cookie is sent.
4. Load the corpus once: `make ingest` against the production database, then create the first
   account (admin): `make user EMAIL=you@your-domain`.

Built in: per-IP rate limits (20 questions / min, 10 sign-in attempts / min; in memory, so
one API process), scrypt password hashing, httpOnly session cookies stored only as hashes, a
CSRF guard (JSON-only writes from allowed origins), security headers on API and web, and
container healthchecks.

## Status & roadmap

### Done (November 2026)

**Corpus & pipeline**
- [x] 45 documents · 11,748 articles · 13,880 indexed passages · 13 domains · 1913–2023
- [x] 7 laws in both Arabic and French (38 AR + 7 FR documents), linked as one law in the UI
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
- [x] Amendments: each law lists the amending texts named in its official footnotes, with
      links to the changed articles and an «Amended» badge on each
- [x] Print / save as PDF: an answer with its question, cited articles and disclaimer
- [x] Settings page: AI model, answer length and language, sources per answer, default
      search scope, export or delete conversations, optional account
- [x] Optional accounts (email + password) with conversations synced across devices
- [x] Insights: corpus statistics and keyword frequencies per domain
- [x] Phone layout with bottom tab bar; skip link, labelled controls, reduced-motion support

**Quality**
- [x] 81 backend + 47 pipeline + frontend unit tests (offline, models faked), ruff clean,
      strict typecheck
- [x] CI on every push / pull request: ruff, both test suites, typecheck, production build
      (`.github/workflows/ci.yml`)
- [x] Eval harness: 29 questions (MSA, Darija, Arabizi, French, abstention probes) plus 36
      article-level questions — hit@k / MRR per law and per article, run history, LLM-as-judge
- [x] Opt-in cross-encoder reranker, measured against the eval before deciding

### Known limitations

- **Missing texts answer «not found»**: e.g. child *kafala* (law 15.01) is not on the portal
  as a law text, so such questions abstain rather than guess.
- **Homonyms** (كفالة = guarantee in the D.O.C. vs. child kafala) can pull the wrong articles
  unless the question is scoped to a domain or law.
- **Rate limits are per API process** (in memory). Running several API replicas needs the
  limit in the reverse proxy instead.
- **Amendments are what the footnotes say**, not point-in-time versions: the text shown is
  the current consolidated one, and a few footnotes name no article.
- **Retrieval misses some short exact articles**: «and for a pregnant woman?» is understood
  correctly, but المادة 133 («تنتهي عدة الحامل بوضع حملها») ranks 20th. Tried and measured on
  `data/eval`: OR-ing keywords (alone, length-normalized, or as a third fused channel) lowers
  hit@10 from 0.923 to 0.846, so it was not shipped. The opt-in reranker raises article-level
  hit@10 (0.833 → 0.889) but not MRR.
- **Free cloud tiers** have daily per-model quotas; fallback absorbs them, heavy use needs a
  paid key or a local model.
- A few old or OCR'd PDFs carry digit / text-direction artifacts in their preambles.

### Roadmap

- [ ] Corpus: الحالة المدنية (37.10), مدونة التغطية الصحية (65.00), مدونة الانتخابات, child
      *kafala* (15.01) — when published as texts on the portal or another official source
- [ ] Reranker that improves MRR, not just hit@10 (fine-tune, or rerank only the top 10)
- [ ] Point-in-time versions of amended articles
- [ ] Password reset by email; publish Docker images from CI

Built by [scorpiontaj](https://github.com/scorpiontaj) — retrieval/eval patterns inherited
from [darija-rag](https://github.com/scorpiontaj/darija-rag).
