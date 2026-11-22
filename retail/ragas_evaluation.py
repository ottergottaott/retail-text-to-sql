"""Bounded advisory Ragas evaluation; never part of the serving path."""
import asyncio
import json
import math
import time

from .security import safe_output


class JudgeBudgetExceeded(RuntimeError):
    """The evaluator refused a request because its paid-call budget was spent."""


class InvalidScore(ValueError):
    pass


def error_category(error):
    chain = []
    for _ in range(8):
        if error is None or any(error is item for item in chain):
            break
        chain.append(error)
        error = error.__cause__ or error.__context__
    if any(isinstance(item, JudgeBudgetExceeded) for item in chain):
        return "judge_budget_exhausted"
    if any(isinstance(item, TimeoutError) or type(item).__name__ in {"APITimeoutError", "ReadTimeout", "ConnectTimeout", "WriteTimeout", "PoolTimeout"} for item in chain):
        return "timeout"
    if any(isinstance(item, InvalidScore) for item in chain):
        return "invalid_score"
    return "judge_unavailable_or_invalid"


def summarize(cases, names):
    means, combined, coverage = {}, {}, {}
    for name in names:
        selected = [c["metrics"][name] for c in cases]
        measured = [v for v in selected if v["status"] == "measured"]
        ragas = [v["value"] for v in measured if v.get("source") == "ragas"]
        values = [v["value"] for v in measured]
        means[name] = sum(ragas) / len(ragas) if ragas else None
        combined[name] = sum(values) / len(values) if values else None
        coverage[name] = {"ragas_scored": len(ragas), "rule_scored": len(values) - len(ragas),
                          "applicable": sum(v["status"] != "not_applicable" for v in selected),
                          "total_samples": len(cases)}
    actual = sum(v["ragas_scored"] for v in coverage.values())
    missing = any(v["status"] not in {"measured", "not_applicable"} for c in cases for v in c["metrics"].values())
    # Failed attempted evaluations remain incomplete; undefined-only inputs are untested.
    attempted_failure = any(v["status"] == "untested" for c in cases for v in c["metrics"].values())
    status = "incomplete" if missing and (actual or attempted_failure) else "tested" if actual else "untested"
    return {"status": status, "aggregation_version": "v2", "means": means,
            "combined_means": combined, "coverage": coverage}


def validate_samples(samples):
    if not isinstance(samples, list) or not 1 <= len(samples) <= 32:
        raise ValueError("Provide 1–32 evaluation samples.")
    seen = set()
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("Samples must be objects.")
        for name in ("id", "question"):
            if not isinstance(sample.get(name), str) or not sample[name].strip():
                raise ValueError("Each sample needs an id and question.")
        if sample["id"] in seen:
            raise ValueError("Duplicate sample id.")
        seen.add(sample["id"])
        for name in ("sql_contexts", "retrieved_contexts"):
            contexts = sample.get(name, [])
            if not isinstance(contexts, list) or len(contexts) > 5 or any(not isinstance(c, str) or not c.strip() for c in contexts):
                raise ValueError("Each context field must contain at most five nonempty strings.")
        for name in ("response", "reference_logic"):
            if not isinstance(sample.get(name, ""), str):
                raise ValueError("Responses and reference logic must be strings.")
        serialized = json.dumps(sample, ensure_ascii=False)
        if len(serialized) > 64000 or len(sample["question"]) > 8000 or len(sample["id"]) > 100:
            raise ValueError("Evaluation sample exceeds the size budget.")
        safe_output(serialized)
    return samples


async def evaluate_samples(samples, metrics, timeout=60):
    validate_samples(samples)
    if not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise ValueError("Metric timeout must be in (0,120].")
    allowed = {"faithfulness", "factual_faithfulness", "sql_factual_faithfulness", "context_precision", "context_recall"}
    if not metrics or not set(metrics) <= allowed:
        raise ValueError("Unsupported or empty metric selection.")
    cases = []
    for sample in samples:
        scored = {}
        for name, metric in metrics.items():
            factual = name in {"faithfulness", "factual_faithfulness", "sql_factual_faithfulness"}
            contexts = sample.get("sql_contexts" if factual else "retrieved_contexts", [])
            reference = sample.get("reference_logic", "")
            applicable = bool(contexts or (sample.get("response") if factual else reference))
            if not applicable:
                scored[name] = {"status": "not_applicable", "value": None}
                continue
            if not contexts:
                scored[name] = {"status": "undefined", "value": None, "reason": "empty_context"}
                if name == "context_recall" and reference:
                    scored[name] = {"status": "measured", "value": 0.0, "source": "empty_context_rule"}
                continue
            if (factual and not sample.get("response")) or (not factual and not reference):
                scored[name] = {"status": "untested", "value": None, "reason": "missing_reference_or_response"}
                continue
            arguments = {"user_input": sample["question"], "retrieved_contexts": contexts}
            arguments["response" if factual else "reference"] = sample["response"] if factual else reference
            start = time.monotonic()
            try:
                result = await asyncio.wait_for(metric.ascore(**arguments), timeout=timeout)
                try:
                    value = float(result.value)
                except (TypeError, ValueError, AttributeError) as error:
                    raise InvalidScore() from error
                if not math.isfinite(value) or not 0 <= value <= 1:
                    raise InvalidScore()
                scored[name] = {"status": "measured", "value": value, "source": "ragas"}
                if getattr(metric, "diagnostics", None) is not None:
                    safe_output(json.dumps(metric.diagnostics))
                    scored[name]["statement_diagnostics"] = metric.diagnostics
            except Exception as error:
                # Provider/instructor diagnostics may contain full prompts or secrets.
                scored[name] = {"status": "untested", "value": None,
                                "error_category": error_category(error)}
            scored[name]["seconds"] = time.monotonic() - start
        cases.append({"id": sample["id"], "metrics": scored})
    return {**summarize(cases, metrics), "evaluation": "ragas_advisory", "cases": cases,
            "limitations": ["LLM judge scores are not independent SQL correctness or human acceptance.",
                            "Golden context precision/recall measures reference logic coverage, not live numerical facts.",
                            "Faithfulness can penalize recommendations not entailed by SQL facts; inspect low scores."]}
