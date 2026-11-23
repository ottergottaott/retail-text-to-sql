import asyncio
from types import SimpleNamespace

import pytest

from retail.faithfulness_experiments import validate_suite, compare_runs, record_diagnostics, check_answer


def case(id, family, split):
    return {"id": id, "family": family, "split": split, "source": "synthetic",
            "question": "Show count in a table.", "sql_contexts": ["count=2"],
            "context": {"report_review": {"draft": "Count is 2"}},
            "required_aliases": ["count"], "reference_rows": [{"count": 2}]}


def test_family_leakage_rejected_before_any_calls():
    with pytest.raises(ValueError, match="family"):
        validate_suite([case("a", "same", "development"), case("b", "same", "test")])
    assert len(validate_suite([case("a", "one", "development"), case("b", "two", "test")])) == 2
    with pytest.raises(ValueError, match="identifier"):
        validate_suite([case("../escape", "one", "development")])


def test_partial_and_negative_runs_cannot_promote():
    def results(values):
        return [{"id": str(i), "score": v, "checks_passed": True} for i, v in enumerate(values)]
    assert compare_runs(results([.5, .5]), results([.8]))["promotable"] is False
    assert compare_runs(results([.5, .5]), results([.4, .4]))["promotable"] is False
    positive = compare_runs(results([.5] * 10), results([.8] * 10))
    assert positive["mean_delta"] == pytest.approx(.3)
    assert positive["delta_ci95"][0] > 0
    assert positive["paired_score_gate_passed"] is True
    assert positive["promotable"] is False
    assert compare_runs(results([.5] * 10), results([.8] * 10), split='validation',
                        independent_review=True, sealed_test_passed=True)["promotable"] is True
    invalid = results([.8] * 10)
    invalid[0]["checks_passed"] = False
    assert compare_runs(results([.5] * 10), invalid)["promotable"] is False


def test_recording_preserves_metric_calls_score_and_prompts():
    class Metric:
        prompt = "unaltered"
        async def _create_verdicts(self, statements, context):
            return SimpleNamespace(model_dump=lambda: {"statements": [
                {"statement": statements[0], "verdict": 1, "reason": "count=2"}]})
        async def ascore(self, **kwargs):
            await self._create_verdicts(["Count is 2"], "count=2")
            return SimpleNamespace(value=1.)
    metric = record_diagnostics(Metric())
    result = asyncio.run(metric.ascore())
    assert result.value == 1 and metric.prompt == "unaltered"
    assert metric.diagnostics["statements"][0]["verdict"] == 1


def test_table_completeness_and_wrong_values_are_not_rewarded():
    c = {"reference_rows": [{"revenue": 98, "items": 2}], "required_aliases": ["revenue", "items"]}
    assert check_answer(c, "## Findings\n|revenue|items|\n|---|---|\n|98|2|\n## Limitations\nOnly queried totals.\n## Action items (proposed)\nQuery month.")["passed"]
    assert not check_answer(c, "Revenue is 98.")["passed"]
    assert not check_answer(c, "## Findings\n|revenue|items|\n|---|---|\n|980|2|\n## Limitations\nUnknown.\n## Action items\nCheck.")["passed"]


def test_empty_result_records_wording_does_not_bypass_nonempty_oracle():
    answer = '|id|complete_items|\n|---|---|\n\n(No records returned)\nLimitations: queried scope only.\nAction items: check status distribution.'
    empty = {'reference_rows': [], 'required_aliases': ['id', 'complete_items']}
    assert check_answer(empty, answer)['passed']
    nonempty = {**empty, 'reference_rows': [{'id': 1, 'complete_items': 2}]}
    assert not check_answer(nonempty, answer)['passed']


def test_numeric_zero_rows_phrase_covers_empty_result_only():
    answer = ('|id|complete_items|\n|---|---|\n\n'
              'No products met this condition (0 rows returned).\n'
              'Limitations: queried scope only.\n'
              'Action items: check status distribution.')
    empty = {'reference_rows': [], 'required_aliases': ['id', 'complete_items']}
    assert check_answer(empty, answer)['passed']
    nonempty = {**empty, 'reference_rows': [{'id': 1, 'complete_items': 2}]}
    assert not check_answer(nonempty, answer)['passed']


def test_exact_table_rows_and_save_claims_are_checked():
    c = {"reference_rows": [{"category": "Tops & Tees", "items": 2}, {"category": "Tops & Tees", "items": 2}],
         "required_aliases": ["category", "items"]}
    one = "|category|items|\n|---|---|\n|Tops & Tees|2|\nLimitations: only this query. Action items: query month."
    assert not check_answer(c, one)["passed"]
    two = one.replace('|Tops & Tees|2|', '|Tops & Tees|2|\n|Tops & Tees|2|')
    assert check_answer(c, two)["passed"]
    assert not check_answer(c, two.replace('Tops & Tees', 'Tops'))["passed"]
    for claim in ['Saved as rep_deadbeef', 'I saved the report', 'Saved to your library']:
        assert not check_answer(c, two+'\n'+claim)["passed"]


def test_suite_requires_declared_source_and_table_oracle():
    for field in ['source', 'required_aliases', 'reference_rows']:
        c = case('one', 'family', 'development')
        del c[field]
        with pytest.raises(ValueError):
            validate_suite([c])


@pytest.mark.parametrize('custom_gateway', [False, True])
def test_resume_rechecks_only_missing_case_and_retains_failed_attempt(tmp_path, monkeypatch, custom_gateway):
    import json
    import sys
    import retail.config
    import retail.deepinfra
    import scripts.evaluate_ragas
    from scripts.run_faithfulness_experiment import main
    cfg = SimpleNamespace(deepinfra_api_key='controlled-key', deepinfra_review_model='controlled', deepinfra_model='controlled')
    cfg.model_copy = lambda **kw: cfg
    if custom_gateway:
        cfg = retail.config.Settings(_env_file=None, retail_mode='fixture',
            llm_provider='openai_compatible', deepinfra_api_key='',
            openai_compatible_api_key='custom-key', openai_compatible_model='custom-flash',
            openai_compatible_base_url='https://gateway.example/v1')
    monkeypatch.setattr(retail.config, 'Settings', lambda **kw: cfg)
    attempts = {}
    answer = '## Findings\n|count|\n|---|\n|2|\n## Limitations\nOnly this query.\n## Action items\nCheck month.'
    class Model:
        def __init__(self, cfg):
            if custom_gateway:
                assert cfg.deepinfra_api_key == 'custom-key'
                assert cfg.deepinfra_model == 'custom-flash'
                assert cfg.deepinfra_base_url == 'https://gateway.example/v1'
        def decide(self, context, seconds):
            key = context['case_id']
            attempts[key] = attempts.get(key, 0)+1
            if key == 'b' and attempts[key] == 1: raise TimeoutError()
            return retail.deepinfra.Decision(action='answer', text=answer), {}
    monkeypatch.setattr(retail.deepinfra, 'DeepInfraModel', Model)
    judged = []
    async def live(samples, *args, **kw):
        judged.append([s['id'] for s in samples])
        return {'status':'tested', 'cases':[{'id':s['id'], 'metrics':{
            name:{'status':'measured','value':1.,'source':'ragas'}
            for name in ['faithfulness','sql_factual_faithfulness']}} for s in samples]}
    monkeypatch.setattr(scripts.evaluate_ragas, 'live', live)
    cases = [case('a','a','development'), case('b','b','development')]
    for c in cases: c['context']['case_id'] = c['id']
    (tmp_path/'cases.json').write_text(json.dumps(cases))
    (tmp_path/'prompt.txt').write_text('controlled')
    monkeypatch.setattr(sys,'argv',['run','--live','--cases',str(tmp_path/'cases.json'),
        '--prompt',str(tmp_path/'prompt.txt'),'--output-dir',str(tmp_path/'run')])
    assert main() == 3
    assert main() == 0
    assert attempts == {'a':1,'b':2}
    assert judged == [['a'],['b']]
    assert (tmp_path/'run/b.attempt-1.json').exists()
    result = json.loads((tmp_path/'run/results.json').read_text())
    assert result['scored_cases'] == 2 and result['generation_attempts'] == 3
    if custom_gateway:
        assert result['generation_provider'] == 'openai_compatible'
        assert result['model'] == 'custom-flash'
