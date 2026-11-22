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
