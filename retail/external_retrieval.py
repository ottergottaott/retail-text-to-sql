"""External retrieval diagnostics only; SQL is opaque text and is never executed."""
import hashlib
import json
import random
import time
from datetime import datetime, timezone

from .bm25 import BM25
from .embeddings import EmbeddingUnavailable
from .knowledge import cosine
from .retrieval_metrics import ranking_metrics, aggregate_metrics

CUTOFFS = (1, 2, 5, 10)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _case(id, ranked, relevant, elapsed):
    return {"id": id, "returned": [{"id": key, "rank": i} for i, key in enumerate(ranked, 1)],
        "at_k": ranking_metrics(ranked, relevant, CUTOFFS), "positive": any(relevant.values()),
        "returned_count": len(ranked), "latency_ms": elapsed}


def _mode(cases):
    return {"status": "tested", "metrics": aggregate_metrics(cases, CUTOFFS), "cases": cases}


def _untested():
    return {"status": "untested", "reason": "No compatible embedding results; no fallback scored.",
        "metrics": None, "cases": []}


def evaluate_external(corpus, queries, qrels, embedder=None, embedding_source="offline", limit=100, seed=42):
    if embedding_source not in {"offline", "controlled", "live"} or ((embedder is None) != (embedding_source == "offline")):
        raise ValueError("Embedding provenance must match the configured adapter.")
    if embedder is not None and not getattr(embedder, "version", None):
        raise ValueError("Embedding adapter must declare its index version before calls.")
    if not corpus or not queries or type(limit) is not int or not 1 <= limit <= 2048:
        raise ValueError("Nonempty corpus/queries and a limit from 1 to 2048 are required.")
    if any(not isinstance(k, str) or not isinstance(t, str) or not t for k, t in [*corpus.items(), *queries.items()]):
        raise ValueError("Document and query ids/text must be nonempty strings.")
    if any(q not in queries or not isinstance(refs, dict) or not refs or
            any(d not in corpus or type(g) is not int or g not in (0, 1, 2) for d, g in refs.items())
            for q, refs in qrels.items()):
        raise ValueError("Invalid external relevance reference.")
    query_ids = sorted(qrels)
    if not query_ids:
        raise ValueError("No judged queries available.")
    if len(query_ids) > limit:
        query_ids = sorted(random.Random(seed).sample(query_ids, limit))
    bm25 = BM25(corpus)
    lexical, lexical_rankings = [], {}
    for id in query_ids:
        start = time.perf_counter()
        ranked = [r["id"] for r in bm25.search(queries[id], k=10)]
        elapsed = (time.perf_counter() - start) * 1000
        lexical_rankings[id] = ranked
        lexical.append(_case(id, ranked, qrels[id], elapsed))
    modes = {"bm25": _mode(lexical), "vector": _untested(), "bm25_vector_rrf": _untested()}
    calls, indexing_ms = 0, None
    if embedder is not None:
        try:
            started = time.perf_counter()
            ids, vectors = sorted(corpus), []
            for offset in range(0, len(ids), 32):
                batch = ids[offset:offset + 32]
                calls += 1
                embedded = embedder.embed([corpus[id] for id in batch], "RETRIEVAL_DOCUMENT", timeout=15)
                if len(embedded) != len(batch):
                    raise EmbeddingUnavailable()
                vectors.extend(embedded)
            indexing_ms = (time.perf_counter() - started) * 1000
            vector_cases, hybrid_cases = [], []
            for id in query_ids:
                start = time.perf_counter()
                calls += 1
                query = embedder.embed([queries[id]], "RETRIEVAL_QUERY", timeout=10)[0]
                ranked = sorted(zip(ids, vectors), key=lambda pair: (-cosine(query, pair[1]), pair[0]))
                ranked = [key for key, _ in ranked[:10]]
                elapsed = (time.perf_counter() - start) * 1000
                vector_cases.append(_case(id, ranked, qrels[id], elapsed))
                fuse_start = time.perf_counter()
                scores = {}
                for ranking in [lexical_rankings[id], ranked]:
                    for rank, key in enumerate(ranking, 1):
                        scores[key] = scores.get(key, 0) + 1 / (60 + rank)
                fused = sorted(scores, key=lambda key: (-scores[key], key))[:10]
                # Include shared query embedding, vector ranking and BM25 work.
                hybrid_ms = elapsed + (time.perf_counter() - fuse_start) * 1000 + lexical[query_ids.index(id)]["latency_ms"]
                hybrid_cases.append(_case(id, fused, qrels[id], hybrid_ms))
            modes["vector"] = _mode(vector_cases)
            modes["bm25_vector_rrf"] = _mode(hybrid_cases)
        except EmbeddingUnavailable:
            pass
    tested = modes["vector"]["status"] == "tested"
    return {"report_version": "external-retrieval-v1", "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_mode": embedding_source, "corpus_documents": len(corpus), "available_queries": len(qrels),
        "evaluated_queries": len(query_ids), "query_ids": query_ids, "seed": seed,
        "subset": len(query_ids) < len(qrels), "cutoffs": list(CUTOFFS),
        "corpus_digest": _digest(corpus), "queries_digest": _digest({q: queries[q] for q in query_ids}),
        "qrels_digest": _digest({q: qrels[q] for q in query_ids}),
        "embedding_model": embedder.version if embedder else None, "embedding_call_attempts": calls,
        "indexing_ms": indexing_ms, "cost": None, "semantic_threshold": None,
        "semantic_quality": "not_evaluated_controlled_vectors_only" if embedding_source == "controlled" else
            "measured_external_retrieval_only" if embedding_source == "live" and tested else "not_evaluated",
        "latency_scope": "vector includes query embedding; hybrid reuses that embedding and adds BM25/fusion; indexing separate",
        "sql_executed": False, "application_state_accessed": False, "modes": modes}
