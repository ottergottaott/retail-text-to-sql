import asyncio
import pytest
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from retail.ragas_evaluation import evaluate_samples, validate_samples
from retail.security import PolicyError


def sample(**changes):
    return {"id": "revenue", "question": "Completed revenue?", "response": "Revenue is 98.",
            "sql_contexts": ['Complete items: [{"revenue":98}]'],
            "retrieved_contexts": ["Sum sale price for Complete items."],
            "reference_logic": "Revenue is sum of sale_price for Complete items.", **changes}


def test_rejects_pii_and_excessive_paid_work_before_scoring():
    with pytest.raises(PolicyError):
        validate_samples([sample(response="Contact a@example.com")])
    with pytest.raises(ValueError):
        validate_samples([sample(id=str(i)) for i in range(33)])
    with pytest.raises(ValueError):
        validate_samples([sample(), sample()])


def test_sql_facts_and_golden_contexts_are_not_mixed():
    seen = {}
    class Metric:
        def __init__(self, name): self.name = name
        async def ascore(self, **kwargs):
            seen[self.name] = kwargs
            return SimpleNamespace(value=0.75)
    metrics = {n: Metric(n) for n in ["faithfulness", "context_precision", "context_recall"]}
    result = asyncio.run(evaluate_samples([sample()], metrics, timeout=1))
    assert seen["faithfulness"]["retrieved_contexts"] == sample()["sql_contexts"]
    assert seen["context_precision"]["retrieved_contexts"] == sample()["retrieved_contexts"]
    assert seen["context_recall"]["reference"] == sample()["reference_logic"]
    assert result["status"] == "tested"
    assert result["means"]["faithfulness"] == .75
    assert "Revenue is 98" not in json.dumps(result)


def test_timeout_and_nan_are_untested_not_zero_or_success():
    class Slow:
        async def ascore(self, **kwargs):
            await asyncio.sleep(1)
    class NaN:
        async def ascore(self, **kwargs): return SimpleNamespace(value=float("nan"))
    result = asyncio.run(evaluate_samples([sample()], {"faithfulness": Slow(), "context_precision": NaN()}, timeout=.01))
    assert result["status"] == "incomplete"
    assert all(v is None for v in result["means"].values())
    assert result["cases"][0]["metrics"]["faithfulness"]["error_category"] == "timeout"


def test_empty_retrieval_is_explicit_and_does_not_call_judge():
    class Forbidden:
        async def ascore(self, **kwargs): raise AssertionError("must not call")
    result = asyncio.run(evaluate_samples([sample(retrieved_contexts=[])], {"context_precision": Forbidden(), "context_recall": Forbidden()}))
    metrics = result["cases"][0]["metrics"]
    assert metrics["context_precision"]["value"] is None
    assert metrics["context_recall"]["value"] == 0
    assert metrics["context_recall"]["source"] == "empty_context_rule"
    assert result["means"]["context_recall"] is None
    assert result["combined_means"]["context_recall"] == 0
    assert result["status"] == "untested"


def test_missing_faithfulness_context_is_not_a_success():
    class Metric:
        async def ascore(self, **kwargs): return SimpleNamespace(value=1)
    result = asyncio.run(evaluate_samples([sample(sql_contexts=[])], {"faithfulness": Metric()}))
    assert result["status"] == "untested"


def test_invalid_score_and_budget_exhaustion_have_distinct_categories():
    from retail.ragas_evaluation import JudgeBudgetExceeded
    class Budget:
        async def ascore(self, **kwargs): raise JudgeBudgetExceeded()
    class Invalid:
        async def ascore(self, **kwargs): return SimpleNamespace(value=2)
    result = asyncio.run(evaluate_samples([sample()], {"faithfulness": Budget(), "context_recall": Invalid()}))
    m = result["cases"][0]["metrics"]
    assert m["faithfulness"]["error_category"] == "judge_budget_exhausted"
    assert m["context_recall"]["error_category"] == "invalid_score"


def test_offline_cli_does_not_read_missing_inputs_or_settings(tmp_path):
    output = tmp_path / "result.json"
    run = subprocess.run([sys.executable, "scripts/evaluate_ragas.py", "--samples", str(tmp_path / "missing.json"), "--output", str(output)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert json.loads(output.read_text())["status"] == "untested"


def test_live_cli_without_measured_metrics_exits_nonzero(tmp_path, monkeypatch):
    from scripts import evaluate_ragas as cli
    from retail import config
    samples = tmp_path / "samples.json"
    samples.write_text(json.dumps([sample()]))
    monkeypatch.setattr(config, "Settings", lambda **kwargs: SimpleNamespace(deepinfra_api_key="controlled-key"))
    async def unscored(*args):
        return {"status": "untested"}
    monkeypatch.setattr(cli, "live", unscored)
    monkeypatch.setattr(sys, "argv", ["evaluate_ragas", "--live", "--samples", str(samples), "--output", str(tmp_path / "out.json")])
    assert cli.main() == 3


def test_live_judge_uses_configured_gateway_base_url():
    from scripts.evaluate_ragas import judge_base_url, judge_http_timeout, judge_api_key, judge_provider, judge_retry_count, judge_instructor_mode
    from instructor import Mode
    assert judge_base_url(SimpleNamespace(deepinfra_base_url="https://gateway.example/v1")) == "https://gateway.example/v1/"
    assert judge_http_timeout(SimpleNamespace(deepinfra_base_url="https://gateway.example/v1")) == 60
    assert judge_http_timeout(SimpleNamespace(deepinfra_base_url="https://gateway.example/v1", ragas_judge_timeout=120)) == 120
    assert judge_retry_count() == 0
    assert judge_instructor_mode(SimpleNamespace(llm_provider='openai_compatible')) == Mode.MD_JSON
    assert judge_instructor_mode(SimpleNamespace(llm_provider='deepinfra')) == Mode.JSON


def test_live_judge_labels_custom_gateway_without_calling_it_deepinfra():
    from scripts.evaluate_ragas import judge_base_url, judge_api_key, judge_provider
    config = SimpleNamespace(
        llm_provider="openai_compatible",
        openai_compatible_api_key="gateway-key",
        openai_compatible_base_url="https://gateway.example/v1",
        deepinfra_api_key="",
        deepinfra_base_url="https://api.deepinfra.com/v1/openai",
    )
    assert judge_base_url(config) == "https://gateway.example/v1/"
    assert judge_api_key(config) == "gateway-key"
    assert judge_provider(config) == "openai_compatible"


@pytest.mark.parametrize("name", ["factual_faithfulness", "sql_factual_faithfulness"])
def test_factual_metric_keeps_assertions_inside_actions_and_uses_sql_context(name):
    response='Revenue is 98. Proposed: fix stock because demand doubled.'
    class FactualMetric:
        async def ascore(self, **kwargs):
            assert kwargs['response']==response
            assert kwargs['retrieved_contexts']==sample()['sql_contexts']
            return SimpleNamespace(value=0.5)
    result=asyncio.run(evaluate_samples([sample(response=response)], {name:FactualMetric()}))
    assert result['means'][name]==0.5
