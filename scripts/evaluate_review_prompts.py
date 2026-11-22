"""Bounded paired review-prompt evaluation; --live explicitly enables billed calls.

Standalone evaluation process only: changes the adapter prompt within this process,
never the running API. Inputs/evidence and both prompts remain fixed for a run.
"""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from retail.model import SYSTEM
from retail.security import safe_output


def validate_cases(cases):
    if not isinstance(cases,list) or not 1 <= len(cases) <= 8:
        raise ValueError('Provide 1–8 cases.')
    seen=set()
    for c in cases:
        if not isinstance(c,dict) or not isinstance(c.get('id'),str) or c['id'] in seen:
            raise ValueError('Cases require unique string IDs.')
        seen.add(c['id'])
        if c.get('split') not in {'calibration','validation'} or not isinstance(c.get('context'),dict):
            raise ValueError('Each case needs a split and context object.')
        if not isinstance(c.get('question'),str) or not isinstance(c.get('sql_contexts'),list):
            raise ValueError('Each case needs a question and original SQL contexts.')
        if not 1 <= len(c['sql_contexts']) <= 5 or any(not isinstance(x,str) for x in c['sql_contexts']):
            raise ValueError('Provide 1–5 string SQL contexts.')
        serialized=json.dumps(c)
        if len(serialized)>64000:
            raise ValueError('Case exceeds context budget.')
        safe_output(serialized)
    return cases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    default=Path('evaluation/prompt-iteration-2026-11-22')
    parser.add_argument('--live',action='store_true',help='At most 16 generation + 96 judge HTTP attempts; no SQL execution.')
    parser.add_argument('--cases',type=Path,default=default/'cases.json')
    parser.add_argument('--baseline',type=Path,default=default/'baseline.txt')
    parser.add_argument('--candidate',type=Path,default=default/'candidate.txt')
    parser.add_argument('--env-file',type=Path,default=Path('.env.live'))
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    OUT=args.output_dir
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'results.json').exists():
        parser.error('Output already exists; choose a new directory to preserve evidence.')
    if not args.live:
        (OUT/'results.json').write_text(json.dumps({'status':'untested','reason':'Live calls not requested; no input/settings read.'})+'\n')
        return 0
    try:
        cases=validate_cases(json.loads(args.cases.read_text()))
        for p in (args.baseline,args.candidate):
            if not 1 <= len(p.read_text()) <= 24000:
                raise ValueError('Prompt size outside 1–24000 characters.')
    except (OSError,ValueError):
        parser.error('Invalid prompt/case input. Check paths, schema, size and privacy.')
    from retail.config import Settings
    import retail.deepinfra as provider
    from scripts.evaluate_ragas import live
    print(json.dumps({'maximum_generation_calls':2*len(cases),'maximum_judge_calls':96,'billed_calls':True}),flush=True)
    try:
        cfg=Settings(_env_file=args.env_file)
    except ValueError:
        parser.error('Invalid provider settings; check configuration without printing credentials.')
    if not cfg.deepinfra_api_key:
        parser.error('DeepInfra credentials are required for this evaluation.')
    model_name=cfg.deepinfra_review_model or cfg.deepinfra_model
    cfg=cfg.model_copy(update={'deepinfra_model':model_name})
    report={'status':'running','model':model_name,'judge_model':'google/gemini-3.5-flash',
        'data_source':'frozen synthetic SQL evidence; no query executed',
        'live_bigquery_verified':False,'production_changed':False,'repetitions':1,
        'selection':{'split_counts':{split:sum(c['split']==split for c in cases)
            for split in ['calibration','validation']},'protocol':'Inputs fixed before calls; prior exposure must be documented by the experiment author.'},
        'cases_sha256':hashlib.sha256(args.cases.read_bytes()).hexdigest(),'variants':{}}
    start=time.monotonic()
    for version in ['baseline','candidate']:
        provider.SYSTEM=(args.baseline if version=='baseline' else args.candidate).read_text()
        def generate(c):
            t=time.monotonic()
            try:
                d,usage=provider.DeepInfraModel(cfg).decide(c['context'],30)
                safe_output(d.model_dump_json())
                return {'id':c['id'],'split':c['split'],'status':'generated','action':d.action,'response':d.text,
                    'seconds':time.monotonic()-t,'usage':usage}
            except Exception as error:
                return {'id':c['id'],'split':c['split'],'status':'failed','error_category':type(error).__name__,'seconds':time.monotonic()-t}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(generate,cases))
        samples=[{'id':c['id'],'question':c['question'],'response':r['response'],
            'sql_contexts':c['sql_contexts'],'retrieved_contexts':[]} for c,r in zip(cases,results) if r['status']=='generated' and r['action']=='answer']
        OUT.joinpath(version+'-samples.json').write_text(json.dumps(samples,indent=2)+'\n')
        report['variants'][version]={'prompt_sha256':hashlib.sha256(provider.SYSTEM.encode()).hexdigest(),'responses':results,
            'generation_summary':{'mean_seconds':sum(r['seconds'] for r in results)/len(results),
                'measured_input_tokens':sum(r.get('usage',{}).get('input_tokens') or 0 for r in results),
                'measured_output_tokens':sum(r.get('usage',{}).get('output_tokens') or 0 for r in results)}}
        OUT.joinpath('results.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'phase':'generation','variant':version,'generated':len(samples),'total':len(cases)}),flush=True)
    provider.SYSTEM=SYSTEM
    all_samples=[]
    for version in ['baseline','candidate']:
        for s in json.loads(OUT.joinpath(version+'-samples.json').read_text()):
            all_samples.append({**s,'id':version+'__'+s['id']})
    # Judge prompt/contracts stay unchanged. Scores retain original evidence and drafts are not evidence.
    if not all_samples:
        report.update(status='incomplete',reason='No valid generated answers; judge not called.')
        OUT.joinpath('results.json').write_text(json.dumps(report,indent=2)+'\n')
        return 3
    judge=asyncio.run(live(all_samples,cfg,'google/gemini-3.5-flash',96,
        ['faithfulness','sql_factual_faithfulness']))
    OUT.joinpath('judge-results.json').write_text(json.dumps(judge,indent=2)+'\n')
    from retail.ragas_evaluation import summarize
    for version in ['baseline','candidate']:
        selected=[c for c in judge['cases'] if c['id'].startswith(version+'__')]
        report['variants'][version]['judge_summary']=summarize(selected,['faithfulness','sql_factual_faithfulness']) if selected else {'status':'untested'}
        for split in ['calibration','validation']:
            ids={c['id'] for c in cases if c['split']==split}
            part=[c for c in selected if c['id'].split('__',1)[1] in ids]
            report['variants'][version][split]=summarize(part,['faithfulness','sql_factual_faithfulness']) if part else {'status':'untested'}
    expected={version+'__'+c['id'] for version in ['baseline','candidate'] for c in cases}
    scored={c['id'] for c in judge['cases'] if all(
        c.get('metrics',{}).get(m,{}).get('status')=='measured' and
        c.get('metrics',{}).get(m,{}).get('source')=='ragas'
        for m in ['faithfulness','sql_factual_faithfulness'])}
    complete=scored==expected and len(all_samples)==len(expected)
    report.update(status=judge['status'] if complete else 'incomplete',seconds=time.monotonic()-start,
        coverage={'expected_answers':len(expected),'generated_answers':len(all_samples),
            'scored_answers':len(scored & expected),'missing_ids':sorted(expected-scored)},
        human_review='pending',limitations=['Small targeted adversarial set, not overall product accuracy.','Temperature zero is not deterministic.','No planner/tool-routing, retrieval or real BigQuery quality measured.','Standard and custom scores are distinct contracts.'],
        judge_calls=judge['attempted_provider_calls'],cost=None)
    OUT.joinpath('results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'variants':{k:v['judge_summary'] for k,v in report['variants'].items()}}),flush=True)
    return 0 if report["status"]=="tested" else 3


if __name__=="__main__":
    raise SystemExit(main())
