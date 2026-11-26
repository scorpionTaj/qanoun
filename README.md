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

**Live demo: [qanoun-ma.vercel.app](https://qanoun-ma.vercel.app)**, on free tiers only: the web
app and the API on Vercel, the database on Supabase. To fit a serverless function, the demo
embeds with Jina's API instead of running BGE-M3; its retrieval scores are measured below.
The API's interactive documentation (Swagger UI) is at
[qanoun-api.vercel.app](https://qanoun-api.vercel.app). The same answers are in an
**Android app** ([latest release](https://github.com/scorpionTaj/qanoun/releases/latest)), a
**Telegram bot** ([@QanounMABot](https://t.me/QanounMABot)) and an **MCP server** for AI agents.

<p align="center">
  <img src="docs/figures/demo.gif" alt="Qanoun demo: asking a question in English, the cited Labour Code article opening beside the answer, browsing laws, the amendments panel, a Darija question answered from the rental law in Arabic (RTL), and the settings page" width="800">
</p>
<p align="center"><sub>Ask in English, French, Arabic or Darija → answer with clickable citations → read the article, its amendments, and the whole law.</sub></p>

## The three layers

| Layer | What it does | Where |
|---|---|---|
| **Data engineering** | fetch (sha256-verified) → Arabic PDF parse + OCR fallback → article segmentation (footnote-glue repair, sub-numbers, sequence checks) → chunking → BGE-M3 embeddings → Postgres/pgvector | `pipeline/` |
| **AI** | hybrid retrieval (pgvector cosine + Arabic FTS, RRF fusion), Darija/Arabizi query rewriting via glossary + LLM, grounded answering with `[n]` citations and explicit abstention, streaming SSE | `backend/src/qanoun_api/rag/` |
| **Data science** | corpus EDA, keyword-domain classification experiments, embedding-space map, retrieval + LLM-as-judge evaluation | `notebooks/`, `backend/src/qanoun_api/eval/` |

## What it does

- **Ask** in Arabic, Darija, Arabizi, French or English. Dialect questions are rewritten to
  Arabic before searching, and follow-ups («and for women?») keep the conversation. The answer
  streams in, cites the exact articles as `[n]`, and says «not found» rather than guess when the
  texts don't answer.
- **Read** every law article by article: in-law search, deep links to `#article-N`, the
  amendments each article went through (from the official footnotes), and its
  cross-references, both the articles it cites and those that cite it (about 7,300 links).
- **Choose the AI**: Gemini, OpenRouter, NVIDIA NIM, LM Studio or Ollama, configured on the
  server only. A busy or out-of-quota model falls back to the next one automatically.
- **Keep your work**: conversations are saved in the browser or, with an optional account,
  synced across the web app and the phone app together with your settings. Answers print or
  save as PDF with their cited articles.
- **Use it elsewhere**: the Android app (also offline reading of saved laws), the Telegram
  bot, the MCP server, and a REST API with optional keys.
- **Trust the numbers**: retrieval is measured on 326 labelled questions, and a weekly CI job
  fails if the live demo gets worse.

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

### Use it from an AI agent (MCP)

The API is also an [MCP](https://modelcontextprotocol.io) server, so Claude, Cursor and other
agents can search and read the corpus and cite it:

```bash
claude mcp add --transport http qanoun https://qanoun-api.vercel.app/mcp
```

| tool | what it returns |
|---|---|
| `search_laws(query, domain?, law?, k?)` | the best-matching articles for an MSA or French query (the agent rewrites Darija/Arabizi first, as told by the tool), with a link into the reader |
| `get_article(law, article)` | one article in full, the articles it cites and those that cite it |
| `list_laws(domain?)` | the laws and implementing decrees: slug, titles, number, year, domain |

It is read-only and has no `ask` tool: the agent writes the answer from the articles, so the
server spends no LLM quota. Set `QANOUN_WEB_URL` to your web app's address for the links.

### Telegram bot

Ask in a private chat with [@QanounMABot](https://t.me/QanounMABot), in Arabic, Darija,
French or English: the answer comes from the same retrieval and citation checks as the web
app, followed by the cited articles as links into the reader. It is off unless
`QANOUN_TELEGRAM_TOKEN` is set; after deploying, register the webhook once:

```bash
uv run --project backend python -m qanoun_api.telegram set-webhook https://<api-host>/api/telegram/webhook
```

Only Telegram can call the webhook (a secret derived from the token is checked on every call).
Each question stands alone (no follow-ups yet), and the chat limit applies per Telegram chat.

### Mobile app

`mobile/` is an Expo (React Native) app for Android and iOS on the same API: streamed answers
with tappable citations, the laws and the reader, laws saved for offline reading, sharing an
article, the same settings as the web app (AI provider and model, answer length and language,
theme, app language), and an optional account that syncs settings and conversations.

Each release tag builds the Android app in GitHub Actions and attaches `qanoun-<version>.apk`
(install it directly) and `.aab` (Play Store) to the
[GitHub release](https://github.com/scorpionTaj/qanoun/releases). To run it from source:
`cd mobile && npm ci && npx expo start`. Details, including release signing, are in
[mobile/README.md](mobile/README.md).

### API keys

Reading laws and articles needs nothing. Search and the MCP server are rate-limited per address
(30 searches and 60 MCP requests a minute, 20 questions a minute for `/api/chat`); signed-in
users can create keys on the Settings page for a higher limit, counted per account (120
searches and 240 MCP requests a minute; questions stay at 20):

```bash
curl -H "Authorization: Bearer qk_…" -H "Content-Type: application/json" \
     -d '{"q": "مدة الرخصة السنوية"}' https://qanoun-api.vercel.app/api/search
claude mcp add --transport http qanoun https://qanoun-api.vercel.app/mcp \
     --header "Authorization: Bearer qk_…"
```

A key is shown once, stored only as a hash, and can be revoked at any time; a revoked or
unknown key gets `401` rather than the anonymous limit. A key never opens the account itself.

In the Swagger UI (the API's home page) everything above can be tried directly: sign up or
sign in and create a key under *auth* / *api keys*, paste it in **Authorize**, then run
`/api/search` or `/mcp` (examples for each MCP tool are in its request body menu).

## The corpus

Ingested from the Ministry of Justice's official legal portal ([adala.justice.gov.ma](https://adala.justice.gov.ma)),
**59 laws + 8 implementing decrees / 14,696 articles across 13 domains**, each verified by sha256
(see `data/catalog/laws.yaml`):

| Domain | Laws (examples) |
|---|---|
| civil | قانون الالتزامات والعقود (D.O.C., ar+fr) |
| family | مدونة الأسرة (ar+fr), الحالة المدنية (36.21), كفالة الأطفال المهملين (15.01), صندوق التكافل العائلي |
| penal | مجموعة القانون الجنائي (ar+fr), مكافحة غسل الأموال, محاربة العنف ضد النساء (103.13) |
| justice | المسطرة المدنية (ar+fr), المسطرة الجنائية, التنظيم القضائي, قضاء القرب, المحاكم المالية, مهنة المحاماة (66.23) |
| labour | مدونة الشغل (ar+fr), العمال المنزليين, حوادث الشغل |
| commercial | مدونة التجارة (ar+fr), شركات المساهمة, الشركات الأخرى (5.96, ar+fr), حماية المستهلك (31.08, ar+fr), المنافسة, المقاول الذاتي, ميثاق الاستثمار (03.22) |
| education | التعليم العالي, التعليم المدرسي الخصوصي (06.00), دور الحضانة الخاصة |
| nationality | قانون الجنسية (ar+fr) |
| social | مدونة التغطية الصحية الأساسية (65.00, AMO), مدونة التأمينات |
| housing | القانون 67.12 المتعلق بالكراء, كراء المحلات التجارية |
| transport | مدونة السير على الطرق (52.05) |
| property | الحقوق العينية, التعمير, الملكية المشتركة, ظهير التحفيظ العقاري (1913, consolidated) |
| governance | الدستور (2011, ar+fr), مدونة الانتخابات (9.97), الحق في الحصول على المعلومات (31.13, ar+fr), الجمعيات, الصحافة والنشر, النقابات, حماية المعطيات الشخصية, الأوقاف, الأجانب, تحصيل الديون العمومية |

Bilingual laws carry both AR and FR editions as separate documents (`group` links them in
the UI). Scanned PDFs (الجنسية، الجمعيات، النقابات، التنظيم القضائي) are OCR'd
automatically at ingest. To add more laws: search the portal
(`adala.justice.gov.ma/search?term=…`), download the PDF into `data/raw/`, and add one YAML
entry — the pipeline handles fetch/verify/OCR/segmentation (`scripts/expand_catalog.py
--slugs …` adds candidates). The portal publishes consolidated texts with footnotes and
amendment notes that also start lines with «المادة N»; segmentation keeps those in the
article body when they cite another text or quote a former wording.

## Architecture

![Qanoun architecture: an offline ingest pipeline (adala.justice.gov.ma PDFs → PyMuPDF / Tesseract OCR → articles → chunks → BGE-M3 embeddings) loads PostgreSQL + pgvector; per question, the Next.js app calls FastAPI, which detects Darija, rewrites to MSA, runs hybrid dense + full-text search with RRF (optional reranker), prompts an LLM through a provider router (Gemini, OpenRouter, NVIDIA NIM, Ollama, LM Studio) and streams a cited answer back over SSE](docs/figures/architecture.svg)

### Two flows, one database

1. **Ingest (offline, `make ingest`).** Each law in `data/catalog/laws.yaml` is downloaded from
   [adala.justice.gov.ma](https://adala.justice.gov.ma) and checked against its sha256. Text comes from the PDF text
   layer (PyMuPDF), falling back to Tesseract OCR (Arabic + French) for scanned pages. It is
   then split into articles using each law's own heading word (المادة / Article / الفصل),
   repaired (glued footnotes, sub-articles like `65-1` or `مكرر`), cut into 180-word passages
   with 40 words of overlap, embedded with BGE-M3 (1024 dimensions, cached by sha256) and
   loaded into Postgres. Every step re-derives from `data/raw/`, so re-running is always safe.
2. **Ask (online, per question).** The browser posts the question to `/api/chat`. FastAPI
   detects the variety (MSA, Darija, Arabizi, French) and, for dialect, rewrites it to MSA
   while the first search is already running. It embeds the question with the same BGE-M3
   model and runs **one SQL query with two channels**: cosine search over the HNSW vector
   index and Arabic-normalized full-text search. The two are fused with reciprocal rank
   fusion (and optionally reranked, blended with that order). The top articles go to the LLM as
   numbered sources, and the answer streams back over SSE (`meta → sources → token* → done`)
   with `[n]` citations — or an explicit «not found» when the sources don't answer.

### Tech stack

| Layer | Tools | What they do here |
|---|---|---|
| Data source | 🏛 [adala.justice.gov.ma](https://adala.justice.gov.ma) | Ministry of Justice portal: official consolidated texts (PDF) |
| Pipeline | <img src="https://img.shields.io/badge/Python_3.13-3776AB?logo=python&logoColor=white&style=flat-square" alt="Python 3.13"> <img src="https://img.shields.io/badge/uv-DE5FE9?logo=uv&logoColor=white&style=flat-square" alt="uv"> <img src="https://img.shields.io/badge/PyMuPDF-C0392B?logo=python&logoColor=white&style=flat-square" alt="PyMuPDF"> <img src="https://img.shields.io/badge/Tesseract_OCR-1E7F4F?style=flat-square" alt="Tesseract OCR"> | fetch + sha256 check, PDF text, OCR fallback (ara + fra), article segmentation |
| Embeddings | <img src="https://img.shields.io/badge/Hugging_Face-FFD21E?logo=huggingface&logoColor=black&style=flat-square" alt="Hugging Face"> <img src="https://img.shields.io/badge/BGE--M3-FF9D00?logo=huggingface&logoColor=black&style=flat-square" alt="BGE-M3"> <img src="https://img.shields.io/badge/PyTorch-EE4C2C?logo=pytorch&logoColor=white&style=flat-square" alt="PyTorch"> <img src="https://img.shields.io/badge/sentence--transformers-3776AB?logo=python&logoColor=white&style=flat-square" alt="sentence-transformers"> | 1024-dim multilingual vectors (strong on Arabic); optional `bge-reranker-v2-m3` cross-encoder |
| Database | <img src="https://img.shields.io/badge/PostgreSQL_19-4169E1?logo=postgresql&logoColor=white&style=flat-square" alt="PostgreSQL 19"> <img src="https://img.shields.io/badge/pgvector-336791?logo=postgresql&logoColor=white&style=flat-square" alt="pgvector"> | laws / articles (`tsvector` GIN) / chunks (`vector(1024)` HNSW) + users, sessions, synced conversations |
| API | <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white&style=flat-square" alt="FastAPI"> <img src="https://img.shields.io/badge/Uvicorn-499848?logo=python&logoColor=white&style=flat-square" alt="Uvicorn"> <img src="https://img.shields.io/badge/Pydantic-E92063?logo=pydantic&logoColor=white&style=flat-square" alt="Pydantic"> <img src="https://img.shields.io/badge/psycopg_3-336791?logo=postgresql&logoColor=white&style=flat-square" alt="psycopg 3"> <img src="https://img.shields.io/badge/httpx-3776AB?logo=python&logoColor=white&style=flat-square" alt="httpx"> | REST + SSE streaming, RAG, auth, rate limits, security headers |
| LLMs | <img src="https://img.shields.io/badge/Google_Gemini-8E75B2?logo=googlegemini&logoColor=white&style=flat-square" alt="Google Gemini"> <img src="https://img.shields.io/badge/OpenRouter-6467F2?logo=openrouter&logoColor=white&style=flat-square" alt="OpenRouter"> <img src="https://img.shields.io/badge/NVIDIA_NIM-76B900?logo=nvidia&logoColor=white&style=flat-square" alt="NVIDIA NIM"> <img src="https://img.shields.io/badge/Ollama-000000?logo=ollama&logoColor=white&style=flat-square" alt="Ollama"> <img src="https://img.shields.io/badge/LM_Studio-4338CA?logo=lmstudio&logoColor=white&style=flat-square" alt="LM Studio"> | any OpenAI-compatible provider; keys only in `.env`; automatic fallback across models and providers |
| Web app | <img src="https://img.shields.io/badge/Next.js_16-000000?logo=nextdotjs&logoColor=white&style=flat-square" alt="Next.js 16"> <img src="https://img.shields.io/badge/React_19-149ECA?logo=react&logoColor=white&style=flat-square" alt="React 19"> <img src="https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white&style=flat-square" alt="TypeScript"> <img src="https://img.shields.io/badge/HeroUI_v3-000000?logo=heroui&logoColor=white&style=flat-square" alt="HeroUI v3"> <img src="https://img.shields.io/badge/Tailwind_CSS_4-06B6D4?logo=tailwindcss&logoColor=white&style=flat-square" alt="Tailwind CSS 4"> <img src="https://img.shields.io/badge/next--intl-26A69A?logo=i18next&logoColor=white&style=flat-square" alt="next-intl"> <img src="https://img.shields.io/badge/Recharts-22B5BF?logo=chartdotjs&logoColor=white&style=flat-square" alt="Recharts"> | trilingual UI (Arabic RTL, French, English), Ask workspace, law reader, insights, settings |
| Mobile app | <img src="https://img.shields.io/badge/Expo_SDK_58-000020?logo=expo&logoColor=white&style=flat-square" alt="Expo SDK 58"> <img src="https://img.shields.io/badge/React_Native-149ECA?logo=react&logoColor=white&style=flat-square" alt="React Native"> <img src="https://img.shields.io/badge/expo--router-000020?logo=expo&logoColor=white&style=flat-square" alt="expo-router"> | Android and iOS app on the same API: streaming answers, reader, offline saved laws, synced account |
| Quality | <img src="https://img.shields.io/badge/pytest-0A9EDC?logo=pytest&logoColor=white&style=flat-square" alt="pytest"> <img src="https://img.shields.io/badge/Ruff-D7FF64?logo=ruff&logoColor=black&style=flat-square" alt="Ruff"> <img src="https://img.shields.io/badge/node:test-5FA04E?logo=nodedotjs&logoColor=white&style=flat-square" alt="node:test"> <img src="https://img.shields.io/badge/GitHub_Actions-2088FF?logo=githubactions&logoColor=white&style=flat-square" alt="GitHub Actions"> | offline tests (models faked), lint, strict typecheck, build on every push; retrieval + LLM-judge eval |
| Deploy | <img src="https://img.shields.io/badge/Docker_Compose-2496ED?logo=docker&logoColor=white&style=flat-square" alt="Docker Compose"> <img src="https://img.shields.io/badge/Caddy-1F88C0?logo=caddy&logoColor=white&style=flat-square" alt="Caddy"> | db · api · web containers with healthchecks; production override behind a TLS proxy |

### Repository layout

| Folder | Role |
|---|---|
| `data/catalog/laws.yaml` | the list of laws: slugs, sha256, official source URLs, per-law article words |
| `pipeline/` | fetch → parse (OCR fallback) → split into articles → chunk → embed → load; owns the DB schema |
| `backend/` | FastAPI: `/api/laws` (+ amendments), `/api/search`, `/api/chat` (SSE), `/api/auth`, `/api/conversations`, `/api/analytics` (+ admin `usage` from the query log); RAG in `rag/`, eval in `eval/` |
| `frontend/` | Next.js 16 + HeroUI v3 + Tailwind 4 + next-intl (ar RTL default, fr, en) |
| `mobile/` | Expo app (Android, iOS); the Android build runs in `.github/workflows/release.yml` |
| `deploy/` | the Vercel function that serves the API on the demo |
| `scripts/` | catalog expansion, portal watcher, re-embedding, eval set port, test fixture |
| `data/eval/`, `docs/eval-report.md` | question sets (law- and article-level), run history, latest report |
| `notebooks/` | EDA, classification, embedding map |
| `docker-compose*.yml` | local stack and production override |

More detail (design principles, retrieval SQL, prompt contract) in [docs/architecture.md](docs/architecture.md).

## Testing & evaluation

```bash
make test          # offline unit tests (models faked) + frontend typecheck and unit tests
QANOUN_TEST_DB_URL=postgresql://qanoun:qanoun@localhost:5433/qanoun make test
                   # + the tests that need Postgres (migrations, load, rate limit, query log)
# browser smoke test: seed a fixture law, run the API and `npm run build && npm start`, then
QANOUN_DB_URL=… uv run --project pipeline python scripts/seed_fixture.py
cd frontend && npx playwright install chromium && npm run e2e
make eval-retrieval  # questions searched as typed: hit@10 / MRR, no LLM (needs ingest)
make eval-rewrite  # + retrieval as /chat does it: Darija/Arabizi rewritten to MSA (needs an LLM)
make eval          # + grounded answers judged by an LLM; add a second provider as judge with
                   #   `python -m qanoun_api.eval.run --judge openrouter`
```

Three question sets, all scored on the full 45-document corpus, top 10, no reranker:

| question set | n | as typed: hit@10 / MRR | as /chat retrieves: hit@10 / MRR |
|---|---|---|---|
| seed, right law (`questions.jsonl`) | 26 | 0.962 / 0.798 | **1.000** / 0.869 |
| seed, exact article (`articles.jsonl`) | 36 | 0.833 / 0.668 | **0.917** / 0.689 |
| darija-rag set, an article on the labelled page (`pages.jsonl`) | 264 | 0.727 / 0.607 | **0.879** / 0.689 |
| darija-rag set, the article the reference answer cites | 260 | 0.704 / 0.575 | **0.850** / 0.650 |

"As /chat retrieves" searches the question and its MSA rewrite and merges both, which is
what users get. The darija-rag set by language, page-level hit@10:

| | MSA (117) | Darija (59) | Arabizi (31) | French (57) |
|---|---|---|---|---|
| as typed | 0.966 | 0.492 | 0.097 | 0.825 |
| as /chat retrieves | 0.966 | **0.831** | **0.742** | 0.825 |

**The live demo** embeds with `jina-embeddings-v3` instead of BGE-M3 (see Deploy). Measured
the same way ([report](docs/eval-report-demo.md)), it is close: page-level hit@10 0.894 as
/chat retrieves (Darija 0.898, Arabizi 0.871, MSA 0.940, French 0.895), cited article 0.873,
and on the seed sets 1.000 for the right law and 0.778 for the exact article. (Re-measured on
the 55-document corpus after the rewrite prompt stopped naming codes and adding boilerplate:
Arabizi 0.774 → 0.871 and Darija 0.864 → 0.898 page-level; the exact-article seed set lost
two Darija questions that sit near rank 10, 0.833 → 0.778.)

The same questions scored 0.93 in [darija-rag](https://github.com/scorpionTaj/darija-rag)
(Darija 0.95, Arabizi 0.90), on 8 documents and with a reranker. Here they compete with 67
documents and no reranker by default; `scripts/port_darija_rag_eval.py` explains the port.

**Answers** (29 seed questions, generated by the default provider, graded by a different
one, OpenRouter): faithfulness 4.58, grounding 4.74, completeness 3.95 out of 5 over the 19
answers graded. 5 were answered but not graded (the judge failed), 2 out-of-scope probes
were correctly refused, and 3 abstention calls were wrong.

Every run appends to `data/eval/history.jsonl` and the report (`docs/eval-report.md`) shows
the trend, the per-language tables and the misses. `--max-drop 0.02` turns a run into a gate:
it exits 1 when a metric falls more than 0.02 below the previous run of the same setup.
`.github/workflows/eval.yml` runs that gate on the live demo weekly, on demand, and on pull
requests that touch retrieval, through a read-only database role.

**Reranker** (opt-in, `QANOUN_RERANKER`): the fused top 20 are re-scored by a reranker and
re-ordered by blending its ranking with the fused one, which raises MRR, not only hit@10.
Measured on the 323 questions as typed against the demo, with Jina's
`jina-reranker-v2-base-multilingual` ([`eval/rerank_study.py`](backend/src/qanoun_api/eval/rerank_study.py)):

| | law hit / MRR | article hit / MRR | page hit / MRR |
|---|---|---|---|
| fused (default) | 0.923 / 0.837 | 0.778 / 0.583 | 0.742 / 0.604 |
| reranker order alone | 0.923 / 0.851 | 0.833 / 0.617 | 0.758 / 0.624 |
| **blended (what `QANOUN_RERANKER` does)** | 0.923 / **0.864** | **0.833 / 0.669** | **0.758 / 0.635** |

Replacing the fused order with the reranker's sometimes buried an exact match; blended, it
mostly moves good candidates up. Jina's reranker runs anywhere but costs about 3,000 tokens
per question, so it is off on the free demo; a local cross-encoder
(`BAAI/bge-reranker-v2-m3`) costs nothing per call. A failed rerank keeps the fused order.

## Common tasks

```bash
uv run --project pipeline python -m qanoun_pipeline.cli refs   # rebuild cross-references (no re-ingest)
make ingest-smoke                      # full pipeline without the embedding model download
uv run --project pipeline python -m qanoun_pipeline.cli summary   # what's in the DB
docker compose up --build              # full stack in containers (api :8000, web :3000)
make user EMAIL=you@example.com        # create an account (asks for the password)
```

### Upgrading Postgres (pg17 → pg19)

The database image moved to Postgres 19 on a new volume (`pgdata19`), so the first `make db`
after pulling starts empty. Postgres can't open an older major version's data files, so the old
`pgdata` volume is left untouched. Either re-run `make ingest` (the corpus is re-derivable), or
carry everything over, including accounts and conversations:

```bash
docker run -d --name pg17 -v qanoun_pgdata:/var/lib/postgresql/data \
  -e POSTGRES_PASSWORD=qanoun pgvector/pgvector:pg17
docker exec pg17 pg_dump -U qanoun -Fc qanoun > qanoun.dump && docker rm -f pg17
make db && docker compose exec -T db pg_restore -U qanoun -d qanoun --no-owner < qanoun.dump
docker volume rm qanoun_pgdata                     # once you're happy with the new one
```

## Deploy

### Free demo: Vercel + Supabase

This is how [qanoun-ma.vercel.app](https://qanoun-ma.vercel.app) runs, at no cost:

- **Embeddings:** BGE-M3 is a 2 GB model, too large for a serverless function, so the demo
  uses Jina's `jina-embeddings-v3` API at 1024 dimensions (`QANOUN_EMBED_MODEL`), for both the
  passages and each question. The corpus was re-embedded once with
  [`scripts/reembed.py`](scripts/reembed.py) in about 12 minutes. (Gemini's free embedding
  tier was tried first; it allows 1,000 embeddings a day, two weeks for this corpus.)
- **Database:** a free Supabase project. The tables live in a `qanoun` schema, which
  Supabase's public Data API does not expose, owned by a dedicated `qanoun_api` role. The API
  connects through the IPv4 **transaction** pooler (port 6543), not the session pooler (5432):
  each warm serverless instance kept a session open, and the free tier's 15 session slots ran
  out, so a new instance could not connect. Behind the transaction pooler an idle instance
  holds no server connection (30 concurrent requests: all 200). One-off CLI runs (ingest,
  `cli refs`) can use either port.
- **API:** a Vercel Python function in Paris (`cdg1`), built from
  [`deploy/vercel-api/`](deploy/vercel-api) with `QANOUN_DB_URL`, `QANOUN_JINA_KEY`, an LLM key
  (`QANOUN_GEMINI_KEY`), `QANOUN_EMBED_MODEL`, `QANOUN_CORS_ORIGINS`,
  `QANOUN_ALLOW_SIGNUP=false`, `QANOUN_TRUST_PROXY=true` (rate limits per visitor, not per
  Vercel proxy), `QANOUN_REWRITE_CACHE=/tmp/rewrites.json` and, for the build,
  `UV_NO_EDITABLE=1`. PyMuPDF is left out of the function: only ingestion reads PDFs.
- **Web app:** a second Vercel project with `frontend/` as its root and `NEXT_PUBLIC_API_URL`
  pointing at the API.

Free-tier limits apply: Supabase pauses a project after a week without traffic (restore it
from the dashboard), Jina's free key covers a fixed number of tokens (each question uses a
few dozen), and Gemini's free tier limits answers per minute and per day.

### Prebuilt images

Each release tag publishes two images to GitHub Container Registry, for amd64 and arm64:

- `ghcr.io/scorpiontaj/qanoun-api`: the API, slim (no PyTorch), so it embeds questions through
  Jina's API: set `QANOUN_EMBED_MODEL=jina-embeddings-v3` and `QANOUN_JINA_KEY`, plus
  `QANOUN_DB_URL` and an LLM key. For the local BGE-M3 model, build it yourself with
  `--build-arg EXTRAS=models` (the compose file does). On Linux, PyTorch comes from its
  CPU-only index (a ~4 GB image instead of 20 GB with CUDA); for a GPU server, remove the
  `sys_platform == 'linux'` source in `backend/pyproject.toml` and re-lock.
- `ghcr.io/scorpiontaj/qanoun-web`: the web app. The API's address is read at runtime:
  `QANOUN_PUBLIC_API_URL` (what browsers call) and, if server rendering should use another
  route, `QANOUN_API_URL` (e.g. `http://api:8000` on a Docker network).

The database must be loaded once with the same embedder (`make ingest`, or
[`scripts/reembed.py`](scripts/reembed.py) for Jina).

### Your own server

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

Built in: per-IP rate limits (20 questions / min, 10 sign-in attempts / min), counted in
Postgres so every API process and serverless instance shares them; a query log of every
question's outcome, provider and timings, without IPs or user ids (question text only with
`QANOUN_LOG_QUESTIONS=true`; admins read abstention rate, p50/p95 latency and the questions
the corpus could not answer at `GET /api/analytics/usage`); scrypt password hashing, httpOnly session cookies stored only as hashes, a
CSRF guard (JSON-only writes from allowed origins), security headers on API and web, and
container healthchecks.

### Privacy and Law 09-08

Qanoun is built to comply with Moroccan **Law No. 09-08** on personal data protection:

- **Information (art. 5):** a privacy notice in Arabic, French and English at `/privacy`, linked
  from every page, the sign-up form, the Android app and the Telegram bot. Its facts come from
  `GET /api/privacy`, so it names the AI services actually configured and their countries.
- **Consent (art. 4):** sign-up requires accepting the notice; the time is stored
  (`users.privacy_accepted_at`).
- **Rights (art. 7–9):** signed-in users download everything kept about them
  (`GET /api/auth/export`) and delete their account with their password
  (`POST /api/auth/delete-account`; conversations, settings, keys and sessions go with it).
- **Minimisation and retention (art. 3):** no account needed; the query log has no IP or user
  id and is deleted after 90 days; rate-limit counters (IP or Telegram chat) last minutes.
- **Transfers abroad (art. 43–44):** questions go to the configured LLM (and Jina for
  embeddings); the notice lists them and the chat asks users not to type personal details.
  A local model (LM Studio / Ollama) keeps questions on your server.

What the operator of a public server still has to do:
1. Declare the processing to the **CNDP** ([cndp.ma](https://www.cndp.ma)) and, for an LLM
   or embedding service outside Morocco, request the transfer authorization (art. 43–44).
2. Set `QANOUN_PRIVACY_CONTROLLER`, `QANOUN_PRIVACY_CONTACT` and `QANOUN_CNDP_RECEIPT`.
3. Keep `QANOUN_LOG_QUESTIONS=false` unless the notice and your declaration cover it.

## Known limitations

- **Only what the portal publishes as text.** Laws missing from
  [adala.justice.gov.ma](https://adala.justice.gov.ma) as a law text are missing here, and
  questions about them get «not found» rather than a guess. The weekly portal watcher
  (`.github/workflows/watch-portal.yml`) proposes updated uploads of the catalog's laws.
- **Homonyms** (كفالة = guarantee in the D.O.C. vs. child kafala) can pull the wrong articles
  unless the question is scoped to a domain or law.
- **Amendments are what the footnotes say**, not past wording: the portal publishes only the
  current consolidated text, so the history lists what changed and when, not what the article
  said before. The year is the one in the amending text's number («12.18» → 2018); its
  promulgation can be a year later. A few footnotes name no article.
- **Dialect questions are the weak spot**: with rewriting, Darija reaches 0.83 and Arabizi
  0.74 page-level hit@10 against 0.97 for MSA; without it Arabizi is at 0.10.
- **Retrieval misses some short exact articles**: «and for a pregnant woman?» is understood
  correctly, but المادة 133 («تنتهي عدة الحامل بوضع حملها») ranks 20th. OR-ing keywords lowered
  hit@10 (0.923 → 0.846), so it was not shipped.
- **Text-layer artifacts**: most Arabic PDFs swap the لا ligature («األولى» for «الأولى»). The
  vector search copes, but full-text search misses those words and the reader shows them as
  extracted. A few old or OCR'd PDFs carry digit or
  text-direction artifacts in their preambles.
- **Free cloud tiers** have daily per-model quotas; fallback absorbs them, heavy use needs a
  paid key or a local model.

Built by [scorpiontaj](https://github.com/scorpiontaj) — retrieval/eval patterns inherited
from [darija-rag](https://github.com/scorpiontaj/darija-rag).

## License

[AGPL-3.0](LICENSE), matching PyMuPDF, which the ingestion pipeline uses to read the PDFs.
The law texts are the Kingdom of Morocco's official publications.
