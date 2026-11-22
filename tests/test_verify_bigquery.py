"""Controlled-adapter checks for the standalone verifier.

These tests exercise mechanics only. A controlled adapter result is never live
BigQuery evidence, and none of these tests contact Google Cloud, use or transmit
credentials, or count as provider verification. Settings-based tests may load
ambient environment values into memory.
"""
import importlib.util
import json
from pathlib import Path
import pytest

from retail.analytics import QueryError, QueryUnavailable, validate
from retail.config import Settings


def load_verifier():
    path = Path(__file__).parents[1] / "scripts/verify_bigquery.py"
    spec = importlib.util.spec_from_file_location("verify_bigquery", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def controlled_outcome():
    # Deliberately returns an aggregate value and metadata. Only metadata may
    # appear in the report.
    return {
        "rows": [{"row_count": 987654}],
        "mode": "live",
        "job_id": "unit-job-id",
        "bytes_processed": 10,
        "estimated_bytes": 9,
        "truncated": False,
        "seconds": 0.01,
    }


def test_default_invocation_makes_no_query():
    module = load_verifier()
    calls = []

    def executor(sql):
        calls.append(sql)
        raise AssertionError("Default invocation must not query")

    report, code = module.verify(False, config=Settings(), executor=executor)

    assert code == 0
    assert report["queried"] is False
    assert report["status"] == "live_not_requested"
    assert report["results"] == []
    assert calls == []


def test_live_without_project_is_safe_and_unconfigured():
    module = load_verifier()
    calls = []

    def executor(sql):
        calls.append(sql)
        raise AssertionError("Missing configuration must not query")

    config = Settings(google_cloud_project="", retail_mode="fixture")
    report, code = module.verify(True, config=config, executor=executor)

    assert code == 2
    assert report["status"] == "unconfigured"
    assert report["queried"] is False
    assert report["results"] == []
    assert calls == []


def test_controlled_adapter_covers_all_four_tables_with_metadata_only():
    module = load_verifier()
    config = Settings(google_cloud_project="unit-project", label_secret="unit-secret")
    calls = []

    def executor(sql):
        calls.append(sql)
        return controlled_outcome()

    report, code = module.verify(True, config=config, executor=executor)

    assert code == 0
    assert report["queried"] is True
    assert [entry["table"] for entry in report["results"]] == list(module.TABLES)
    assert len(calls) == len(module.QUERIES) == 4

    for (table, sql), executed in zip(module.QUERIES, calls):
        _, base = validate(sql)
        assert {source.name for source in base} == {table}
        assert sql == executed

    serialized = json.dumps(report)
    assert "987654" not in serialized
    assert "unit-secret" not in serialized
    assert "unit-project" not in serialized
    for entry in report["results"]:
        assert set(entry["result"]) == {
            "mode",
            "rows_returned",
            "columns",
            "job_id",
            "bytes_processed",
            "estimated_bytes",
            "truncated",
            "seconds",
        }
        assert entry["result"]["rows_returned"] == 1
        assert entry["result"]["columns"] == ["row_count"]

    # A controlled adapter can pass mechanics, but it is never reported as
    # successful live BigQuery verification.
    assert report["status"] == "unit_controlled"
    assert report["evidence"]["kind"] == "controlled_adapter"
    assert "not live" in report["evidence"]["note"]


def test_unavailable_is_categorized_without_leaking_service_detail():
    module = load_verifier()
    config = Settings(google_cloud_project="unit-project")

    def executor(sql):
        raise QueryUnavailable("login failed for secret@example.com")

    report, code = module.verify(True, config=config, executor=executor)

    assert code == 3
    assert report["status"] == "incomplete_controlled"
    assert all(entry["status"] == "unavailable" for entry in report["results"])
    serialized = json.dumps(report)
    assert "secret@example.com" not in serialized
    assert "login failed" not in serialized


def test_query_error_and_non_live_outcomes_are_not_success():
    module = load_verifier()
    config = Settings(google_cloud_project="unit-project")

    def rejected(sql):
        raise QueryError("provider quoted a literal")

    report, code = module.verify(True, config=config, executor=rejected)
    assert code == 3
    assert all(entry["status"] == "query_error" for entry in report["results"])
    assert "provider quoted a literal" not in json.dumps(report)

    def fixture_mode(sql):
        return {**controlled_outcome(), "mode": "fixture"}

    report, code = module.verify(True, config=config, executor=fixture_mode)
    assert code == 3
    assert report["status"] == "incomplete_controlled"
    assert all(entry["status"] == "not_live" for entry in report["results"])


def test_main_exits_zero_without_live_and_emits_json(capsys):
    module = load_verifier()
    assert module.main([]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["live_requested"] is False
    assert payload["queried"] is False
    assert payload["status"] == "live_not_requested"


def test_live_requires_explicit_product_scope(capsys):
    module = load_verifier()
    assert module.main(["--live", "--project", "unit-project"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["queried"] is False
    assert payload["status"] == "unconfigured"
    assert "--products" in payload["evidence"]["note"]


def test_build_config_sets_project_and_explicit_products():
    module = load_verifier()
    config = module.build_config(True, project="unit-project", products=[2, 1, 2])
    assert config.retail_mode == "live"
    assert config.google_cloud_project == "unit-project"
    assert json.loads(config.entitlements_json) == {"alice": [1, 2]}


def test_no_live_does_not_load_settings(monkeypatch, capsys):
    module = load_verifier()

    def forbidden_settings():
        raise AssertionError("No-live invocation must not load environment settings")

    monkeypatch.setattr(module, "Settings", forbidden_settings)
    report, code = module.verify(False)
    assert code == 0 and report["queried"] is False
    assert module.main([]) == 0
    assert json.loads(capsys.readouterr().out)["queried"] is False


@pytest.mark.parametrize("secret", ["local-fixture-label-secret", "", "   "])
def test_live_rejects_unsafe_label_secret_before_executor(monkeypatch, secret):
    module = load_verifier()
    config = Settings(_env_file=None, google_cloud_project="unit-project", label_secret=secret)

    def forbidden_executor(config):
        raise AssertionError("Unsafe configuration must not construct the live executor")

    monkeypatch.setattr(module, "Analytics", forbidden_executor)
    report, code = module.verify(True, config=config)
    assert code == 2
    assert report["status"] == "unconfigured"
    assert report["queried"] is False
    assert "LABEL_SECRET" in report["evidence"]["note"]


def test_expired_shared_budget_stops_submitting_queries(monkeypatch):
    module = load_verifier()
    config = Settings(_env_file=None, google_cloud_project="unit-project",
                      label_secret="unit-secret", max_seconds=1)
    clock = [100.0]
    calls = []

    def execute(self, sql, principal, remaining_seconds):
        calls.append((sql, remaining_seconds))
        clock[0] = 102.0
        return controlled_outcome()

    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(module.Analytics, "execute", execute)
    report, code = module.verify(True, config=config)
    assert code == 3
    assert len(calls) == 1
    assert calls[0][1] == 1.0
    assert report["results"][0]["status"] == "ok"
    assert [entry["status"] for entry in report["results"][1:]] == ["budget_exhausted"] * 3


@pytest.mark.parametrize("flags", [["--project", "unit-project"], ["--products", "1"]])
def test_scope_flags_without_live_are_rejected(flags, capsys):
    module = load_verifier()
    with pytest.raises(SystemExit) as error:
        module.main(flags)
    assert error.value.code == 2
    assert "--live" in capsys.readouterr().err
