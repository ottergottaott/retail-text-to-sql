"""Mock SDK contracts only; none of these tests count as live BigQuery evidence."""
from types import SimpleNamespace
import pytest
from google.cloud import bigquery
from retail.analytics import Analytics, QueryUnavailable
from retail.config import Settings
from retail.security import principal_for, PolicyError


def test_bigquery_binding_parameters_budgets_and_disabled_sdk_retries(monkeypatch):
    config = Settings(retail_mode="live", google_cloud_project="test-project")
    calls = []
    class Job:
        job_id = "mock-job"
        total_bytes_processed = 123
        def result(self, **kwargs):
            assert kwargs["retry"] is None and kwargs["job_retry"] is None
            assert 0 < kwargs["timeout"] <= 40
            return [{"n": 2}]
    class Client:
        def __init__(self, **kwargs): pass
        def query(self, sql, job_config, **kwargs):
            calls.append((sql, job_config.to_api_repr(), kwargs))
            return SimpleNamespace(total_bytes_processed=100) if job_config.dry_run else Job()
        def close(self): pass
    monkeypatch.setattr(bigquery, "Client", Client)
    result = Analytics(config).execute("SELECT COUNT(*) AS n FROM products", principal_for("alice", config))
    assert result["job_id"] == "mock-job" and result["estimated_bytes"] == 100
    assert len(calls) == 2
    assert "thelook_ecommerce.products" in calls[1][0] and "UNNEST(@products)" in calls[1][0]
    assert calls[0][1]["dryRun"] is True
    assert calls[1][1]["query"]["maximumBytesBilled"] == str(config.maximum_bytes_billed)
    assert calls[1][2]["retry"] is None and calls[1][2]["job_retry"] is None
    parameters = calls[1][1]["query"]["queryParameters"]
    assert parameters[0]["parameterValue"]["arrayValues"] == [{"value": "1"}, {"value": "2"}]


def test_auth_failure_is_sanitized_and_byte_budget_blocks_execution(monkeypatch):
    config = Settings(retail_mode="live", google_cloud_project="test-project")
    def broken(**kwargs): raise RuntimeError("secret@example.com provider diagnostic")
    monkeypatch.setattr(bigquery, "Client", broken)
    with pytest.raises(QueryUnavailable) as error:
        Analytics(config).execute("SELECT COUNT(*) AS n FROM products", principal_for("alice", config))
    assert "secret@example.com" not in str(error.value)
    class Client:
        calls = 0
        def __init__(self, **kwargs): pass
        def query(self, sql, job_config, **kwargs):
            self.__class__.calls += 1
            return SimpleNamespace(total_bytes_processed=config.maximum_bytes_billed + 1)
        def close(self): pass
    monkeypatch.setattr(bigquery, "Client", Client)
    with pytest.raises(PolicyError):
        Analytics(config).execute("SELECT COUNT(*) AS n FROM products", principal_for("alice", config))
    assert Client.calls == 1
