# Qanoun evaluation report

- Questions: 65 (scored for retrieval: 26)
- Law-level hit@10: **0.923** (MRR 0.759)
- Article-level hit@10: **0.833** (MRR 0.668, 36 questions)

## History (last 10 runs)

| when (UTC) | commit | reranker | law hit / MRR | article hit / MRR |
|---|---|---|---|---|
| 2026-11-08T22:36:53+00:00 | fc819bd | off | 0.923 / 0.759 | 0.833 / 0.668 |

## Per-question retrieval

| id | variety | expected | hit | rr |
|---|---|---|---|---|
| moudawana-marriage-01 | msa | family-code-ar, family-code-fr | ✓ | 0.12 |
| moudawana-fiance-01 | msa | family-code-ar, family-code-fr | ✓ | 1.00 |
| moudawana-sadaq-01 | msa | family-code-ar, family-code-fr | ✓ | 1.00 |
| moudawana-divorce-01 | msa | family-code-ar, family-code-fr | ✓ | 1.00 |
| moudawana-custody-01 | msa | family-code-ar, family-code-fr | ✓ | 1.00 |
| moudawana-age-01 | darija | family-code-ar, family-code-fr | ✓ | 0.25 |
| moudawana-nafaqa-01 | darija | family-code-ar, family-code-fr | ✓ | 1.00 |
| moudawana-arity-01 | arabizi | family-code-ar, family-code-fr | ✗ | 0.00 |
| moudawana-mariage-fr-01 | other | family-code-fr, family-code-ar | ✓ | 1.00 |
| moudawana-divorce-fr-01 | other | family-code-fr, family-code-ar | ✓ | 1.00 |
| labour-cdd-01 | msa | labour-code-ar, labour-code-fr | ✓ | 1.00 |
| labour-leave-01 | msa | labour-code-ar, labour-code-fr | ✓ | 1.00 |
| labour-dismiss-01 | msa | labour-code-ar, labour-code-fr | ✓ | 1.00 |
| labour-salary-01 | darija | labour-code-ar, labour-code-fr | ✓ | 0.20 |
| labour-try-01 | darija | labour-code-ar, labour-code-fr | ✓ | 1.00 |
| labour-heures-01 | arabizi | labour-code-ar, labour-code-fr | ✗ | 0.00 |
| labour-conge-fr-01 | other | labour-code-fr, labour-code-ar | ✓ | 1.00 |
| labour-licenciement-fr-01 | other | labour-code-fr, labour-code-ar | ✓ | 1.00 |
| doc-contract-01 | msa | obligations-contracts-ar, obligations-contracts-fr | ✓ | 1.00 |
| doc-liability-01 | msa | obligations-contracts-ar, obligations-contracts-fr | ✓ | 0.33 |
| doc-sale-01 | msa | obligations-contracts-ar, obligations-contracts-fr | ✓ | 1.00 |
| doc-contrat-fr-01 | other | obligations-contracts-fr, obligations-contracts-ar | ✓ | 1.00 |
| rental-lease-01 | msa | rental-law-ar | ✓ | 1.00 |
| rental-increase-01 | darija | rental-law-ar | ✓ | 0.33 |
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
| lab-hours-darija | darija | labour-code 184 | ✗ | 0.00 |
| lab-leave-fr | other | labour-code 231 | ✓ | 0.50 |
| lab-seniority-darija | darija | labour-code 232 | ✗ | 0.00 |
| lab-wage | msa | labour-code 345 | ✓ | 1.00 |
| rent-increase-darija | darija | rental 31 | ✗ | 0.00 |
| rent-written | msa | rental 3 | ✓ | 1.00 |
| rent-sale | msa | rental 4 | ✗ | 0.00 |
| rent-payment | msa | rental 12 | ✓ | 1.00 |
| doc-conditions | msa | doc 2 | ✓ | 1.00 |
| doc-binding | msa | doc 230 | ✓ | 1.00 |
| doc-liability-fr | other | doc 77 | ✓ | 0.50 |
| pen-theft | msa | penal-code 505 | ✗ | 0.00 |
