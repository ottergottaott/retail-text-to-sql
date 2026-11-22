"""Synthetic corpus import is explicit, validated and cannot replace published versions."""
import json
import pytest

from retail.knowledge import Knowledge
from retail.store import Store


def trio(id="demo-extra", **changes):
    return {"id": id, "version": 1, "question": "How many products?",
        "sql": "SELECT COUNT(*) AS products FROM products",
        "report": "Count authorized catalog products; this is not a sales count.",
        "tags": ["catalog"], "scope": "shared", "schema_version": "safe-v1",
        "origin": "synthetic demonstration; not historical analyst work", **changes}


def write_corpus(tmp_path, records):
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps({"dataset_version": "unit-v1", "trios": records}))
    return path


def test_demo_import_is_idempotent_and_preserves_newer_publication(tmp_path):
    from retail.golden import load_demo_corpus
    store = Store(f"sqlite:///{tmp_path}/state.db")
    try:
        knowledge = Knowledge(store)
        path = write_corpus(tmp_path, [trio()])
        assert load_demo_corpus(store, path)["imported"] == 1
        assert load_demo_corpus(store, path)["imported"] == 0
        store.put("trio", "system", {**trio(), "version": 2, "status": "published",
            "scope": "products", "products": [3]})
        assert load_demo_corpus(store, path)["imported"] == 0
        record = next(t for t in knowledge.published() if t["id"] == "demo-extra")
        assert record["version"] == 2 and record["scope"] == "products"
    finally:
        store.engine.dispose()


@pytest.mark.parametrize("bad", [
    trio(sql="SELECT email FROM users"),
    trio(origin="historical human analyst"),
    trio(scope="products", products=[3]),
    trio(version=2),
])
def test_demo_import_validates_entire_file_before_writing(tmp_path, bad):
    from retail.golden import load_demo_corpus
    store = Store(f"sqlite:///{tmp_path}/state.db")
    try:
        path = write_corpus(tmp_path, [trio(id="good"), bad])
        with pytest.raises(ValueError):
            load_demo_corpus(store, path)
        assert store.list("trio", "system") == []
    finally:
        store.engine.dispose()


def test_expanded_evaluation_uses_explicit_corpus(tmp_path):
    from retail.retrieval_evaluation import run
    path = write_corpus(tmp_path, [trio()])
    report = run([{"id": "catalog", "question": "catalog products count", "relevant": [
        {"id": "demo-extra", "version": 1}]}], corpus=path)
    assert report["corpus_dataset_version"] == "unit-v1"
    assert any(t["id"] == "demo-extra" for t in report["modes"]["lexical"]["cases"][0]["returned"])


def test_evaluation_preserves_builtin_seed_when_extra_corpus_collides(tmp_path):
    from retail.retrieval_evaluation import run
    cases = [{"id": "monthly", "question": "monthly revenue", "relevant": [
        {"id": "monthly-revenue", "version": 1}]}]
    baseline = run(cases)
    collision = write_corpus(tmp_path, [trio(id="monthly-revenue")])
    expanded = run(cases, corpus=collision)
    assert expanded["corpus_version"] == baseline["corpus_version"]
    assert expanded["modes"]["lexical"]["metrics"]["recall_at_2"] == 1
