"""Bounded, resumable frozen-evidence report generation and Ragas evaluation."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retail.faithfulness_experiments import validate_suite, check_answer
from retail.experiment_tracking import digest
from retail.ragas_evaluation import summarize
from retail.security import safe_output
from scripts.evaluate_review_prompts import generation_config, generation_model_name, provider_ready


def write(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--prompt', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--env-file', type=Path, default=Path('.env.live'))
    parser.add_argument('--limit', type=int, default=40)
    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--max-seconds', type=int, default=1800)
    parser.add_argument('--max-calls-per-batch', type=int, default=48)
    parser.add_argument('--allow-test', action='store_true', help='Explicit sealed-test execution; never use for tuning.')
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    if not args.live:
        print(json.dumps({'status': 'untested', 'reason': 'Live calls not requested; no settings or inputs read.'}))
        return 0
    try:
        if not 1 <= args.limit <= 80 or not 1 <= args.batch_size <= 8 or not 60 <= args.max_seconds <= 3600 or not 1 <= args.max_calls_per_batch <= 96:
            raise ValueError('Bounds invalid.')
        all_cases = validate_suite(json.loads(args.cases.read_text()))
        cases = all_cases[:args.limit]
        selected_ids = {c['id'] for c in cases}
        selected_families = {c['family'] for c in cases}
        if any(c['family'] in selected_families and c['id'] not in selected_ids for c in all_cases):
            raise ValueError('Limit must not cut a task family.')
        if any(c['split'] == 'test' for c in cases) and not args.allow_test:
            raise ValueError('Sealed test requires --allow-test.')
        prompt = args.prompt.read_text()
        if not 1 <= len(prompt) <= 24000:
            raise ValueError('Invalid prompt size.')
        from retail.config import Settings
        cfg = Settings(_env_file=args.env_file)
        if not provider_ready(cfg):
            raise ValueError('Provider configuration missing.')
    except (ValueError, OSError):
        parser.error('Invalid inputs, split authorization, limits or provider configuration.')
    from scripts.evaluate_ragas import live
    import retail.deepinfra as provider
    model = generation_model_name(cfg)
    cfg = generation_config(cfg)
    judge_model = model
    identity = {'dataset_sha256': digest(cases), 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                'model': model, 'judge_model': judge_model, 'ragas_version': '0.4.4',
                'generation_provider': getattr(cfg, 'llm_provider', 'deepinfra'),
                'gateway_base_url': getattr(cfg, 'deepinfra_base_url', 'https://api.deepinfra.com/v1/openai'),
                'metric_contract': 'standard-faithfulness-unchanged; separate-sql-aware-v1',
                'batch_size': args.batch_size, 'max_calls_per_batch': args.max_calls_per_batch,
                'evidence_boundary': 'Synthetic frozen SQL results; review stage only. No live BigQuery or tool routing.'}
    identity_path = out / 'identity.json'
    if identity_path.exists() and json.loads(identity_path.read_text()) != identity:
        parser.error('Output belongs to a different experiment; use a new directory.')
    write(identity_path, identity)
    provider.SYSTEM = prompt  # Process-local only; running service is untouched.
    planned_batches = (len(cases)+args.batch_size-1)//args.batch_size
    print(json.dumps({'planned_generation_calls': len(cases), 'maximum_judge_calls': planned_batches*args.max_calls_per_batch,
                      'maximum_seconds_this_invocation': args.max_seconds, 'billed_calls': True}), flush=True)
    deadline = time.monotonic() + args.max_seconds
    def generate(c):
        path = out / (c['id'] + '.json')
        attempt = 1
        if path.exists():
            previous = json.loads(path.read_text())
            if previous['status'] != 'failed' or previous.get('attempt', 1) >= 2:
                return previous
            attempt = previous.get('attempt', 1) + 1
            write(out/(c['id']+f'.attempt-{attempt-1}.json'), previous)
        start = time.monotonic()
        try:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            decision, usage = provider.DeepInfraModel(cfg).decide(c['context'], min(30, remaining))
            safe_output(decision.model_dump_json())
            record = {'id': c['id'], 'family': c['family'], 'split': c['split'], 'action': decision.action,
                      'response': decision.text, 'status': 'generated' if decision.action == 'answer' else 'unexpected_action',
                      'seconds': time.monotonic()-start, 'usage': usage,
                      'checks': check_answer(c, decision.text)}
        except Exception as error:
            record = {'id': c['id'], 'family': c['family'], 'split': c['split'], 'status': 'failed',
                      'error_category': type(error).__name__, 'seconds': time.monotonic()-start}
        record['attempt'] = attempt
        write(path, record)
        return record
    judge_reports = []
    generations = []
    names = ['faithfulness', 'sql_factual_faithfulness']
    for offset in range(0, len(cases), args.batch_size):
        if time.monotonic() >= deadline:
            break
        batch = cases[offset:offset+args.batch_size]
        with ThreadPoolExecutor(max_workers=2) as pool:
            records = list(pool.map(generate, batch))
        generations.extend(records)
        samples = [{**{k: c[k] for k in ('id', 'question', 'sql_contexts', 'source')},
                    'response': r['response'], 'retrieved_contexts': []}
                   for c, r in zip(batch, records) if r['status'] == 'generated']
        judge_path = out / f'judge-{offset//args.batch_size:02}.json'
        previous = json.loads(judge_path.read_text()) if judge_path.exists() else None
        previous_cases = {c['id']:c for c in previous['cases']} if previous else {}
        pending = [s for s in samples if s['id'] not in previous_cases or any(
            previous_cases[s['id']]['metrics'].get(n,{}).get('status') != 'measured' for n in names)]
        attempt = previous.get('evaluation_attempts', 1) if previous else 0
        if pending and attempt < 2 and deadline-time.monotonic() > 5:
            if previous:
                write(out/f'judge-{offset//args.batch_size:02}.attempt-{attempt}.json', previous)
            async def bounded():
                return await asyncio.wait_for(live(pending, cfg, judge_model,
                    args.max_calls_per_batch, names, diagnostics=True), timeout=deadline-time.monotonic())
            try:
                judge_report = asyncio.run(bounded())
            except TimeoutError:
                judge_report = {'status': 'incomplete', 'cases': [], 'reason': 'Experiment deadline exhausted.',
                                'call_count_complete': False}
            if previous:
                for c in judge_report['cases']:
                    old = previous_cases.get(c['id'], {}).get('metrics', {})
                    c['metrics'] = {name: old[name] if old.get(name, {}).get('status') == 'measured' else score
                                    for name, score in c['metrics'].items()}
                    previous_cases[c['id']] = c
                judge_report['cases'] = list(previous_cases.values())
                for field in ['attempted_provider_calls', 'measured_total_tokens']:
                    judge_report[field] = (judge_report.get(field) or 0)+(previous.get(field) or 0)
            judge_report['evaluation_attempts'] = attempt+1
            write(judge_path, judge_report)
        elif previous:
            judge_report = previous
        else:
            judge_report = {'status': 'incomplete', 'cases': []}
        judge_reports.append(judge_report)
        print(json.dumps({'batch': offset//args.batch_size+1, 'generation': len(records),
                          'judge_status': judge_report['status']}), flush=True)
    scored = [c for report in judge_reports for c in report['cases']]
    expected = {c['id'] for c in cases}
    measured = {c['id'] for c in scored if all(c['metrics'].get(n, {}).get('status') == 'measured' for n in names)}
    summary = summarize(scored, names) if scored else {'status': 'untested', 'means': {n: None for n in names}}
    for c, record in zip(cases, generations):
        if record.get('status') == 'generated':
            record['checks'] = check_answer(c, record['response'])
    checks_passed = sum(r.get('checks', {}).get('passed', False) for r in generations)
    report = {**identity, **summary, 'status': 'tested' if expected == measured else 'incomplete',
              'acceptance': 'passed' if expected == measured and checks_passed == len(cases) else 'failed_or_incomplete',
              'expected_cases': len(cases), 'scored_cases': len(measured), 'missing_ids': sorted(expected-measured),
              'cases': scored, 'generations': generations,
              'checks_passed': checks_passed,
              'attempted_provider_calls': sum(r.get('attempted_provider_calls', 0) for r in judge_reports)
                  if all(r.get('call_count_complete', True) for r in judge_reports) else None,
              'confirmed_judge_call_lower_bound': sum(r.get('attempted_provider_calls', 0) for r in judge_reports),
              'measured_judge_tokens': sum(r.get('measured_total_tokens') or 0 for r in judge_reports),
              'generation_attempts': sum(r.get('attempt',1) for r in generations),
              'rechecks_disclosed': 'At most one generation recheck per failed case and one judge recheck per batch; original attempt artifacts retained.',
              'human_review': 'pending', 'cost': None}
    write(out/'results.json', report)
    write(out/'samples.json', [{**{k:c[k] for k in ('id','question','sql_contexts','source')}, 'response':r['response']}
        for c in cases for r in generations if c['id']==r['id'] and r['status']=='generated'])
    print(json.dumps({k:report[k] for k in ('status','means','scored_cases','expected_cases','checks_passed')}), flush=True)
    return 0 if report['acceptance'] == 'passed' else 3


if __name__ == '__main__':
    raise SystemExit(main())
