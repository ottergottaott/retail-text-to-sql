"""Explicitly export recorded evaluation scores to local Langfuse, no judge calls."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--dataset", default="retail-faithfulness-historical")
    parser.add_argument("--prompt-version", required=True)
    parser.add_argument("--capture-synthetic", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from dotenv import dotenv_values
    from langfuse import Langfuse
    from retail.experiment_tracking import export_case, digest
    settings = dotenv_values(".local/langfuse/.env")
    client = Langfuse(public_key=settings["LANGFUSE_PUBLIC_KEY"], secret_key=settings["LANGFUSE_SECRET_KEY"],
                      base_url="http://127.0.0.1:3001", timeout=10)
    samples = json.loads(args.samples.read_text())
    report = json.loads(args.results.read_text())
    scores = {c["id"]: c for c in report["cases"]}
    generations = {c["id"]: c for c in report.get("generations", [])}
    records = []
    for sample in samples:
        if sample["id"] not in scores:
            continue
        records.append(export_case(client, args.dataset, args.run, sample, scores[sample["id"]], {
            "serving_prompt": args.prompt_version, "dataset_sha256": report.get("dataset_sha256", digest(samples)),
            "prompt_sha256": report.get("prompt_sha256"), "model": report.get("model"),
            "split": generations.get(sample["id"], {}).get("split"),
            "family": generations.get(sample["id"], {}).get("family"),
            "judge_model": report.get("judge_model"), "evidence_boundary": "Imported recorded scores; no recomputation."},
            capture=args.capture_synthetic))
    client.flush()
    output = {"status": "submitted_not_yet_verified", "run": args.run, "dataset": args.dataset,
              "records": records, "capture": "synthetic" if args.capture_synthetic else "metadata_only"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"submitted": len(records), "capture": output["capture"]}))
    client.shutdown()


if __name__ == "__main__":
    main()
