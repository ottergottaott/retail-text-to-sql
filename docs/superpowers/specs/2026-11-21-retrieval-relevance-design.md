# English Golden Knowledge relevance

Goal: reduce irrelevant Golden Trio retrieval without losing supported English
questions. Retrieved methods are advisory, never authorization or current facts.

Diagnosis: healthy hybrid retrieval currently admits every lexical hit into RRF,
including candidates rejected by semantic similarity. Negative queries therefore
return trios even when vector-only retrieval correctly returns none.

Approaches: add an LLM/reranker (extra latency/cost), tune word overlap (brittle),
or gate lexical additions using existing query/document cosine scores. Choose
the existing embeddings: no new dependency or model call. Calibrate a floor
on a deterministic development split; record English validation separately.
Keep strong semantic-only matches and RRF ordering. Missing vectors and provider
failure must remain explicit; never call partially checked retrieval fully gated.
The agent may still answer schema-supported questions without Golden examples.

Keep the evaluated baseline instruction while isolating retrieval-policy changes.
Preserve latest-version/schema/product filtering and bounded provider calls.
Fallback remains lexical when embeddings are unavailable, labeled as such.
Synthetic relevance metrics do not prove report accuracy or analyst acceptance.
