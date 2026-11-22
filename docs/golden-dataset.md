# Synthetic golden knowledge dataset

## Contents and provenance

`retail/data/golden-trios.json` contains **20 additional methodology trios**.
Their IDs are distinct from the original `monthly-revenue`,
`product-comparison`, and `customer-spend` seeds. Every trio is version 1,
`shared`, and `safe-v1`, with the exact origin label
`synthetic demonstration; not historical analyst work`.

The corpus is synthetic and unreviewed. Reports provide analytical methodology,
caveats, and possible follow-up actions; they do not report measured business
figures, claim historical analyst authorship, or establish external causes.
Product cost and price differences are explicitly proxies rather than net profit
or verified promotions. The SQL does not invent order totals, traffic,
acquisition spend, inventory, or external data.

The corpus is not automatically imported at startup. Parent integration adds
`retail-admin load-demo` for explicit synthetic demonstration import. It validates
the whole file before writes, preserves existing IDs/publications, and leaves
real analyst publication on the Governance review path. `--corpus` on the
retrieval evaluator imports only into its isolated temporary store.

## Analytical coverage

| Trio ID | Methodology intent |
| --- | --- |
| `monthly-revenue-change` | Prior-month completed-item revenue comparison with `LAG` |
| `revenue-period-completeness` | Activity boundaries, sparse periods, and freshness caveats |
| `orders-items-grain` | Distinct orders versus item units and items per order |
| `order-item-status-reconciliation` | Mixed order/item status combinations at separate grains |
| `returned-item-rate-finalized` | Returned share with Complete plus Returned denominator |
| `completed-item-share-all-statuses` | Complete share with all recorded statuses as denominator |
| `cancelled-order-share` | Distinct-order cancellation share without item duplication |
| `discount-vs-retail-proxy` | Realized sale price versus listed retail price |
| `category-price-realization` | Aggregate category sale value relative to listed retail value |
| `cost-proxy-margin` | Completed revenue less recorded product cost, with exclusions |
| `product-margin-rate-proxy` | Product margin-rate proxy with aggregate revenue denominator |
| `category-revenue-returns` | Category finalized units, completed revenue, and returns |
| `brand-product-performance` | Brand contribution with item volume and catalog breadth |
| `customer-cohort-repeat` | First-purchase cohorts and repeat purchasing with follow-up caveat |
| `customer-purchase-frequency` | Customer distribution by distinct completed-item order frequency |
| `state-purchaser-demographics` | Coarse state-level observed purchaser activity |
| `age-country-purchaser-mix` | Broad age-band/country mix without individual profiling |
| `active-day-revenue-gaps` | Dates with activity and the ambiguity of missing daily rows |
| `customer-spend-outliers` | Spend/frequency extrema and distribution-oriented follow-up |
| `monthly-product-diagnostic` | Multi-step product revenue, volume, price, and return decomposition |

All queries use only `products`, `order_items`, `orders`, and `users` from the
approved logical schema. They use functions already allowed by
`retail/analytics.py`; no physical table names, sensitive customer columns,
mutations, traffic fields, order-total fields, or unsupported functions are
introduced.

## Expanded retrieval cases

`evaluation/expanded-retrieval-cases.json` contains **98 synthetic, unreviewed
relevance cases**:

- **80 positive paraphrases:** two English and two Russian questions for each of
  the 20 intents, with exact trio ID/version references.
- **18 negatives:** out-of-domain requests, unavailable metrics or schemas,
  PII requests, prompt injection, and a mutation/approval-bypass request.

The labels describe only whether the requested intent has a useful methodology
match in this synthetic corpus. They are not human analyst judgments or live
semantic-quality evidence. Churn is not used as a negative: cohort, repeat
purchase, and inactivity definitions are adjacent methodology and require
clarification rather than an irrelevant label.

Russian cases are intended for multilingual semantic evaluation. The current
lexical tokenizer recognizes ASCII alphanumeric tokens, so English-only trio
text should not be expected to retrieve pure Russian paraphrases through
lexical matching. A low Russian lexical score is not evidence about a real
embedding model; live multilingual relevance remains untested until explicitly
run with a provider.

Negative retrieval behavior must also be measured rather than assumed. Terms
such as `customer`, `department`, or `order` can produce lexical false matches
even when payroll, PII, shipping, or tax methodology is absent. A returned trio
does not make an unavailable metric computable.

## Offline validation and limits

All **20 SQL statements** passed `retail.analytics.validate` and executed through
`Analytics` fixture mode using an in-memory DuckDB fixture with synthetic
principal scope. No application store, credentials, network, BigQuery, or live
provider was used.

Fixture execution confirms validator compatibility and basic SQL mechanics only.
It does not prove live BigQuery behavior, production data quality, business
correctness, usefulness of recommendations, or real semantic relevance. The
small fixture cannot substantiate empty-period, outlier, cohort, demographic,
or return-rate conclusions; reports deliberately provide methods and caveats
instead of measured outcomes.

Parent integration loaded the corpus into an isolated store and ran expanded
lexical retrieval: Recall@2 0.50 overall, 0.95 English and 0.05 Russian; negative
false-match rate 0.4444. All 40 two-principal SQL checks and six independent
fixture oracles passed. See retrieval-verification.md. Live embedding results
remain untested and must be labeled separately. Dataset relevance labels remain synthetic and unreviewed unless a
human reviewer subsequently approves them.
