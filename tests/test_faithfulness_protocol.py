import asyncio
import json
import sys
from pathlib import Path

import pytest


def test_schema_judge_evidence_excludes_drafts_history_and_examples():
    from retail.faithfulness_experiments import judge_contexts
    case={'sql_contexts':['{"rows":[{"revenue":98}]}'], 'context':{
        'schema':{'order_items':{'sale_price':'DOUBLE'}},
        'report_review':{'draft':'Invented revenue 999'},
        'history':['Private narrative'], 'trios':[{'report':'Unverified interpretation'}]}}
    contexts=judge_contexts(case,'schema-v1')
    assert contexts[0]=='{"rows":[{"revenue":98}]}'
    assert json.loads(contexts[1])=={'logical_schema':{'order_items':{'sale_price':'DOUBLE'}}}
    assert len(contexts)==2
    contexts.append('changed')
    assert len(case['sql_contexts'])==1
    assert judge_contexts(case,'sql-only')==case['sql_contexts']
    with pytest.raises(ValueError):judge_contexts({'sql_contexts':['rows'],'context':{}},'schema-v1')
    with pytest.raises(ValueError):judge_contexts({**case,'sql_contexts':['rows']*5},'schema-v1')


def test_parallel_judging_preserves_each_case_and_total_call_budget():
    from scripts.run_faithfulness_experiment import judge_batch
    active=peak=0
    budgets=[]
    async def live(samples, config, model, max_calls, names, diagnostics):
        nonlocal active,peak
        assert len(samples)==1 and model=='fixed-judge'
        active+=1;peak=max(peak,active);budgets.append(max_calls)
        await asyncio.sleep(.01)
        active-=1
        case=samples[0]
        return {'status':'tested','cases':[{'id':case['id'],'metrics':{
            'faithfulness':{'status':'measured','value':case['expected'],'source':'ragas',
                'statement_diagnostics':{'statements':[case['id']]}}}}],
            'attempted_provider_calls':2,'measured_total_tokens':10}
    report=asyncio.run(judge_batch(live,[{'id':'a','expected':.5},{'id':'b','expected':1.}],
        None,'fixed-judge',9,['faithfulness'],2))
    assert peak==2 and sorted(budgets)==[4,5]
    assert report['attempted_provider_calls']==4 and report['measured_total_tokens']==20
    assert {c['id']:c['metrics']['faithfulness']['value'] for c in report['cases']}=={'a':.5,'b':1.}
    assert report['cases'][0]['metrics']['faithfulness']['statement_diagnostics']=={'statements':['a']}


def test_runner_pins_explicit_judge_and_schema_context_before_resume(tmp_path,monkeypatch):
    import retail.config
    import retail.deepinfra
    import scripts.evaluate_ragas
    import scripts.run_faithfulness_experiment as cli
    from retail.model import Decision
    cfg=retail.config.Settings(_env_file=None,llm_provider='openai_compatible',
        openai_compatible_base_url='https://gateway.example/v1',
        openai_compatible_api_key='controlled',openai_compatible_model='generator')
    monkeypatch.setattr(retail.config,'Settings',lambda **kw:cfg)
    answer='## Findings\n|count|\n|---|\n|2|\n## Limitations\nOnly this query.\n## Action items\nInspect dates.'
    class Model:
        def __init__(self,config):assert config.deepinfra_model=='generator'
        def decide(self,context,seconds):return Decision(action='answer',text=answer),{}
    monkeypatch.setattr(retail.deepinfra,'DeepInfraModel',Model)
    seen=[]
    async def live(samples,config,judge,*args,**kwargs):
        seen.append((samples,judge))
        return {'status':'tested','cases':[{'id':s['id'],'metrics':{
            n:{'status':'measured','value':1.,'source':'ragas'}
            for n in ('faithfulness','sql_factual_faithfulness')}} for s in samples]}
    monkeypatch.setattr(scripts.evaluate_ragas,'live',live)
    case={'id':'a','family':'a','split':'development','source':'synthetic','question':'Count?',
        'sql_contexts':['count=2'],'required_aliases':['count'],'reference_rows':[{'count':2}],
        'context':{'schema':{'order_items':{'item_key':'VARCHAR'}},'report_review':{'draft':'POISONED'}}}
    (tmp_path/'cases.json').write_text(json.dumps([case]));(tmp_path/'prompt.txt').write_text('Controlled')
    argv=['run','--live','--cases',str(tmp_path/'cases.json'),'--prompt',str(tmp_path/'prompt.txt'),
        '--output-dir',str(tmp_path/'out'),'--judge-model','fixed-judge','--judge-context','schema-v1']
    monkeypatch.setattr(sys,'argv',argv)
    assert cli.main()==0
    assert seen[0][1]=='fixed-judge'
    contexts=seen[0][0][0]['sql_contexts']
    assert contexts[0]=='count=2'
    assert json.loads(contexts[1])=={'logical_schema':{'order_items':{'item_key':'VARCHAR'}}}
    assert 'POISONED' not in json.dumps(contexts)
    r=json.loads((tmp_path/'out/results.json').read_text())
    assert r['judge_model']=='fixed-judge' and r['model']=='generator'
    assert r['judge_context_contract']=='schema-v1' and r['judge_contexts_sha256']
    monkeypatch.setattr(sys,'argv',argv[:-3]+['different-judge','--judge-context','schema-v1'])
    with pytest.raises(SystemExit):cli.main()


def test_comparison_rejects_matching_but_incomplete_runs(tmp_path,monkeypatch):
    import scripts.compare_faithfulness_experiments as cli
    def run(score):
        return {'status':'incomplete','acceptance':'failed_or_incomplete',
            'dataset_sha256':'same','model':'same','judge_model':'fixed','ragas_version':'0.4.4',
            'metric_contract':'same','expected_cases':20,'scored_cases':5,
            'cases':[{'id':str(i),'metrics':{n:{'status':'measured','value':score,'source':'ragas'}
                for n in ('faithfulness','sql_factual_faithfulness')}} for i in range(5)],
            'generations':[{'id':str(i),'family':str(i),'checks':{'passed':True}} for i in range(5)]}
    for name,score in [('before',.5),('after',.9)]:
        (tmp_path/(name+'.json')).write_text(json.dumps(run(score)))
    output=tmp_path/'comparison.json'
    monkeypatch.setattr(sys,'argv',['compare','--baseline',str(tmp_path/'before.json'),
        '--candidate',str(tmp_path/'after.json'),'--output',str(output)])
    assert cli.main()==3
    assert json.loads(output.read_text())['complete_coverage'] is False
