"""Explicit synthetic demo import; real analyst publication uses Governance."""
import json
from pathlib import Path

from .analytics import validate, QueryError
from .security import safe_output, PolicyError

DEFAULT_CORPUS = Path(__file__).parent / "data" / "golden-trios.json"
ORIGIN = "synthetic demonstration; not historical analyst work"


def load_demo_corpus(store, path=DEFAULT_CORPUS):
    payload = json.loads(Path(path).read_text())
    if (not isinstance(payload, dict) or not isinstance(payload.get("dataset_version"), str)
            or not payload["dataset_version"].strip() or not isinstance(payload.get("trios"), list)
            or not payload["trios"]):
        raise ValueError("A versioned nonempty synthetic corpus is required.")
    ids = set()
    allowed = {"id", "version", "question", "sql", "report", "tags", "scope", "schema_version", "origin"}
    for trio in payload["trios"]:
        if not isinstance(trio, dict) or set(trio) != allowed:
            raise ValueError("Unsupported synthetic trio fields.")
        if any(not isinstance(trio[field], str) or not trio[field].strip()
                for field in ("id", "question", "sql", "report")):
            raise ValueError("A synthetic trio needs nonempty text fields.")
        if (trio["id"] in ids or type(trio["version"]) is not int or trio["version"] != 1
                or trio["origin"] != ORIGIN or trio["scope"] != "shared"
                or trio["schema_version"] != "safe-v1"
                or not isinstance(trio["tags"], list) or not trio["tags"]
                or any(not isinstance(tag, str) or not tag.strip() for tag in trio["tags"])):
            raise ValueError("Invalid synthetic trio provenance, scope, version or tags.")
        try:
            safe_output(json.dumps(trio))
            validate(trio["sql"])
        except (PolicyError, QueryError):
            raise ValueError("Synthetic trio failed privacy or SQL validation.") from None
        ids.add(trio["id"])
    # Validate every record before the first write; never downgrade or broaden
    # an existing publication, even if its version is absent from this corpus.
    existing = {row["body"]["id"] for row in store.list("trio", "system")}
    pending = [trio for trio in payload["trios"] if trio["id"] not in existing]
    with store.engine.begin() as connection:
        for trio in pending:
            store.put("trio", "system", {**trio, "status": "published",
                "corpus_dataset_version": payload["dataset_version"]}, conn=connection)
    return {"dataset_version": payload["dataset_version"], "imported": len(pending),
        "skipped_existing": len(payload["trios"]) - len(pending), "origin": ORIGIN}
