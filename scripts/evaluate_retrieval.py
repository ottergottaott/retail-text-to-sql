"""Run isolated held-out retrieval evaluation; live embeddings require --live."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from retail.config import Settings
from retail.providers import embeddings_for
from retail.retrieval_evaluation import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "evaluation" / "heldout-retrieval-cases.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, help="Additional versioned synthetic demo trios; isolated store only.")
    parser.add_argument("--k", type=int, nargs="+", default=[1, 2, 5], help="Ranking cutoffs; @2 is always retained.")
    parser.add_argument("--live", action="store_true",
        help="Use the configured embedding provider; may make billed provider calls.")
    args = parser.parse_args()

    try:
        payload = json.loads(args.cases.read_text())
    except (OSError, ValueError):
        parser.error("Case file could not be read as JSON.")
    if (not isinstance(payload, dict) or not isinstance(payload.get("cases"), list)
            or not isinstance(payload.get("dataset_version"), str) or not payload["dataset_version"]):
        parser.error("Case file must contain dataset_version and a cases list.")

    if args.live:
        config = Settings()
        try:
            config.validate_embeddings()
        except ValueError as error:
            parser.error(str(error))
        embedder = embeddings_for(config)
        if embedder is None:
            parser.error("--live requires an enabled embedding provider.")
        source = "live"
        min_similarity = config.retrieval_min_similarity
        lexical_min_similarity = config.retrieval_lexical_min_similarity
    else:
        embedder = None
        source = "offline"
        min_similarity = 0.65
        lexical_min_similarity = 0.60

    try:
        report = run(payload["cases"], embedder=embedder, embedding_source=source,
            dataset_version=payload["dataset_version"], min_similarity=min_similarity, corpus=args.corpus, cutoffs=args.k,
            lexical_min_similarity=lexical_min_similarity)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "evaluation_mode": report["evaluation_mode"],
        "modes": {name: result["status"] for name, result in report["modes"].items()}}))
    if args.live and any(report["modes"][name]["status"] != "tested" for name in ("vector", "hybrid")):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
