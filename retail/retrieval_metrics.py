"""Shared ranking metrics; no model, storage, network or credential dependency."""
import math


def cutoffs_validated(cutoffs):
    values = tuple(cutoffs)
    if not values or any(type(k) is not int or not 1 <= k <= 100 for k in values):
        raise ValueError("Retrieval cutoffs must be integers from 1 to 100.")
    return tuple(sorted(set(values)))


def ranking_metrics(ranked, grades, cutoffs=(1, 2, 5)):
    cutoffs = cutoffs_validated(cutoffs)
    if any(type(g) is not int or g not in (0, 1, 2) for g in grades.values()):
        raise ValueError("Relevance grades must be integers 0, 1 or 2.")
    relevant = {key: grade for key, grade in grades.items() if grade > 0}
    ideal = sorted(relevant.values(), reverse=True)
    result = {}
    for k in cutoffs:
        if not relevant:
            result[str(k)] = dict.fromkeys(("recall", "precision", "rr", "ndcg"))
            continue
        seen, hits, dcg, rr = set(), 0, 0.0, 0.0
        for rank, key in enumerate(ranked[:k], 1):
            grade = relevant.get(key, 0) if key not in seen else 0
            seen.add(key)
            if grade:
                hits += 1
                rr = rr or 1 / rank
                dcg += (2 ** grade - 1) / math.log2(rank + 1)
        idcg = sum((2 ** grade - 1) / math.log2(rank + 1)
            for rank, grade in enumerate(ideal[:k], 1))
        result[str(k)] = {"recall": hits / len(relevant), "precision": hits / k,
            "rr": rr, "ndcg": dcg / idcg}
    return result


def aggregate_metrics(cases, cutoffs=(1, 2, 5)):
    cutoffs = cutoffs_validated(cutoffs)
    positives = [c for c in cases if c["positive"]]
    negatives = [c for c in cases if not c["positive"]]
    def avg(values):
        return sum(values) / len(values) if values else None
    latency = sorted(c["latency_ms"] for c in cases)
    def percentile(fraction):
        return latency[math.ceil(fraction * len(latency)) - 1] if latency else None
    return {"positive_cases": len(positives), "negative_cases": len(negatives),
        "by_k": {str(k): {name: avg([c["at_k"][str(k)][field] for c in positives])
            for name, field in [("recall", "recall"), ("precision", "precision"), ("mrr", "rr"), ("ndcg", "ndcg")]}
            for k in cutoffs},
        "negative_false_match_rate": avg([float(c["returned_count"] > 0) for c in negatives]),
        "negative_no_result_rate": avg([float(c["returned_count"] == 0) for c in negatives]),
        "mean_latency_ms": avg(latency), "p50_latency_ms": percentile(0.5),
        "p95_latency_ms": percentile(0.95)}
