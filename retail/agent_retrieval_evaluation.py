"""Small retrieval ablation: real agent, isolated fixture SQL, explicit model source."""
import math
import tempfile
import time
from pathlib import Path

from .agent import Agent
from .analytics import Analytics
from .embeddings import EmbeddingUnavailable
from .golden import load_demo_corpus
from .knowledge import Knowledge
from .security import Principal
from .store import Store

CASES = [
    {"id": "monthly", "question": "Compare completed-item revenue for January and February 2026, using only authorized products. Return one row per month with columns month (start-of-month UTC date) and revenue, then explain limitations and action items.",
     "expected_rows": [{"month": "2026-01-01 00:00:00", "revenue": 100.0}, {"month": "2026-02-01 00:00:00", "revenue": 110.0}]},
    {"id": "returns", "question": "For each authorized product, calculate returned items / (Complete + Returned items) across all available history. Return columns product_id, finalized_items, returned_items, return_rate. Explain why this is not a refund rate and suggest follow-up actions.",
     "expected_rows": [{"product_id": 1, "finalized_items": 8, "returned_items": 1, "return_rate": 0.125}, {"product_id": 2, "finalized_items": 8, "returned_items": 1, "return_rate": 0.125}]},
    {"id": "margin", "question": "Across all authorized Complete items and all available history, calculate total sale price minus product cost, excluding other expenses. Return one row with columns completed_revenue, product_cost_proxy, margin_proxy. Explain limitations and suggest actions; do not call this net profit.",
     "expected_rows": [{"completed_revenue": 210.0, "product_cost_proxy": 490.0, "margin_proxy": -280.0}]},
]


def matches(actual, expected):
    if len(actual) != len(expected):
        return False
    unmatched = list(actual)
    for want in expected:
        found = None
        for i, got in enumerate(unmatched):
            def equal(key, value):
                other = got.get(key)
                if isinstance(value, (float, int)) and not isinstance(value, bool):
                    return isinstance(other, (int, float)) and not isinstance(other, bool) and math.isclose(other, value, rel_tol=1e-6, abs_tol=1e-6)
                return other == value
            if all(key in got and equal(key, value) for key, value in want.items()):
                found = i
                break
        if found is None:
            return False
        unmatched.pop(found)
    return True


class NoRetrieval:
    def retrieve(self, question, principal, emit=None, **kwargs):
        if emit:
            emit("retrieval", retrieval_mode="disabled", returned=0)
        return []


def run_ablation(config, model, embedder, model_source, cases=CASES):
    if model_source not in {"live", "controlled"}:
        raise ValueError("Ablation model source must be live or controlled.")
    results = {}
    with tempfile.TemporaryDirectory(prefix="retail-agent-ablation-") as directory:
        # The model may be live; Analytics is explicitly injected with fixture
        # config. No BigQuery client is constructed by this evaluation.
        agent_config = config.model_copy(update={"log_path": str(Path(directory) / "events.jsonl"),
            "langfuse_public_key": "", "langfuse_secret_key": "", "embedding_provider": "none"})
        fixture_config = agent_config.model_copy(update={"retail_mode": "fixture"})
        store = Store(f"sqlite:///{directory}/state.db")
        try:
            lexical = Knowledge(store)
            load_demo_corpus(store)
            hybrid = Knowledge(store, embedder, config.retrieval_min_similarity,
                config.retrieval_lexical_min_similarity) if embedder else None
            if hybrid:
                try:
                    hybrid.index()
                except EmbeddingUnavailable:
                    hybrid = None
            for mode, knowledge in [("none", NoRetrieval()), ("lexical", lexical), ("hybrid", hybrid)]:
                if knowledge is None:
                    results[mode] = {"status": "untested", "cases": []}
                    continue
                evaluated = []
                agent = Agent(agent_config, store, model=model, analytics=Analytics(fixture_config))
                agent.knowledge = knowledge
                for case in cases:
                    events = []
                    start = time.perf_counter()
                    answer = agent.chat(Principal("alice", (1, 2)), case["question"], sink=events.append)
                    evidence = answer["evidence"]
                    used_hybrid = any(e.get("retrieval_mode") == "hybrid" for e in events)
                    oracle = any(not e["truncated"] and e["mode"] == "fixture" and
                        matches(e["rows"], case["expected_rows"]) for e in evidence)
                    evaluated.append({"id": case["id"], "outcome": answer["outcome"],
                        "query_oracle_passed": oracle and answer["outcome"] == "succeeded",
                        "retrieval_verified": mode != "hybrid" or used_hybrid,
                        "seconds": time.perf_counter() - start, "trace_id": answer["trace_id"],
                        "answer": answer["answer"], "evidence": evidence,
                        "trios": next((e["trios"] for e in events if e["stage"] == "context_versions"), []),
                        "model_usage": [e for e in events if e["stage"] == "model_usage"]})
                results[mode] = {"status": "tested" if all(c["retrieval_verified"] for c in evaluated) else "incomplete",
                    "query_oracles_passed": sum(c["query_oracle_passed"] for c in evaluated), "cases": evaluated}
        finally:
            store.engine.dispose()
    return {"evaluation_mode": "agent_retrieval_ablation", "data_mode": "fixture", "model_source": model_source,
        "live_bigquery_verified": False, "report_faithfulness": "pending_human_review",
        "oracle_scope": "three synthetic fixture queries with requested output aliases; not broad intent accuracy",
        "repetitions": 1, "cost": None, "modes": results}
