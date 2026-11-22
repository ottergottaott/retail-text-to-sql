"""Opt-in, bounded Ragas judge calls through DeepInfra. Default does no work."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from retail.ragas_evaluation import evaluate_samples, validate_samples, JudgeBudgetExceeded
from retail.security import PolicyError


async def live(samples, config, model, max_calls, metric_names=None, diagnostics=False):
    os.environ["RAGAS_DO_NOT_TRACK"] = "true"
    from openai import AsyncOpenAI
    import httpx
    from instructor import Mode
    from ragas.llms import llm_factory
    from ragas.metrics.collections import Faithfulness, ContextPrecision, ContextRecall
    from retail.ragas_metrics import factual_faithfulness, sql_factual_faithfulness

    class BoundedTransport(httpx.AsyncBaseTransport):
        def __init__(self):
            self.inner = httpx.AsyncHTTPTransport(retries=0)
            self.attempts = self.tokens = self.usage_responses = 0
        async def handle_async_request(self, request):
            if self.attempts >= max_calls:
                raise JudgeBudgetExceeded("Judge call budget exhausted")
            self.attempts += 1
            response = await self.inner.handle_async_request(request)
            await response.aread()
            try:
                usage = response.json().get("usage", {})
                if isinstance(usage.get("total_tokens"), int):
                    self.tokens += usage["total_tokens"]
                    self.usage_responses += 1
            except Exception:
                pass
            return response
        async def aclose(self): await self.inner.aclose()

    transport = BoundedTransport()
    async with httpx.AsyncClient(transport=transport, timeout=30) as http:
        async with AsyncOpenAI(api_key=config.deepinfra_api_key, base_url="https://api.deepinfra.com/v1/openai", max_retries=0, http_client=http) as client:
            judge = llm_factory(model, client=client, mode=Mode.JSON, temperature=0, max_tokens=6000, max_retries=1)
            metrics = {"faithfulness": Faithfulness(judge), "context_precision": ContextPrecision(judge), "context_recall": ContextRecall(judge)}
            if metric_names:
                if "factual_faithfulness" in metric_names:
                    metrics["factual_faithfulness"] = factual_faithfulness(judge)
                if "sql_factual_faithfulness" in metric_names:
                    metrics["sql_factual_faithfulness"] = sql_factual_faithfulness(judge)
                metrics = {name: metrics[name] for name in metric_names}
            if diagnostics:
                from retail.faithfulness_experiments import record_diagnostics
                metrics = {name: record_diagnostics(metric) if "faithfulness" in name else metric
                           for name, metric in metrics.items()}
            report = await evaluate_samples(samples, metrics)
    report.update(judge_provider="deepinfra", judge_model=model, ragas_version="0.4.4",
                  attempted_provider_calls=transport.attempts, max_provider_calls=max_calls,
                  measured_total_tokens=transport.tokens if transport.usage_responses else None,
                  usage_responses=transport.usage_responses, cost=None, human_review="pending")
    report["metric_definitions"] = {
        "faithfulness": "Unmodified Ragas whole-response statement entailment against original SQL contexts.",
        "factual_faithfulness": "Scoped Ragas metric with factual statement extraction v1; keeps every empirical assertion including premises inside proposals. Excludes only pure suggestions without factual premises. Not directly comparable to whole-response faithfulness.",
        "sql_factual_faithfulness": "Factual extraction plus SQL/provenance entailment instruction v1. Accounts for trusted scope, untruncated groups and measurement boundaries; not standard Ragas or comparable with v1 factual scores."}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=Path(".env.live"))
    parser.add_argument("--judge-model", default="google/gemini-3.5-flash")
    parser.add_argument("--max-calls", type=int, default=96)
    parser.add_argument("--metrics", nargs="+", choices=["faithfulness", "factual_faithfulness", "sql_factual_faithfulness", "context_precision", "context_recall"])
    args = parser.parse_args()
    if not args.live:
        report = {"status": "untested", "reason": "Live judge not requested; no inputs or settings read."}
    else:
        try:
            if not 1 <= args.max_calls <= 256:
                raise ValueError("max-calls must be in [1,256].")
            samples = validate_samples(json.loads(args.samples.read_text()))
            from retail.config import Settings
            config = Settings(_env_file=args.env_file)
            if not config.deepinfra_api_key:
                raise ValueError("DeepInfra key required.")
            print(json.dumps({"planned_samples": len(samples), "maximum_provider_calls": args.max_calls, "billed_calls": True}), file=sys.stderr)
            report = asyncio.run(live(samples, config, args.judge_model, args.max_calls, args.metrics))
        except (OSError, ValueError, PolicyError):
            parser.error("Invalid evaluation configuration or sample input; check schema, bounds and privacy.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"output": str(args.output), "status": report["status"]}))
    return 0 if report["status"] == "tested" or not args.live else 3


if __name__ == "__main__":
    raise SystemExit(main())
