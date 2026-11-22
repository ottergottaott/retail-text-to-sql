"""Build judge inputs from recorded live evidence; never infer context from prose."""
import argparse
import json
from pathlib import Path


def build(report, metadata=None):
    samples=[]
    for case in report['cases']:
        response=case.get('response',{})
        if response.get('outcome')!='succeeded' or not response.get('evidence'):
            continue
        # These pinned verifier cases authenticate Alice, whose configured scope is 1/2.
        # Management metadata is supplied by the application, not extracted from text.
        contexts=[json.dumps({'sql':e['sql'],'rows':e['rows'],'truncated':e['truncated'],
                             'query_id':e['query_id'],'job_id':e['job_id']})
                  for e in response['evidence']]
        contexts.append(json.dumps({'execution_scope':{'authorized_products':[1,2],
            'enforcement':'Trusted executor binds every logical SQL source to authorized physical subqueries.'},
            'management':response.get('management'),
            'persisted_report_metadata':(metadata or {}).get((response.get('management') or {}).get('report_id')),
            'scope_note':'Rows describe the queried population only. No unqueried causal or operational facts are supplied.'}))
        samples.append({'id':case['id'],'question':case['question'],'response':response['answer'],
                        'sql_contexts':contexts,'retrieved_contexts':[],
                        'reference_logic':'','source':'Recorded business verifier response and executor provenance'})
    return samples


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--report-metadata',type=Path)
    a=p.parse_args()
    metadata=json.loads(a.report_metadata.read_text()) if a.report_metadata else None
    a.output.write_text(json.dumps(build(json.loads(a.input.read_text()), metadata),indent=2)+'\n')
