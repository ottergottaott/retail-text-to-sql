import json
from pathlib import Path

import pytest

from retail.embeddings import EmbeddingUnavailable
from retail.retrieval_evaluation import run


class ControlledEmbeddings:
    """Deterministic vectors for mechanics tests, never semantic quality evidence."""
    version = "controlled-test-v1"

    def embed(self, texts, task, timeout=10):
        return [self._vector(text) for text in texts]

    @staticmethod
    def _vector(text):
        text = text.lower()
        if any(term in text for term in ("month", "takings")):
            return [1.0, 0.0, 0.0]
        if any(term in text for term in ("customer", "shopper", "buyer", "spender", "pseudonymous")):
            return [0.0, 0.0, 1.0]
        if any(term in text for term in ("product", "units sold", "item performance", "sent-back")):
            return [0.0, 1.0, 0.0]
        if any(term in text for term in ("revenue", "income", "sales")):
            return [1.0, 0.0, 0.0]
        return [0.0, 0.0, 0.0]


CASES = [
    {
        "id": "monthly-paraphrase",
        "question": "Track monthly income trajectory",
        "relevant": [{"id": "monthly-revenue", "version": 1}],
    },
    {"id": "unrelated-negative", "question": "Weather forecast", "relevant": []},
]


class QueryFailureEmbeddings(ControlledEmbeddings):
    def embed(self, texts, task, timeout=10):
        if task == "RETRIEVAL_QUERY":
            raise EmbeddingUnavailable()
        return super().embed(texts, task, timeout)


def test_default_runs_only_lexical_and_marks_semantic_modes_untested(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    report = run(CASES)

    assert report["evaluation_mode"] == "offline_lexical"
    assert report["model_version"] is None
    assert report["index_version"] is None
    assert report["modes"]["lexical"]["status"] == "tested"
    assert report["modes"]["vector"]["status"] == "untested"
    assert report["modes"]["hybrid"]["status"] == "untested"
    assert report["modes"]["vector"]["metrics"] is None
    assert report["modes"]["hybrid"]["cases"] == []
    assert "live embedding relevance" in report["not_evaluated"]
    assert not (tmp_path / "retail.db").exists()


def test_lexical_report_contains_ranking_relevance_and_no_result_behavior():
    report = run(CASES)
    lexical = report["modes"]["lexical"]

    positive, negative = lexical["cases"]
    assert positive["returned"][0]["id"] == "monthly-revenue"
    assert positive["returned"][0]["version"] == 1
    assert positive["reciprocal_rank"] == 1
    assert negative["returned"] == []
    assert negative["no_result"] is True
    assert lexical["metrics"]["recall_at_2"] == 1
    assert lexical["metrics"]["mrr"] == 1
    assert lexical["metrics"]["negative_false_match_rate"] == 0
    assert lexical["metrics"]["irrelevant_example_rate"] == 0
    assert lexical["metrics"]["mean_latency_ms"] >= 0


def test_controlled_vectors_cover_mechanics_without_claiming_semantic_quality():
    report = run(CASES, embedder=ControlledEmbeddings(), embedding_source="controlled")

    assert report["evaluation_mode"] == "offline_controlled_vectors"
    assert report["model_version"] == "controlled-test-v1"
    assert len(report["index_version"]) == 64
    assert len(report["corpus_version"]) == 64
    assert set(report["modes"]) == {"lexical", "bm25", "vector", "hybrid"}
    for mode in report["modes"].values():
        assert mode["status"] == "tested"
        assert mode["metrics"]["recall_at_2"] == 1
        assert mode["metrics"]["negative_false_match_rate"] == 0
    assert "live embedding relevance" in report["not_evaluated"]
    assert report["semantic_quality"] == "not_evaluated_controlled_vectors_only"


def test_embedding_failure_never_becomes_successful_lexical_fallback():
    report = run(
        CASES,
        embedder=QueryFailureEmbeddings(),
        embedding_source="controlled",
    )

    assert report["modes"]["lexical"]["status"] == "tested"
    for name in ("vector", "hybrid"):
        assert report["modes"][name]["status"] == "untested"
        assert report["modes"][name]["metrics"] is None
        assert report["modes"][name]["cases"] == []
        assert "unavailable" in report["modes"][name]["reason"]


def test_relevant_version_is_part_of_the_relevance_judgment():
    cases = [{"id": "new-version", "question": "monthly revenue", "relevant": [
        {"id": "monthly-revenue", "version": 2}
    ]}]
    result = run(cases)["modes"]["lexical"]["cases"][0]
    assert result["returned"][0]["id"] == "monthly-revenue"
    assert result["recall"] == 0
    assert result["reciprocal_rank"] == 0


def test_case_file_is_separate_versioned_paraphrase_and_negative_set():
    path = Path(__file__).parents[1] / "evaluation" / "heldout-retrieval-cases.json"
    data = json.loads(path.read_text())
    assert data["dataset_version"]
    assert len(data["cases"]) >= 6
    assert any(case["relevant"] for case in data["cases"])
    assert any(not case["relevant"] for case in data["cases"])
    assert all(case["id"] and case["question"] for case in data["cases"])


def test_invalid_relevance_reference_is_rejected():
    with pytest.raises(ValueError, match="relevant"):
        run([{"id": "bad", "question": "revenue", "relevant": ["monthly-revenue"]}])


def test_cli_default_does_not_configure_live_embeddings(tmp_path, monkeypatch):
    from scripts import evaluate_retrieval as cli

    cases_path = tmp_path / "cases.json"
    output_path = tmp_path / "report.json"
    cases_path.write_text(json.dumps({"dataset_version": "test-v1", "cases": CASES}))

    def unexpected_live_adapter(config):
        raise AssertionError("Default evaluation must not construct GeminiEmbeddings")

    monkeypatch.setattr(cli, "embeddings_for", unexpected_live_adapter)
    monkeypatch.setattr("sys.argv", [
        "evaluate_retrieval.py", "--cases", str(cases_path), "--output", str(output_path)
    ])
    cli.main()

    report = json.loads(output_path.read_text())
    assert report["evaluation_mode"] == "offline_lexical"
    assert report["modes"]["lexical"]["status"] == "tested"
    assert report["modes"]["vector"]["status"] == "untested"
    assert report["modes"]["hybrid"]["status"] == "untested"


def test_multi_cutoff_metrics_and_language_slices_preserve_legacy_at_two():
    report = run(CASES)
    metrics = report["modes"]["lexical"]["metrics"]
    assert report["cutoffs"] == [1, 2, 5]
    assert metrics["by_k"]["1"]["precision"] == 1
    assert metrics["by_k"]["5"]["precision"] == 0.2
    assert metrics["by_k"]["2"]["recall"] == metrics["recall_at_2"]
    assert metrics["by_k"]["2"]["mrr"] == metrics["mrr"]
    assert report["modes"]["lexical"]["by_language"]["en"]["positive_cases"] == 1


def test_graded_annotations_are_preserved_for_ndcg():
    cases = [{"id": "graded", "question": "monthly revenue", "language": "en", "relevant": [
        {"id": "monthly-revenue", "version": 1, "grade": 2},
        {"id": "product-comparison", "version": 1, "grade": 1}]}]
    report = run(cases)
    case = report["modes"]["lexical"]["cases"][0]
    assert case["relevant"][0]["grade"] == 2
    assert case["at_k"]["1"]["ndcg"] == 1
    assert report["judgment_type"] == "graded"


def test_unknown_label_is_reported_without_becoming_a_correct_match():
    report = run([{"id": "typo", "question": "monthly revenue", "relevant": [
        {"id": "typo-trio", "version": 1}]}])
    assert report["label_warnings"] == [{"case": "typo", "id": "typo-trio", "version": 1,
        "category": "reference_not_in_eligible_corpus"}]
    assert report["modes"]["lexical"]["metrics"]["recall_at_2"] == 0


def test_bm25_baseline_is_offline_and_shares_scope_and_metric_contract():
    report = run(CASES)
    mode = report["modes"]["bm25"]
    assert mode["status"] == "tested"
    assert mode["cases"][0]["returned"][0]["id"] == "monthly-revenue"
    assert mode["metrics"]["by_k"]["2"]["recall"] == 1
    assert mode["cases"][1]["no_result"] is True


def test_cli_accepts_requested_cutoffs(tmp_path, monkeypatch):
    from scripts import evaluate_retrieval as cli
    path, output = tmp_path / "cases.json", tmp_path / "report.json"
    path.write_text(json.dumps({"dataset_version": "unit", "cases": CASES}))
    monkeypatch.setattr("sys.argv", ["eval", "--cases", str(path), "--output", str(output), "--k", "1", "2", "10"])
    cli.main()
    assert json.loads(output.read_text())["cutoffs"] == [1, 2, 10]


def test_cli_missing_case_file_is_a_clean_input_error(tmp_path, monkeypatch, capsys):
    from scripts import evaluate_retrieval as cli
    monkeypatch.setattr("sys.argv", ["eval", "--cases", str(tmp_path / "missing"), "--output", str(tmp_path / "report.json")])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
    assert "Case file" in capsys.readouterr().err
