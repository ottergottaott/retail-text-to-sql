"""Compare complete frozen-evidence runs; never promotes serving automatically."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retail.faithfulness_experiments import compare_runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    before = json.loads(args.baseline.read_text())
    after = json.loads(args.candidate.read_text())
    matching = all(before.get(key) == after.get(key) for key in ['dataset_sha256','model','judge_model','ragas_version','metric_contract','judge_context_contract','judge_contexts_sha256'])
    def complete(report):
        expected = report['expected_cases']
        generated = [g['id'] for g in report['generations']]
        scored = [c['id'] for c in report['cases']]
        return (report.get('status') == 'tested' and report.get('acceptance') == 'passed'
                and report.get('scored_cases') == expected
                and len(generated) == len(set(generated)) == expected
                and len(scored) == len(set(scored)) == expected
                and set(generated) == set(scored))
    coverage = complete(before) and complete(after)
    def rows(report, metric):
        cases = {c['id']:c for c in report['cases']}
        results = []
        for generation in report['generations']:
            score = cases.get(generation['id'], {}).get('metrics', {}).get(metric, {})
            results.append({'id':generation['id'], 'family':generation['family'],
                'score':score.get('value') if score.get('status')=='measured' and score.get('source')=='ragas' else None,
                'checks_passed':generation.get('checks',{}).get('passed',False)})
        return results
    comparisons = {name:compare_runs(rows(before,name),rows(after,name))
                   for name in ['faithfulness','sql_factual_faithfulness']}
    result = {'matching_contracts_and_data':matching,'baseline':str(args.baseline),'candidate':str(args.candidate),
              'comparisons':comparisons,'complete_coverage':coverage,'automatic_promotion':False,'human_review':'pending',
              'baseline_expected_cases':before['expected_cases'],'candidate_expected_cases':after['expected_cases'],
              'boundary':'Same synthetic frozen evidence and judge contracts. Case bootstrap excludes repeated-judge variance. No overall accuracy claim.'}
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'matching':matching,'metrics':{k:{n:v[n] for n in ['mean_delta','delta_ci95','improved','regressed','paired_score_gate_passed']} for k,v in comparisons.items()}}))
    return 0 if matching and coverage and comparisons['faithfulness']['paired_score_gate_passed'] and comparisons['sql_factual_faithfulness']['mean_delta'] is not None and comparisons['sql_factual_faithfulness']['mean_delta'] >= 0 else 3


if __name__=='__main__':
    raise SystemExit(main())
