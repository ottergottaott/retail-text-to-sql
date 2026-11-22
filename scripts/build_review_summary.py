"""Build the offline review page and metrics from recorded evidence; no provider calls."""
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sources = {}


def read(name):
    path = ROOT / 'evaluation' / name
    sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return json.loads(path.read_text())


def main():
    regression = read('regression-2026-11-22.json')
    business = read('live-business-pro-final-2026-11-21.json')
    faith = read('faithfulness-pro-live-results-2026-11-21.json')
    retrieval = read('retrieval-gate-2026-11-21/english-results.json')
    challenge = read('retrieval-gate-2026-11-21/challenge-results.json')
    cli = read('cli-live-2026-11-22.json')
    browser = read('browser-acceptance-2026-11-22.json')
    prompt = read('prompt-iteration-3-2026-11-22/results.json')
    audit = read('deepseek-final-metrics-audit-2026-11-22.json')
    report_audit = read('deepseek-browser-report-review-2026-11-22.json')
    installation = read('archive-installation-2026-11-22.json')
    metrics = {
        'date': '2026-11-22', 'serving_prompt': 'retail-v8', 'human_review': 'pending',
        'regression': {k: regression[k] for k in ('passed', 'total', 'seconds')},
        'archive_installation': installation,
        'live_business': {'serving_prompt': 'retail-v7', 'selected_reports': len(business['cases']),
                          'query_oracle_passed': sum(c['query_oracle_passed'] for c in business['cases']),
                          'attempts': business['attempts']},
        'live_judge': {'means': faith['means'], 'coverage': faith['coverage'],
                       'judge': faith['judge_model'], 'ragas_version': faith['ragas_version'],
                       'calls': faith['attempted_provider_calls'], 'tokens': faith['measured_total_tokens'],
                       'cost': faith['cost'], 'boundary': 'Different judge contracts; neither is overall answer accuracy.'},
        'english_retrieval': {k: retrieval[k]['metrics'] for k in ('baseline', 'candidate')},
        'english_challenge': {k: challenge[k]['metrics'] for k in ('baseline', 'candidate')},
        'retrieval_boundary': 'Small synthetic sets, cached live Qwen vectors. Expanded cases previously exposed; challenge evaluated without retuning. Replay latency excludes providers.',
        'cli': {'turns': len(cli['cases']), 'checks': cli['checks']},
        'browser': {'passed': sum(c['status'] == 'passed' for c in browser['checks']),
                    'untested': sum(c['status'] == 'untested' for c in browser['checks']),
                    'checks': browser['checks'], 'boundary': browser['evidence_boundary']},
        'targeted_save_prompt': {k: prompt['variants'][k]['validation'] for k in ('baseline', 'candidate')},
        'prompt_boundary': 'Four synthetic validation cases per variant, one repetition; save semantics only. Broad live business set predates retail-v8.',
        'deepseek_review': {'metrics_blockers': audit['blocking_inconsistencies'], 'new_report_verdict': report_audit['verdict'],
                            'boundary': 'Independent AI text/evidence critique; no SQL recomputation or visual review.'},
        'remaining': ['Human report review', 'Fresh installation on another machine', 'Optional live Langfuse ingestion'],
        'source_sha256': sources,
    }
    (ROOT / 'evaluation/submission-metrics-2026-11-22.json').write_text(json.dumps(metrics, indent=2) + '\n')
    rows = [
        ('Regression', f"{regression['passed']}/{regression['total']}", 'Controlled tests; rerun on 22 November.', 'regression-2026-11-22.json'),
        ('Live SQL / save / structure', f"{len(business['cases'])} selected reports", '11/12 initial requests passed; 1/1 recheck passed. 13 requests total. retail-v7.', 'live-business-pro-final-2026-11-21.json'),
        ('Live report faithfulness', f"{faith['means']['faithfulness']:.3f} / {faith['means']['sql_factual_faithfulness']:.3f}", 'Standard Ragas / custom SQL-aware contract. 12 reports each; LLM judge, not answer accuracy.', 'faithfulness-pro-live-results-2026-11-21.json'),
        ('English retrieval', f"Recall@2 {retrieval['candidate']['metrics']['by_k']['2']['recall']:.2f}", '40 positive cases; negative matches 8/10 → 0/10. New challenge: recall 1.00, negatives 0/8. Synthetic, cached live embeddings.', 'retrieval-gate-2026-11-21/english-results.json'),
        ('Browser / CLI', f"{metrics['browser']['passed']}/{len(browser['checks'])} browser checks passed; {metrics['browser']['untested']} untested. {len(cli['cases'])} CLI turns.", 'New live report, Artifacts, SQL, library, preferences, feedback, confirmed deletion and reopening after chat deletion. Limits below.', 'browser-acceptance-2026-11-22.json'),
    ]
    table = ''.join(f'<tr><th>{html.escape(a)}</th><td>{html.escape(b)}</td><td>{html.escape(c)} <a href="../evaluation/{d}">Evidence ↗</a></td></tr>' for a,b,c,d in rows)
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Retail Intelligence · Review pack</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f0f5f4;color:#173238;font:16px/1.55 system-ui,sans-serif}main{max-width:1080px;margin:auto;padding:48px 24px}header{background:#143e46;color:#fff;padding:40px;border-radius:24px}small{letter-spacing:.12em;text-transform:uppercase;color:#b4dbd3}h1{font-size:clamp(32px,6vw,56px);line-height:1.1;margin:16px 0}header p{max-width:700px;color:#daebea}nav{display:flex;flex-wrap:wrap;gap:12px;margin-top:26px}nav a{background:#e3f6f1;color:#153c41;border-radius:10px;padding:10px 16px;text-decoration:none;font-weight:650}section{margin-top:28px;background:white;border:1px solid #d8e3df;border-radius:20px;padding:28px}h2{font-size:23px;margin:0 0 16px}table{border-collapse:collapse;width:100%}th,td{padding:17px 10px;border-bottom:1px solid #e6ece9;text-align:left;vertical-align:top}th{width:23%;font-weight:600}td:nth-child(2){width:24%;font-weight:650;color:#08776d}td:last-child{font-size:14px;color:#50676b}a{color:#08776d}details{margin-top:16px}summary{cursor:pointer;font-weight:600}.note{font-size:14px;color:#50676b}footer{margin:24px 4px;color:#50676b;font-size:13px}@media(max-width:650px){main{padding:18px 12px}header,section{padding:24px 18px}table,tbody,tr,th,td{display:block;width:100%!important}th{padding-bottom:0}td{padding-top:8px}td:nth-child(2){border:0}th{border:0}}</style>
<main><header><small>Technical assignment · Review pack · 22 November 2026</small><h1>Retail Intelligence</h1><p>Ask a business question. Inspect the numbers and SQL. Keep the report.</p><nav><a href="../START_HERE.md">Start the demo ↗</a><a href="technical-overview.html">Architecture ↗</a><a href="submission-evidence.md">Evidence guide ↗</a></nav></header>
<section><h2>What is implemented</h2><p>Open WebUI and CLI share a FastAPI/LangGraph backend. Gemini plans analysis and reviews reports. BigQuery execution is read-only, scoped to the user and bounded by time and scan budgets. Hybrid retrieval supplies versioned Golden Trios.</p><p>Reports have tables, supported charts and inspectable SQL. They survive chat deletion. Preferences persist across chats; feedback enters analyst review before shared knowledge changes.</p></section>
<section><h2>Recorded checks</h2><table><tbody>''' + table + '''</tbody></table><p class="note">These measurements cover different contracts and datasets. They cannot be combined into one accuracy score. <a href="../evaluation/submission-metrics-2026-11-22.json">Full metrics and source hashes ↗</a></p></section>
<section><h2>What to review</h2><p>Try the five-minute walkthrough in START_HERE, inspect a saved report and its query evidence, then leave feedback or change your preferred format.</p><details><summary>Limits and open checks</summary><p>Human report review, installation on another machine and optional live Langfuse delivery remain unverified. Browser checks used local headless Chrome; native fullscreen and downloaded-file persistence were not established. Cross-user and error paths have controlled API/CLI coverage, not live browser fault injection.</p><p>Standard live faithfulness remains limited. The promoted retail-v8 change improves deferred-save wording on a small synthetic set; broad live report quality has not been remeasured for v8. DeepSeek reviewed metrics and the new live report against recorded evidence; it did not recompute SQL or inspect the UI.</p><p>Golden Trios are synthetic and need analyst review. Preferences are explicit; shared improvements require approval. No autonomous model training is claimed.</p></details></section>
<footer>Credential-free fixture demo included. Live Gemini/BigQuery calls require your credentials and may incur charges. No secrets are included in the review archive.</footer></main></html>'''
    (ROOT / 'docs/review-summary.html').write_text(page)
    print('Built docs/review-summary.html and evaluation/submission-metrics-2026-11-22.json')


if __name__ == '__main__':
    main()
