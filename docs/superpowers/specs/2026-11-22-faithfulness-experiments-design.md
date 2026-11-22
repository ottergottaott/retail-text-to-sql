# Faithfulness experiments and local Langfuse

## Intent and authorization
Implement the experiment loop requested on 2026-11-22: local Langfuse, a larger English evaluation set, a current v8 baseline, and paired improvements with retained failures. The user authorized the preceding five-step design with `/goal сделать это и улучшить консистентно метрики`.

## Approach
Use local self-hosted Langfuse as the comparison interface and retain versioned JSON as authoritative evidence. Cloud hosting adds unnecessary credential and data transfer decisions. Replacing Ragas or tuning its standard scoring instructions would break the requested comparison, so keep standard Ragas 0.4.4 unchanged and custom SQL-aware scores separately named.

## Design
- Isolated Compose project on loopback port 3001, independent volumes and generated local credentials. Preserve the existing WebUI and application stores. Pin released images. Verify authenticated ingestion and retrieval of a scored trace, not merely container health.
- Export evaluation datasets, per-case traces, experiment identity and numeric scores. Default to metadata/hashes for existing live evidence. Detailed synthetic inputs/outputs may be captured explicitly; never export settings, credentials or unreviewed personal data.
- Freeze the current serving prompt v8 and model/judge identities. The historical 0.534 standard score belongs to v7 and is not a v8 baseline.
- Create 80 English scenarios grouped into 40 development, 20 validation and 20 sealed test scenarios. Family/template relatives must stay together; synthetic evidence is labeled and is not BigQuery ground truth. Previously exposed cases remain regression/development. Keep the sealed test unread during tuning.
- Batch paid execution, retaining the existing per-batch limits, with generation/judge/time bounds, progress and resumable immutable results. Capture standard metric statement diagnostics without modifying the metric instructions.
- Improve one concrete failure mode at a time. Paired comparisons use identical questions/evidence/models/judge contracts. Track completeness/task success and factual/SQL checks alongside faithfulness, plus tokens and latency. Missing/failed samples make a run incomplete; do not select only successes.
- Promotion needs complete paired coverage, positive validation mean delta, no material correctness/completeness regression, independent review and a sealed test confirmation. Report per-case deltas and uncertainty; a small positive mean alone is not evidence of consistent improvement. Never promise a target score before measurement.
- Run fresh live end-to-end smoke/regression separately from frozen-evidence prompt experiments. Preserve unsuccessful iterations and historical handoff artifacts.

## Completion evidence
Local dashboard with retrieved scored experiment; validated split manifest; baseline and candidate artifacts with coverage/diagnostics; full tests; independent bounded DeepSeek audit; concise report distinguishing observed improvements, remaining errors and untested surfaces.
