import math

from retail.experiment_tracking import tracking_payload


def test_metadata_export_excludes_question_answer_rows_and_unmeasured_scores():
    sample = {"id": "case-1", "question": "private question", "response": "private answer",
              "sql_contexts": ["private rows"], "source": "live"}
    result = {"metrics": {"faithfulness": {"status": "measured", "value": .5, "source": "ragas"},
                          "other": {"status": "untested", "value": None}}}
    payload = tracking_payload("run-1", sample, result, {"prompt_sha256": "a" * 64})
    assert payload["scores"] == {"faithfulness": .5}
    assert "private" not in str(payload)
    assert payload["trace_id"] == tracking_payload("run-1", sample, result, {})["trace_id"]
    assert payload["trace_id"] != tracking_payload("run-2", sample, result, {})["trace_id"]


def test_detailed_capture_requires_explicit_synthetic_source():
    import pytest
    with pytest.raises(ValueError, match="synthetic"):
        tracking_payload("r", {"id": "c", "source": "live"}, {"metrics": {}}, {}, capture=True)
    payload = tracking_payload("r", {"id": "c", "source": "synthetic", "question": "Count?",
                                         "response": "2", "sql_contexts": ["count=2"]},
                               {"metrics": {}}, {}, capture=True)
    assert payload["input"]["question"] == "Count?"
    assert payload["output"] == "2"


def test_bad_scores_do_not_become_successful_measurements():
    import pytest
    for bad in [math.nan, math.inf, -.1, 1.1, True]:
        with pytest.raises(ValueError, match="score"):
            tracking_payload("r", {"id": "c"}, {"metrics": {
                "faithfulness": {"status": "measured", "value": bad, "source": "ragas"}}}, {})


def test_export_associates_v4_experiment_and_trace_without_live_content():
    from contextlib import contextmanager
    from types import SimpleNamespace
    from retail.experiment_tracking import export_case
    calls = []
    attributes = {}
    class Client:
        def create_dataset(self, **kw): calls.append(kw)
        def create_dataset_item(self, **kw):
            calls.append(kw)
            return SimpleNamespace(id='item', dataset_id='dataset')
        @contextmanager
        def start_as_current_observation(self, **kw):
            calls.append(kw)
            yield SimpleNamespace(id='observation', _otel_span=SimpleNamespace(set_attributes=attributes.update))
        def create_score(self, **kw): calls.append(kw)
        def flush(self): pass
    client = Client()
    client.api = SimpleNamespace(dataset_run_items=SimpleNamespace(create=lambda **kw: SimpleNamespace(dataset_run_id='experiment')))
    result = export_case(client, 'dataset', 'run', {'id':'case', 'question':'PRIVATE', 'response':'PRIVATE', 'sql_contexts':['PRIVATE']},
                         {'metrics':{'faithfulness':{'status':'measured','source':'ragas','value':.5}}}, {})
    assert result['score_count'] == 1 and 'PRIVATE' not in str(calls)
    assert attributes['langfuse.experiment.id'] == 'experiment'
    assert attributes['langfuse.experiment.item.id'] == 'item'
