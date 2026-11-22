"""Isolated held-out retrieval comparison using the existing Knowledge contracts."""
import hashlib
import json
import math
import re
import tempfile
import time
from datetime import datetime, timezone
from types import SimpleNamespace

from .embeddings import EmbeddingUnavailable
from .knowledge import Knowledge, cosine
from .security import principal_for
from .store import Store
from .retrieval_metrics import ranking_metrics, aggregate_metrics, cutoffs_validated
from .bm25 import BM25


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _validate_cases(cases):
    validated, ids = [], set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Each retrieval case must be an object.")
        if not isinstance(case.get("id"), str) or not case["id"].strip():
            raise ValueError("Each retrieval case requires a nonempty id.")
        if case["id"] in ids:
            raise ValueError(f"Duplicate retrieval case id: {case['id']}")
        if not isinstance(case.get("question"), str) or not case["question"].strip():
            raise ValueError(f"Case {case['id']} requires a nonempty question.")
        if not isinstance(case.get("relevant"), list):
            raise ValueError(f"Case {case['id']} requires a relevant list.")
        relevant = []
        for reference in case["relevant"]:
            if (not isinstance(reference, dict) or not isinstance(reference.get("id"), str)
                    or not reference["id"] or type(reference.get("version")) is not int
                    or reference["version"] < 1):
                raise ValueError(f"Case {case['id']} has an invalid relevant id/version reference.")
            grade = reference.get("grade", 1)
            if type(grade) is not int or grade not in (1, 2):
                raise ValueError("Relevant reference grades must be 1 or 2; omit irrelevant references.")
            pair = {"id": reference["id"], "version": reference["version"], "grade": grade}
            if any(r["id"] == pair["id"] and r["version"] == pair["version"] for r in relevant):
                raise ValueError("Duplicate relevance reference; provide one grade per id/version.")
            relevant.append(pair)
        ids.add(case["id"])
        language = case.get("language") or ("ru" if re.search("[а-яё]", case["question"], re.I) else "en")
        if language not in {"en", "ru", "other"}:
            raise ValueError("Case language must be en, ru or other.")
        validated.append({"id": case["id"], "question": case["question"], "relevant": relevant,
            "language": language})
    return validated


def _corpus_version(knowledge):
    corpus = [{"id": t["id"], "version": t["version"], "schema_version": t.get("schema_version"),
        "question": t["question"], "tags": t["tags"], "sql": t["sql"], "report": t["report"],
        "scope": t.get("scope"), "products": t.get("products")}
        for t in sorted(knowledge.published(), key=lambda t: t["id"])]
    return _digest(corpus)


def _index_version(store):
    rows = sorted(store.list("embedding", "system"), key=lambda row: row["id"])
    if not rows:
        return None
    return _digest([{"id": row["id"], "trio": row["body"]["trio"], "version": row["body"]["version"],
        "model": row["body"]["model"], "vector_digest": _digest(row["body"]["vector"])} for row in rows])


def _eligible(knowledge, principal):
    eligible = []
    for trio in knowledge.published():
        if trio.get("schema_version") != "safe-v1":
            continue
        if trio.get("scope") != "shared" and (trio.get("scope") != "products" or not trio.get("products")
                or not set(trio["products"]) <= set(principal.products)):
            continue
        eligible.append(trio)
    return eligible


def _vector_retrieve(knowledge, principal, question, k=2):
    vectors = {row["id"]: row["body"]["vector"] for row in knowledge.store.list("embedding", "system")}
    indexed = [t for t in _eligible(knowledge, principal) if knowledge.vector_id(t) in vectors]
    if not indexed:
        raise EmbeddingUnavailable("No compatible vectors are indexed.")
    query = knowledge.embedder.embed([question], "RETRIEVAL_QUERY", timeout=10)[0]
    ranked = [{**t, "similarity": cosine(query, vectors[knowledge.vector_id(t)])} for t in indexed]
    ranked = [t for t in ranked if t["similarity"] >= knowledge.min_similarity]
    return sorted(ranked, key=lambda t: (-t["similarity"], t["id"]))[:k]


def _hybrid_retrieve(knowledge, principal, question, k=2):
    events = []
    results = knowledge.retrieve(question, principal, k=k,
        emit=lambda stage, **facts: events.append(facts), remaining_seconds=10)
    if not events or events[-1].get("retrieval_mode") != "hybrid":
        raise EmbeddingUnavailable("Hybrid retrieval did not use embeddings.")
    return results


def _case_result(case, results, score_kind, elapsed_ms, cutoffs=(1, 2, 5)):
    returned = [{"id": t["id"], "version": t["version"], "rank": rank,
        "score": t["similarity"] if score_kind == "cosine" else t["score"]}
        for rank, t in enumerate(results, 1)]
    relevant = {(ref["id"], ref["version"]) for ref in case["relevant"]}
    pairs = [(item["id"], item["version"]) for item in returned]
    grades = {(ref["id"], ref["version"]): ref.get("grade", 1) for ref in case["relevant"]}
    at_k = ranking_metrics(pairs, grades, cutoffs)
    return {"id": case["id"], "question": case["question"], "relevant": case["relevant"],
        "language": case.get("language", "other"), "at_k": at_k,
        "positive": bool(relevant), "returned_count": len(returned),
        "returned": returned, "no_result": not returned,
        "recall": at_k["2"]["recall"], "reciprocal_rank": at_k["2"]["rr"],
        "irrelevant_results": sum(pair not in relevant for pair in pairs), "latency_ms": elapsed_ms}


def _average(values):
    return sum(values) / len(values) if values else None


def _metrics(cases, cutoffs=(1, 2, 5)):
    returned = sum(len(case["returned"]) for case in cases)
    irrelevant = sum(case["irrelevant_results"] for case in cases)
    metrics = aggregate_metrics(cases, cutoffs)
    return {**metrics, "recall_at_2": metrics["by_k"]["2"]["recall"],
        "mrr": metrics["by_k"]["2"]["mrr"],
        "irrelevant_example_rate": irrelevant / returned if returned else None}


def _evaluate(name, cases, retrieve, score_kind, cutoffs):
    evaluated = []
    for case in cases:
        started = time.perf_counter()
        results = retrieve(case["question"], max(cutoffs))
        elapsed_ms = (time.perf_counter() - started) * 1000
        evaluated.append(_case_result(case, results, score_kind, elapsed_ms, cutoffs))
    return {"mode": name, "status": "tested", "score_kind": score_kind,
        "metrics": _metrics(evaluated, cutoffs), "cases": evaluated,
        "by_language": {lang: _metrics([c for c in evaluated if c["language"] == lang], cutoffs)
            for lang in sorted({c["language"] for c in evaluated})}}


def _untested(name, score_kind, reason):
    return {"mode": name, "status": "untested", "score_kind": score_kind,
        "reason": reason, "metrics": None, "cases": []}


def run(cases, embedder=None, embedding_source="offline", dataset_version="unversioned", min_similarity=0.65,
        corpus=None, cutoffs=(1, 2, 5), lexical_min_similarity=0.60):
    cutoffs = cutoffs_validated((*cutoffs, 2))
    if embedding_source not in {"offline", "controlled", "live"}:
        raise ValueError("embedding_source must be offline, controlled, or live.")
    if embedder is None and embedding_source != "offline":
        raise ValueError("Controlled/live evaluation requires an embedder.")
    if embedder is not None and embedding_source == "offline":
        raise ValueError("An embedder requires controlled or live provenance.")
    if embedder is not None and not getattr(embedder, "version", None):
        raise ValueError("The embedding provider must expose a model version.")
    cases = _validate_cases(cases)
    evaluation_mode = {"offline": "offline_lexical", "controlled": "offline_controlled_vectors",
        "live": "live_embeddings"}[embedding_source]

    with tempfile.TemporaryDirectory(prefix="retail-retrieval-eval-") as directory:
        store = Store(f"sqlite:///{directory}/state.db")
        try:
            # Establish built-in publications before the non-replacing import.
            lexical = Knowledge(store)
            corpus_info = None
            if corpus is not None:
                from .golden import load_demo_corpus
                corpus_info = load_demo_corpus(store, corpus)
            semantic = Knowledge(store, embedder, min_similarity, lexical_min_similarity) if embedder is not None else None
            principal = principal_for("alice", SimpleNamespace(entitlements_json='{"alice":[1,2]}'))
            eligible_pairs = {(t["id"], t["version"]) for t in _eligible(lexical, principal)}
            label_warnings = [{"case": c["id"], "id": ref["id"], "version": ref["version"],
                "category": "reference_not_in_eligible_corpus"} for c in cases for ref in c["relevant"]
                if (ref["id"], ref["version"]) not in eligible_pairs]
            modes = {"lexical": _evaluate("lexical", cases,
                lambda question, k: lexical.retrieve(question, principal, k=k),
                "reciprocal_rank_fusion", cutoffs)}
            from .knowledge import document
            bm25_trios = {t["id"]: t for t in _eligible(lexical, principal)}
            bm25 = BM25({id: document(t) for id, t in bm25_trios.items()})
            modes["bm25"] = _evaluate("bm25", cases, lambda question, k: [
                {**bm25_trios[r["id"]], "score": r["score"]} for r in bm25.search(question, k)],
                "bm25", cutoffs)
            index_version = None
            unavailable_reason = "No embedding provider configured; vector and hybrid modes were not run."
            if semantic is not None:
                try:
                    semantic.index()
                    index_version = _index_version(store)
                    if index_version is None:
                        raise EmbeddingUnavailable("The embedding index is empty.")
                except EmbeddingUnavailable:
                    unavailable_reason = "Embedding indexing unavailable; vector and hybrid modes were not evaluated."
                else:
                    try:
                        modes["vector"] = _evaluate("vector", cases,
                            lambda question, k: _vector_retrieve(semantic, principal, question, k=k), "cosine", cutoffs)
                    except EmbeddingUnavailable:
                        modes["vector"] = _untested("vector", "cosine",
                            "Embedding provider unavailable; no vector fallback results were scored.")
                    try:
                        modes["hybrid"] = _evaluate("hybrid", cases,
                            lambda question, k: _hybrid_retrieve(semantic, principal, question, k=k),
                            "reciprocal_rank_fusion", cutoffs)
                    except EmbeddingUnavailable:
                        modes["hybrid"] = _untested("hybrid", "reciprocal_rank_fusion",
                            "Embedding provider unavailable or hybrid retrieval fell back; fallback results were not scored.")
            if embedder is None:
                modes["vector"] = _untested("vector", "cosine", unavailable_reason)
                modes["hybrid"] = _untested("hybrid", "reciprocal_rank_fusion", unavailable_reason)
            elif index_version is None:
                modes["vector"] = _untested("vector", "cosine", unavailable_reason)
                modes["hybrid"] = _untested("hybrid", "reciprocal_rank_fusion", unavailable_reason)

            semantic_tested = all(modes[name]["status"] == "tested" for name in ("vector", "hybrid"))
            if embedding_source == "controlled":
                semantic_quality = "not_evaluated_controlled_vectors_only"
            elif embedding_source == "offline":
                semantic_quality = "not_evaluated_no_embedding_provider"
            else:
                semantic_quality = ("measured_against_heldout_labels_not_a_release_pass"
                    if semantic_tested else "untested_provider_unavailable")
            not_evaluated = ["SQL and generated report quality", "live BigQuery", "human analyst review"]
            if embedding_source != "live" or not semantic_tested:
                not_evaluated.append("live embedding relevance")
            return {"report_version": "retrieval-evaluation-v2",
                "generated_at": datetime.now(timezone.utc).isoformat(), "evaluation_mode": evaluation_mode,
                "dataset_version": dataset_version, "relevance_scope": "synthetic_curated_trio_relevance_only",
                "corpus_dataset_version": corpus_info["dataset_version"] if corpus_info else "original-demo-v1",
                "corpus_version": _corpus_version(lexical), "model_version": embedder.version if embedder else None,
                "index_version": index_version, "k": 2, "rank_depth": max(cutoffs),
                "cutoffs": list(cutoffs), "label_warnings": label_warnings,
                "judgment_type": "graded" if any(r["grade"] > 1 for c in cases for r in c["relevant"]) else "binary",
                "min_similarity": min_similarity, "lexical_min_similarity": min(lexical_min_similarity, min_similarity),
                "retrieval_policy": "semantic-lexical-gate-v1",
                "semantic_quality": semantic_quality, "modes": modes, "not_evaluated": not_evaluated}
        finally:
            store.engine.dispose()
