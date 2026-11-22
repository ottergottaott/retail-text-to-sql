"""Summarize pinned comparisons without replacing metrics or hiding failed turns."""
import json
from pathlib import Path
import hashlib

ROOT=Path(__file__).resolve().parents[1]/'evaluation'
def load(name):return json.loads((ROOT/name).read_text())

def main():
    names={'comparison':'faithfulness-comparison-results-2026-11-21.json',
           'calibration':'faithfulness-calibration-results-2026-11-21.json',
           'business':'live-business-grounded-v7-2026-11-21.json',
           'fresh':'faithfulness-live-results-2026-11-21.json',
           'sql_calibration':'faithfulness-sql-calibration-results-2026-11-21.json',
           'sql_live':'faithfulness-sql-live-results-2026-11-21.json',
           'final_business':'live-business-pro-final-2026-11-21.json',
           'final_judge':'faithfulness-pro-live-results-2026-11-21.json'}
    data={k:load(v) for k,v in names.items()}
    comparison=[]
    for metric in ['faithfulness','factual_faithfulness']:
        groups={group:[c['metrics'][metric]['value'] for c in data['comparison']['cases']
                       if c['id'].startswith(group+'-') and c['metrics'][metric]['status']=='measured']
                for group in ['baseline','reviewed']}
        comparison.append({'name':metric,'before':sum(groups['baseline'])/len(groups['baseline']),
                           'after':sum(groups['reviewed'])/len(groups['reviewed']),
                           'better':'higher','context':'4 identical recorded evidence sets (1 live, 3 fixture); v5 replay, not fresh v6'})
    calibration=[{'name':c['id'], 'value':c['metrics']['factual_faithfulness']['value'],
                  'status':'passed' if c['metrics']['factual_faithfulness']['status']=='measured' and
                  (c['metrics']['factual_faithfulness']['value']==1 if c['id']=='supported' else c['metrics']['factual_faithfulness']['value']<1) else 'failed'}
                 for c in data['calibration']['cases']]
    business=data['business']; fresh=data['fresh']
    sql_groups={}
    for label, recheck in [('full_run',False),('focused_rechecks',True)]:
        cases=[c for c in data['sql_live']['cases'] if c['id'].startswith('recheck-')==recheck]
        values=[c['metrics']['sql_factual_faithfulness']['value'] for c in cases if c['metrics']['sql_factual_faithfulness']['status']=='measured']
        sql_groups[label]={'mean':sum(values)/len(values) if values else None,'scored':len(values),'total':len(cases)}
    sql_calibration=[{'name':c['id'],'value':c['metrics']['sql_factual_faithfulness'].get('value'),
        'status':'passed' if c['metrics']['sql_factual_faithfulness']['status']=='measured' and
        (c['metrics']['sql_factual_faithfulness']['value']==1 if c['id'].startswith('supported') else c['metrics']['sql_factual_faithfulness']['value']<1) else 'failed'}
        for c in data['sql_calibration']['cases']]
    report={'comparison':comparison,'calibration':calibration,
            'business':{'status':business['status'],'passed':sum(c.get('status')=='passed' for c in business['cases']),'total':len(business['cases'])},
            'fresh':{'status':fresh['status'],'means':fresh['means'],'coverage':fresh['coverage']},
            'sql_aware':sql_groups,'sql_calibration':sql_calibration,
            'final_pro':{'business_status':data['final_business']['status'],'attempts':data['final_business']['attempts'],'business_passed':sum(c.get('status')=='passed' for c in data['final_business']['cases']),'total':len(data['final_business']['cases']),'judge_status':data['final_judge']['status'],'means':data['final_judge']['means'],'coverage':data['final_judge']['coverage']},
            'quality_status':'human_review_required',
            'known_flags':['Focused Flash recheck reintroduced the unsupported no-discounts inference; it is a report-quality failure despite matching SQL and saving.', 'Automatic review and judge scores are fallible; no general hallucination-free claim.'],
            'sources':{key:{'file':name,'sha256':hashlib.sha256((ROOT/name).read_bytes()).hexdigest()} for key,name in names.items()},
            'limitations':['Advisory LLM judging; same Gemini judge and application family introduces self-judge bias.',
                           'Four-record comparison and twelve live business cases are small samples, not a statistical benchmark.',
                           'Whole-response and scoped factual metrics differ; neither proves SQL correctness or human acceptance.',
                           'Live public data changed between historical and fresh runs; only replay uses identical contexts.',
                           'Preserve failed v5/v6 runs. A successful later run does not erase their reliability failures.']}
    (ROOT/'faithfulness-summary-2026-11-21.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
