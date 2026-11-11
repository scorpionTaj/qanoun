# Qanoun evaluation report

- Questions: 65 (scored for retrieval: 26)
- Law-level hit@10: **0.962** (MRR 0.798)
- Article-level hit@10: **0.833** (MRR 0.668, 36 questions)
- With Darija/Arabizi rewriting (what /chat serves): law-level **1.0** (MRR 0.869), article-level **0.917** (MRR 0.689)
- LLM-judge averages (1–5): {'faithfulness': 4.58, 'grounding': 4.74, 'completeness': 3.95} over 19 answers, judged by openrouter
- Abstention: 2 correct refusals, 3 wrong calls (answered an out-of-scope question, or refused an answerable one)
- 5 answers were not graded (the judge failed or replied without JSON)

## History (last 10 runs)

| when (UTC) | commit | reranker | rewrite | law hit / MRR | article hit / MRR | page hit / MRR | cited hit / MRR |
|---|---|---|---|---|---|---|---|
| 2026-11-08T22:36:53+00:00 | fc819bd | off | off | 0.923 / 0.759 | 0.833 / 0.668 | – | – |
| 2026-11-08T22:44:13+00:00 | fc819bd | BAAI/bge-reranker-v2-m3 | off | 0.923 / 0.767 | 0.889 / 0.623 | – | – |
| 2026-11-10T22:43:39+00:00 | d9b4d09 | off | off | 0.962 / 0.798 | 0.833 / 0.668 | 0.727 / 0.607 | 0.704 / 0.575 |
| 2026-11-10T22:44:44+00:00 | d9b4d09 | off | on | 1.0 / 0.869 | 0.917 / 0.689 | 0.879 / 0.689 | 0.85 / 0.65 |

## darija-rag question set (264 questions)

Ported from darija-rag (`scripts/port_darija_rag_eval.py`). **Page-level**: any article printed on a labelled page is in the top 10, which is darija-rag's own criterion. **Cited article**: the article the reference answer cites is in the top 10. *Raw* searches the question as typed; *+ rewrite* is what /chat does (Darija and Arabizi rewritten to MSA, both searches merged).

| Page-level | n | raw hit@10 / MRR | + rewrite hit@10 / MRR |
|---|---|---|---|
| all | 264 | 0.727 / 0.607 | 0.879 / 0.689 |
| msa | 117 | 0.966 / 0.869 | 0.966 / 0.869 |
| darija | 59 | 0.492 / 0.298 | 0.831 / 0.54 |
| arabizi | 31 | 0.097 / 0.052 | 0.742 / 0.288 |
| other | 57 | 0.825 / 0.69 | 0.825 / 0.69 |

| Cited article | n | raw hit@10 / MRR | + rewrite hit@10 / MRR |
|---|---|---|---|
| all | 260 | 0.704 / 0.575 | 0.85 / 0.65 |
| msa | 114 | 0.956 / 0.845 | 0.956 / 0.845 |
| darija | 58 | 0.431 / 0.259 | 0.759 / 0.48 |
| arabizi | 31 | 0.065 / 0.032 | 0.677 / 0.248 |
| other | 57 | 0.825 / 0.651 | 0.825 / 0.651 |

Page-level misses (+ rewrite):

- drag-q015 (darija): شنو هي الحقوق اللي كتاخد المرا ملي كتطلق؟
- drag-q061 (darija): نقدر نوصي لولدي بشي حاجة زايدة على الورث ديالو؟
- drag-q064 (arabizi): wach rajel y9der yzewej 3la mrato bla ma ykoun 3ando lflous?
- drag-q070 (arabizi): chhal n9der nwessi men lflous dyali?
- drag-q071 (other): Quel est l'âge de la majorité légale au Maroc ?
- drag-q098 (msa): متى يستحق الأجير العطلة السنوية المؤدى عنها؟
- drag-q106 (darija): إلا تزوجت شحال من نهار كيعطيوني رخصة؟
- drag-q138 (darija): المرا الخدامة ملي كتولد شحال كتاخد ديال الكونجي؟
- drag-q154 (arabizi): men b3d chhal mn chhar n9der nakhod conge mkhalles?
- drag-q168 (arabizi): wach 3andi l7a9 nrad3 weldi f lkhedma?
- drag-q171 (darija): واش الكونجي كيزيد مع الأقدمية؟
- drag-q180 (other): Que s'applique-t-il quand le Code de la famille ne prévoit rien ?
- drag-q204 (other): Le bail d'habitation doit-il être écrit ?
- drag-q205 (msa): ماذا يحدث لعقد الكراء إذا بيع المحل المكترى؟
- drag-q206 (darija): مول الدار باع الدار، واش خاصني نخرج؟
- drag-q207 (other): Si le propriétaire vend le logement, le bail continue-t-il ?
- drag-q216 (darija): مول الدار بغا يزيد فالكرا، شحال يقدر يزيد؟
- drag-q218 (other): De combien le loyer peut-il être augmenté ?
- drag-q221 (other): Pour quels motifs le bailleur peut-il demander l'expulsion du locataire ?
- drag-q226 (arabizi): tle9t w ana 3ndi lwlad, wach n9der nb9a f dar dyal lkra?
- drag-q229 (msa): ما المحكمة المختصة في نزاعات الكراء السكني؟
- drag-q235 (darija): سنيت عقد وأنا مضغوط عليا، واش نقدر نبطلو؟
- drag-q236 (other): Un contrat signé sous la contrainte est-il valable ?
- drag-q238 (darija): واحد خسر ليا الطوموبيل، واش خاصو يعوضني؟
- drag-q239 (arabizi): wa7d dar liya dorr, wach khaso y3wdni?
- drag-q241 (msa): هل يجوز إلغاء العقد بإرادة طرف واحد؟
- drag-q245 (arabizi): chhal mn 3am kayt9adem l7a9 f dyn?
- drag-q256 (arabizi): wach n9der nchreT lfayda 3la sslf?
- drag-q260 (darija): واش الكونطرا ديال الحانوت خاصها تكون مكتوبة؟
- drag-q261 (other): Le bail commercial doit-il être écrit ?
- drag-q270 (other): Le locataire commercial a-t-il droit à une indemnité d'éviction ?
- drag-q276 (other): Le locataire peut-il céder son droit au bail sans l'accord du bailleur ?

## Per-question retrieval

| id | variety | expected | hit | rr |
|---|---|---|---|---|
| moudawana-marriage-01 | msa | family-code-ar, family-code-fr | ✓ | 0.12 |
| moudawana-fiance-01 | msa | family-code-ar, family-code-fr | ✓ | 1.00 |
| moudawana-sadaq-01 | msa | family-code-ar, family-code-fr | ✓ | 1.00 |
| moudawana-divorce-01 | msa | family-code-ar, family-code-fr | ✓ | 1.00 |
| moudawana-custody-01 | msa | family-code-ar, family-code-fr | ✓ | 1.00 |
| moudawana-age-01 | darija | family-code-ar, family-code-fr | ✓ | 0.12 |
| moudawana-nafaqa-01 | darija | family-code-ar, family-code-fr | ✓ | 1.00 |
| moudawana-arity-01 | arabizi | family-code-ar, family-code-fr | ✓ | 1.00 |
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
| doc-liability-01 | msa | obligations-contracts-ar, obligations-contracts-fr | ✓ | 0.33 |
| doc-sale-01 | msa | obligations-contracts-ar, obligations-contracts-fr | ✓ | 1.00 |
| doc-contrat-fr-01 | other | obligations-contracts-fr, obligations-contracts-ar | ✓ | 1.00 |
| rental-lease-01 | msa | rental-law-ar | ✓ | 1.00 |
| rental-increase-01 | darija | rental-law-ar | ✓ | 1.00 |
| rental-depart-01 | darija | rental-law-ar | ✓ | 0.50 |
| commercial-lease-01 | msa | commercial-lease-ar | ✓ | 1.00 |

## Per-question retrieval (article level)

| id | variety | expected | hit | rr |
|---|---|---|---|---|
| fam-age | msa | moudawana 19 | ✓ | 0.12 |
| fam-underage | other | moudawana 20 | ✓ | 0.11 |
| fam-definition | msa | moudawana 4 | ✓ | 1.00 |
| fam-gifts | msa | moudawana 8 | ✓ | 1.00 |
| fam-sadaq | msa | moudawana 26 | ✓ | 1.00 |
| fam-polygamy | msa | moudawana 40 | ✓ | 1.00 |
| fam-dues | msa | moudawana 84 | ✓ | 1.00 |
| fam-shiqaq | msa | moudawana 94 | ✗ | 0.00 |
| fam-harm | msa | moudawana 99 | ✓ | 1.00 |
| fam-consent-fr | other | moudawana 114 | ✓ | 0.17 |
| fam-khul | msa | moudawana 115 | ✓ | 0.14 |
| fam-idda-widow | msa | moudawana 132 | ✓ | 1.00 |
| fam-idda-pregnant | msa | moudawana 133 | ✓ | 1.00 |
| fam-idda-divorced | msa | moudawana 136 | ✓ | 0.50 |
| fam-custody | msa | moudawana 171 | ✓ | 1.00 |
| fam-support-age | msa | moudawana 198 | ✓ | 1.00 |
| fam-sadaq-due | msa | moudawana 31 | ✓ | 1.00 |
| lab-probation | msa | labour-code 13 | ✓ | 1.00 |
| lab-probation-fr | other | labour-code 14 | ✓ | 1.00 |
| lab-cdd | msa | labour-code 16 | ✓ | 1.00 |
| lab-notice | msa | labour-code 43 | ✓ | 1.00 |
| lab-severance | msa | labour-code 52 | ✓ | 0.50 |
| lab-minors | msa | labour-code 143 | ✓ | 0.50 |
| lab-maternity-fr | other | labour-code 152 | ✓ | 1.00 |
| lab-hours-darija | darija | labour-code 184 | ✓ | 0.25 |
| lab-leave-fr | other | labour-code 231 | ✓ | 0.50 |
| lab-seniority-darija | darija | labour-code 232 | ✓ | 0.17 |
| lab-wage | msa | labour-code 345 | ✓ | 1.00 |
| rent-increase-darija | darija | rental 31 | ✓ | 0.33 |
| rent-written | msa | rental 3 | ✓ | 1.00 |
| rent-sale | msa | rental 4 | ✗ | 0.00 |
| rent-payment | msa | rental 12 | ✓ | 1.00 |
| doc-conditions | msa | doc 2 | ✓ | 1.00 |
| doc-binding | msa | doc 230 | ✓ | 1.00 |
| doc-liability-fr | other | doc 77 | ✓ | 0.50 |
| pen-theft | msa | penal-code 505 | ✗ | 0.00 |

## Abstention probes

- abstain-traffic-01: ✗ answered
- abstain-weather-01: ✓ abstained
- abstain-criminal-01: ✓ abstained
