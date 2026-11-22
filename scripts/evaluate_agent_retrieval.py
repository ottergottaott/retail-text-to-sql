"""Opt-in live model retrieval ablation against isolated fixture SQL, never BigQuery."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from retail.config import Settings
from retail.providers import model_for, embeddings_for
from retail.agent_retrieval_evaluation import run_ablation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Billed model/embedding calls; SQL remains fixture-only.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        report = {"status": "untested", "reason": "Live model not requested; no settings or providers loaded."}
    else:
        config = Settings(retail_mode="live")
        try:
            config.validate_embeddings()
            if config.llm_provider == "deepinfra" and not config.deepinfra_api_key:
                raise ValueError("DeepInfra model key required.")
            if config.llm_provider == "gemini" and not all([config.gemini_api_key, config.gemini_model]):
                raise ValueError("Google model key and model name required.")
        except ValueError as error:
            parser.error(str(error))
        report = run_ablation(config, model_for(config), embeddings_for(config), model_source="live")
        report["model"] = config.deepinfra_model if config.llm_provider == "deepinfra" else config.gemini_model
        report["embedding_model"] = config.deepinfra_embedding_model if config.embedding_provider == "deepinfra" else config.embedding_model
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "modes": {n: {"status": m["status"],
        "query_oracles_passed": m.get("query_oracles_passed")} for n, m in report.get("modes", {}).items()}}))


if __name__ == "__main__":
    main()
