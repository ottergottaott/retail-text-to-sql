import json
from pathlib import Path
import subprocess
import sys
import pytest


def test_review_prompt_cli_default_reads_no_inputs_or_settings(tmp_path):
    output=tmp_path/'result.json'
    result=subprocess.run([sys.executable,'scripts/evaluate_review_prompts.py',
        '--cases','/missing-cases','--env-file','/missing-secrets','--output-dir',str(tmp_path)],
        capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads((tmp_path/'results.json').read_text())['status']=='untested'


def test_review_prompt_inputs_are_bounded_before_paid_calls():
    from scripts.evaluate_review_prompts import validate_cases
    with pytest.raises(ValueError):
        validate_cases([{}]*9)
    with pytest.raises(ValueError):
        validate_cases([])


def test_review_prompt_accepts_openai_compatible_gateway_credentials():
    from types import SimpleNamespace
    from scripts.evaluate_review_prompts import provider_ready, generation_model_name

    cfg = SimpleNamespace(
        llm_provider='openai_compatible',
        openai_compatible_api_key='gateway-key',
        openai_compatible_base_url='https://gateway.example/v1',
        openai_compatible_model='gemini-4-neon',
        deepinfra_api_key='',
        deepinfra_model='google/gemini-3.7-flash',
        deepinfra_review_model='',
    )
    assert provider_ready(cfg)
    assert generation_model_name(cfg) == 'gemini-4-neon'


def test_live_evaluation_calls_gateway_even_with_fixture_application_mode(monkeypatch, tmp_path):
    import httpx
    import retail.deepinfra as provider
    from retail.config import Settings
    from scripts.evaluate_review_prompts import generation_config

    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={
            'choices': [{'message': {'tool_calls': [{'function': {
                'arguments': json.dumps({'action': 'answer', 'text': 'Gateway answer.'})
            }}]}}],
            'usage': {'prompt_tokens': 12, 'completion_tokens': 4, 'total_tokens': 16},
        })
    real_client = httpx.Client
    monkeypatch.setattr(provider.httpx, 'Client', lambda *a, **kw: real_client(
        *a, **kw, transport=httpx.MockTransport(respond)))
    cfg = Settings(_env_file=None, retail_mode='fixture', llm_provider='openai_compatible',
                   openai_compatible_base_url='https://gateway.example/v1',
                   openai_compatible_api_key='controlled', openai_compatible_model='flash')
    decision, usage = provider.DeepInfraModel(generation_config(cfg)).decide({'question': 'Count?'}, 30)
    assert decision.text == 'Gateway answer.'
    assert usage['usage_source'] == 'provider_measured'
    assert len(requests) == 1
    assert str(requests[0].url) == 'https://gateway.example/v1/chat/completions'
    assert json.loads(requests[0].content)['model'] == 'flash'

    import retail.config
    import scripts.evaluate_ragas
    import scripts.evaluate_review_prompts as cli
    monkeypatch.setattr(retail.config, 'Settings', lambda **kw: cfg)
    async def judge(samples, *args):
        return {'status': 'tested', 'attempted_provider_calls': 0, 'cases': [
            {'id': s['id'], 'metrics': {m: {'status': 'measured', 'value': 1.0, 'source': 'ragas'}
             for m in ['faithfulness', 'sql_factual_faithfulness']}} for s in samples]}
    monkeypatch.setattr(scripts.evaluate_ragas, 'live', judge)
    cases = json.loads(Path('evaluation/prompt-iteration-3-2026-11-22/cases.json').read_text())[:1]
    case_file = tmp_path/'cases.json'
    case_file.write_text(json.dumps(cases))
    monkeypatch.setattr(sys, 'argv', ['eval', '--live', '--cases', str(case_file),
                                   '--output-dir', str(tmp_path)])
    assert cli.main() == 0
    report = json.loads((tmp_path/'results.json').read_text())
    assert len(requests) == 3  # One adapter call and both CLI variants reach the gateway.
    assert all(v['responses'][0]['usage']['usage_source'] == 'provider_measured'
               for v in report['variants'].values())


@pytest.mark.parametrize('missing', ['generation', 'action', 'judge'])
def test_live_run_cannot_claim_tested_with_missing_answers_or_scores(tmp_path, monkeypatch, missing):
    from types import SimpleNamespace
    import scripts.evaluate_review_prompts as cli
    import retail.config
    import retail.deepinfra
    import scripts.evaluate_ragas
    from retail.model import Decision
    cases=json.loads(Path('evaluation/prompt-iteration-2026-11-22/cases.json').read_text())[:2]
    cases[1]['split']='validation'
    case_file=tmp_path/'cases.json'
    case_file.write_text(json.dumps(cases))
    cfg=SimpleNamespace(deepinfra_api_key='controlled',deepinfra_review_model='controlled',deepinfra_model='controlled')
    cfg.model_copy=lambda **kwargs: cfg
    monkeypatch.setattr(retail.config,'Settings',lambda **kwargs: cfg)
    class ControlledModel:
        def __init__(self, config): pass
        def decide(self, context, remaining):
            if context['question']==cases[1]['question']:
                if missing=='generation': raise RuntimeError('controlled failure')
                if missing=='action': return Decision(action='clarify',text='Which period?'),{}
            return Decision(action='answer',text='Controlled answer.'),{}
    monkeypatch.setattr(retail.deepinfra,'DeepInfraModel',ControlledModel)
    async def judge(samples,*args):
        selected=samples[:-1] if missing=='judge' else samples
        return {'status':'tested','attempted_provider_calls':0,'cases':[
            {'id':s['id'],'metrics':{m:{'status':'measured','value':1.0,'source':'ragas'}
             for m in ['faithfulness','sql_factual_faithfulness']}} for s in selected]}
    monkeypatch.setattr(scripts.evaluate_ragas,'live',judge)
    monkeypatch.setattr(sys,'argv',['eval','--live','--cases',str(case_file),'--output-dir',str(tmp_path)])
    assert cli.main()==3
    report=json.loads((tmp_path/'results.json').read_text())
    assert report['status']=='incomplete'
    assert report['selection']['split_counts']=={'calibration':1,'validation':1}
    assert report['coverage']['expected_answers']==4
    assert report['coverage']['scored_answers']<4
