"""Pinned external WikiSQL retrieval diagnostic. Offline BM25 unless --live."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb
import httpx
from retail.config import Settings
from retail.providers import embeddings_for
from retail.external_retrieval import evaluate_external

REVISION = "add6c3faf0d972ebb139b30fa6c4f955d99635c5"
CHECKSUMS = {
    "corpus": "4bb57ef0d11d8bc2dc8d0244a23bb8e16ac0429b53c841b4876c695de8cf0f4b",
    "queries": "432c25a8f22eec9bff74ceeb5b577b51c4c558de57fd4f86139fa1712cf4ee46",
    "qrels": "f04d2f2dcd7ae1f2fbe506353ab51878283779bf621553d524fc20b9edba11c5",
}


def load_data(directory, download=False):
    records = {}
    for kind, expected in CHECKSUMS.items():
        path = directory / f"{kind}.parquet"
        if not path.exists():
            if not download:
                raise ValueError("Pinned dataset files missing; use --download to fetch public WikiSQL data.")
            url = f"https://huggingface.co/datasets/mteb/WikiSQLRetrieval/resolve/{REVISION}/{kind}/test-00000-of-00001.parquet"
            response = httpx.get(url, timeout=30, follow_redirects=True)
            response.raise_for_status()
            directory.mkdir(parents=True, exist_ok=True)
            content = response.content
            if hashlib.sha256(content).hexdigest() != expected:
                raise ValueError("Downloaded WikiSQL checksum mismatch.")
            path.write_bytes(content)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Pinned WikiSQL file checksum mismatch.")
        with duckdb.connect() as connection:
            cursor = connection.execute("SELECT * FROM read_parquet(?)", [str(path)])
            names = [c[0] for c in cursor.description]
            records[kind] = [dict(zip(names, row)) for row in cursor.fetchall()]
    corpus = {r["id"]: r["text"] for r in records["corpus"]}
    queries = {r["id"]: r["text"] for r in records["queries"]}
    qrels = {}
    for row in records["qrels"]:
        qrels.setdefault(row["query-id"], {})[row["corpus-id"]] = row["score"]
    return corpus, queries, qrels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--download", action="store_true", help="Fetch three checksum-pinned public parquet files.")
    parser.add_argument("--live", action="store_true", help="Use selected embedding provider; incurs billed calls.")
    parser.add_argument("--limit", type=int, default=100, help="Deterministic query sample, 1..2048; corpus stays complete.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        if not 1 <= args.limit <= 2048:
            raise ValueError("--limit must be from 1 to 2048.")
        corpus, queries, qrels = load_data(args.data_dir, args.download)
        embedder = None
        if args.live:
            config = Settings()
            config.validate_embeddings()
            embedder = embeddings_for(config)
            if embedder is None:
                raise ValueError("--live requires an enabled embedding provider.")
            planned_calls = (len(corpus) + 31) // 32 + min(args.limit, len(qrels))
            print(f"Planned: {planned_calls} embedding calls (full corpus indexing plus sampled queries); "
                "billed usage, no automatic retries. --limit caps queries only.", file=sys.stderr)
        report = evaluate_external(corpus, queries, qrels, embedder,
            "live" if args.live else "offline", limit=args.limit, seed=args.seed)
    except ValueError as error:
        parser.error(str(error))
    except (httpx.HTTPError, OSError, duckdb.Error):
        parser.error("WikiSQL files could not be downloaded or read; no provider results inferred.")
    report["dataset"] = {"name": "mteb/WikiSQLRetrieval", "revision": REVISION,
        "file_sha256": CHECKSUMS, "query_representation": "unmodified upstream question plus table context",
        "corpus_representation": "unmodified upstream SQL text"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "queries": report["evaluated_queries"],
        "subset": report["subset"], "modes": {n: m["status"] for n, m in report["modes"].items()}}))
    if args.live and report["modes"]["vector"]["status"] != "tested":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
