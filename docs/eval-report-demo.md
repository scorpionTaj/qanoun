# Qanoun evaluation report

- Questions: 65 (scored for retrieval: 26)
- Law-level hit@10: **0.923** (MRR 0.856)
- Article-level hit@10: **0.778** (MRR 0.584, 36 questions)
- With Darija/Arabizi rewriting (what /chat serves): law-level **1.0** (MRR 0.896), article-level **0.833** (MRR 0.609)

## History (last 10 runs)

| when (UTC) | commit | embedder | reranker | rewrite | law hit / MRR | article hit / MRR | page hit / MRR | cited hit / MRR |
|---|---|---|---|---|---|---|---|---|
| 2026-11-08T22:36:53+00:00 | fc819bd | BAAI/bge-m3 | off | off | 0.923 / 0.759 | 0.833 / 0.668 | – | – |
| 2026-11-08T22:44:13+00:00 | fc819bd | BAAI/bge-m3 | BAAI/bge-reranker-v2-m3 | off | 0.923 / 0.767 | 0.889 / 0.623 | – | – |
| 2026-11-10T22:43:39+00:00 | d9b4d09 | BAAI/bge-m3 | off | off | 0.962 / 0.798 | 0.833 / 0.668 | 0.727 / 0.607 | 0.704 / 0.575 |
| 2026-11-10T22:44:44+00:00 | d9b4d09 | BAAI/bge-m3 | off | on | 1.0 / 0.869 | 0.917 / 0.689 | 0.879 / 0.689 | 0.85 / 0.65 |
| 2026-11-12T03:50:09+00:00 | e2424fa | jina-embeddings-v3 | off | off | 0.923 / 0.856 | 0.778 / 0.584 | 0.746 / 0.607 | 0.712 / 0.553 |
| 2026-11-12T03:54:20+00:00 | e2424fa | jina-embeddings-v3 | off | on | 1.0 / 0.896 | 0.833 / 0.609 | 0.894 / 0.688 | 0.869 / 0.629 |

## darija-rag question set (264 questions)

Ported from darija-rag (`scripts/port_darija_rag_eval.py`). **Page-level**: any article printed on a labelled page is in the top 10, which is darija-rag's own criterion. **Cited article**: the article the reference answer cites is in the top 10. *Raw* searches the question as typed; *+ rewrite* is what /chat does (Darija and Arabizi rewritten to MSA, both searches merged).

| Page-level | n | raw hit@10 / MRR | + rewrite hit@10 / MRR |
|---|---|---|---|
| all | 264 | 0.746 / 0.607 | 0.894 / 0.688 |
| msa | 117 | 0.94 / 0.789 | 0.94 / 0.789 |
| darija | 59 | 0.576 / 0.428 | 0.864 / 0.64 |
| arabizi | 31 | 0.065 / 0.038 | 0.774 / 0.318 |
| other | 57 | 0.895 / 0.73 | 0.895 / 0.73 |

| Cited article | n | raw hit@10 / MRR | + rewrite hit@10 / MRR |
|---|---|---|---|
| all | 260 | 0.712 / 0.553 | 0.869 / 0.629 |
| msa | 114 | 0.921 / 0.759 | 0.921 / 0.759 |
| darija | 58 | 0.483 / 0.327 | 0.81 / 0.522 |
| arabizi | 31 | 0.032 / 0.011 | 0.742 / 0.278 |
| other | 57 | 0.895 / 0.667 | 0.895 / 0.667 |

Page-level misses (+ rewrite):

- drag-q015 (darija): شنو هي الحقوق اللي كتاخد المرا ملي كتطلق؟
- drag-q021 (msa): لمن تخول الحضانة بالترتيب؟
- drag-q022 (darija): شكون اللي عندو الحق يربي الدراري الأول من بعد الطلاق؟
- drag-q027 (darija): فشحال من عام كيولي الواحد راشد فالقانون؟
- drag-q030 (darija): شحال نقدر نوصي من المال ديالي؟
- drag-q031 (msa): هل يمكن التنازل عن صفة الوارث للغير؟
- drag-q062 (msa): إلى ماذا يرجع فيما لم يرد به نص في مدونة الأسرة؟
- drag-q063 (arabizi): chno howa sen rochd f lmaghrib?
- drag-q065 (arabizi): chkoun li 3ando l7a9 f l7adana lewel?
- drag-q070 (arabizi): chhal n9der nwessi men lflous dyali?
- drag-q071 (other): Quel est l'âge de la majorité légale au Maroc ?
- drag-q077 (other): Quelle part de ses biens peut-on léguer par testament ?
- drag-q106 (darija): إلا تزوجت شحال من نهار كيعطيوني رخصة؟
- drag-q130 (msa): ما الحق المترتب عن الفصل التعسفي؟
- drag-q168 (arabizi): wach 3andi l7a9 nrad3 weldi f lkhedma?
- drag-q180 (other): Que s'applique-t-il quand le Code de la famille ne prévoit rien ?
- drag-q196 (arabizi): kifach nkhrej lkari men dari?
- drag-q204 (other): Le bail d'habitation doit-il être écrit ?
- drag-q206 (darija): مول الدار باع الدار، واش خاصني نخرج؟
- drag-q207 (other): Si le propriétaire vend le logement, le bail continue-t-il ?
- drag-q229 (msa): ما المحكمة المختصة في نزاعات الكراء السكني؟
- drag-q230 (msa): ما هي مصادر الالتزامات؟
- drag-q236 (other): Un contrat signé sous la contrainte est-il valable ?
- drag-q239 (arabizi): wa7d dar liya dorr, wach khaso y3wdni?
- drag-q241 (msa): هل يجوز إلغاء العقد بإرادة طرف واحد؟
- drag-q260 (darija): واش الكونطرا ديال الحانوت خاصها تكون مكتوبة؟
- drag-q268 (darija): مول الحانوت بغا يخرجني، واش عندي الحق فالتعويض؟
- drag-q269 (arabizi): mol l7anout bgha ykhrjni, wach 3ndi l7a9 f ta3wid?

## Per-question retrieval

| id | variety | expected | hit | rr |
|---|---|---|---|---|
| moudawana-marriage-01 | msa | family-code-ar, family-code-fr | ✓ | 0.14 |
| moudawana-fiance-01 | msa | family-code-ar, family-code-fr | ✓ | 1.00 |
| moudawana-sadaq-01 | msa | family-code-ar, family-code-fr | ✓ | 1.00 |
| moudawana-divorce-01 | msa | family-code-ar, family-code-fr | ✓ | 1.00 |
| moudawana-custody-01 | msa | family-code-ar, family-code-fr | ✓ | 1.00 |
| moudawana-age-01 | darija | family-code-ar, family-code-fr | ✓ | 0.14 |
| moudawana-nafaqa-01 | darija | family-code-ar, family-code-fr | ✓ | 1.00 |
| moudawana-arity-01 | arabizi | family-code-ar, family-code-fr | ✓ | 0.50 |
| moudawana-mariage-fr-01 | other | family-code-fr, family-code-ar | ✓ | 1.00 |
| moudawana-divorce-fr-01 | other | family-code-fr, family-code-ar | ✓ | 1.00 |
| labour-cdd-01 | msa | labour-code-ar, labour-code-fr | ✓ | 1.00 |
| labour-leave-01 | msa | labour-code-ar, labour-code-fr | ✓ | 1.00 |
| labour-dismiss-01 | msa | labour-code-ar, labour-code-fr | ✓ | 1.00 |
| labour-salary-01 | darija | labour-code-ar, labour-code-fr | ✓ | 1.00 |
| labour-try-01 | darija | labour-code-ar, labour-code-fr | ✓ | 1.00 |
| labour-heures-01 | arabizi | labour-code-ar, labour-code-fr | ✓ | 0.50 |
| labour-conge-fr-01 | other | labour-code-fr, labour-code-ar | ✓ | 1.00 |
| labour-licenciement-fr-01 | other | labour-code-fr, labour-code-ar | ✓ | 1.00 |
| doc-contract-01 | msa | obligations-contracts-ar, obligations-contracts-fr | ✓ | 1.00 |
| doc-liability-01 | msa | obligations-contracts-ar, obligations-contracts-fr | ✓ | 1.00 |
| doc-sale-01 | msa | obligations-contracts-ar, obligations-contracts-fr | ✓ | 1.00 |
| doc-contrat-fr-01 | other | obligations-contracts-fr, obligations-contracts-ar | ✓ | 1.00 |
| rental-lease-01 | msa | rental-law-ar | ✓ | 1.00 |
| rental-increase-01 | darija | rental-law-ar | ✓ | 1.00 |
| rental-depart-01 | darija | rental-law-ar | ✓ | 1.00 |
| commercial-lease-01 | msa | commercial-lease-ar | ✓ | 1.00 |

## Per-question retrieval (article level)

| id | variety | expected | hit | rr |
|---|---|---|---|---|
| fam-age | msa | moudawana 19 | ✗ | 0.00 |
| fam-underage | other | moudawana 20 | ✓ | 0.33 |
| fam-definition | msa | moudawana 4 | ✓ | 1.00 |
| fam-gifts | msa | moudawana 8 | ✓ | 0.50 |
| fam-sadaq | msa | moudawana 26 | ✓ | 1.00 |
| fam-polygamy | msa | moudawana 40 | ✓ | 1.00 |
| fam-dues | msa | moudawana 84 | ✓ | 1.00 |
| fam-shiqaq | msa | moudawana 94 | ✗ | 0.00 |
| fam-harm | msa | moudawana 99 | ✓ | 1.00 |
| fam-consent-fr | other | moudawana 114 | ✓ | 0.50 |
| fam-khul | msa | moudawana 115 | ✓ | 0.17 |
| fam-idda-widow | msa | moudawana 132 | ✓ | 1.00 |
| fam-idda-pregnant | msa | moudawana 133 | ✓ | 0.33 |
| fam-idda-divorced | msa | moudawana 136 | ✓ | 1.00 |
| fam-custody | msa | moudawana 171 | ✗ | 0.00 |
| fam-support-age | msa | moudawana 198 | ✓ | 1.00 |
| fam-sadaq-due | msa | moudawana 31 | ✓ | 1.00 |
| lab-probation | msa | labour-code 13 | ✓ | 1.00 |
| lab-probation-fr | other | labour-code 14 | ✓ | 1.00 |
| lab-cdd | msa | labour-code 16 | ✓ | 0.33 |
| lab-notice | msa | labour-code 43 | ✓ | 1.00 |
| lab-severance | msa | labour-code 52 | ✓ | 0.50 |
| lab-minors | msa | labour-code 143 | ✓ | 0.25 |
| lab-maternity-fr | other | labour-code 152 | ✓ | 1.00 |
| lab-hours-darija | darija | labour-code 184 | ✓ | 0.50 |
| lab-leave-fr | other | labour-code 231 | ✓ | 1.00 |
| lab-seniority-darija | darija | labour-code 232 | ✓ | 0.17 |
| lab-wage | msa | labour-code 345 | ✓ | 1.00 |
| rent-increase-darija | darija | rental 31 | ✓ | 0.33 |
| rent-written | msa | rental 3 | ✓ | 1.00 |
| rent-sale | msa | rental 4 | ✗ | 0.00 |
| rent-payment | msa | rental 12 | ✓ | 0.50 |
| doc-conditions | msa | doc 2 | ✓ | 1.00 |
| doc-binding | msa | doc 230 | ✗ | 0.00 |
| doc-liability-fr | other | doc 77 | ✓ | 0.50 |
| pen-theft | msa | penal-code 505 | ✗ | 0.00 |
