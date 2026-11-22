"""Build a self-contained human review page from recorded acceptance evidence."""
import argparse
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(directory):
    load = lambda name: json.loads((directory / name).read_text())
    business_file = 'live-business-pro-final-2026-11-21.json'
    business = load(business_file)
    faithfulness = load('faithfulness-summary-2026-11-21.json')
    webui = load('webui-live-grounded-2026-11-21.json')
    dialogue = load('live-dialogue-security-2026-11-21.json')
    ragas = load('ragas-results-2026-11-21.json')
    rechecks = load('live-business-grounded-v8-rechecks-2026-11-21.json')
    review = load('deepseek-report-review-2026-11-21.json')
    live_review = load('deepseek-live-business-review-2026-11-21.json')
    disposition = load('review-disposition-2026-11-21.json')
    fault = load('fault-observability-checks-2026-11-21.json')
    checks = [dict(name=c['id'], status=c['status'], evidence=business_file) for c in business['cases']]
    checks.extend(dict(name=c['name'], status=c['status'], evidence='live-dialogue-security-2026-11-21.json') for c in dialogue['checks'])
    checks.extend(dict(name=c['name'], status=c['status'], evidence='fault-observability-checks-2026-11-21.json') for c in fault['checks'])
    checks.extend([
        dict(name='Isolated installation and regression suite', status='passed', note='Frozen lock into a fresh virtual environment; 159 tests at that historical installation check. Current checkout regression: 167 tests. Installed wheel evaluator passed 21 fixture cases with explicit case paths. Same host, not a clean-machine test.'),
        dict(name='Live Open WebUI browser workflow', status=webui['status'], note='Visible progress, rendered table, save and opening the same report from a new chat. Docker recovered; 13 unrelated containers stopped without deleting volumes.'),
        dict(name='Langfuse ingestion/read-back', status='untested', note='No running configured Langfuse service; local metadata audit passed.'),
        dict(name='Clean-machine installation', status='untested', note='Existing host setup was used.'),
        dict(name='Human report and UX acceptance', status='untested', note='Pending reviewer decision; automated checks do not imply acceptance.')])
    ledger = {'date':'2026-11-21', 'overall_status':'incomplete', 'checks':checks,
              'historical_failures_preserved':True,
              'preference_regression':'Fixed by requiring explicit format/depth; final live regression passed.',
              'evidence_boundary':'See per-case SQL/save/structure checks and separate faithfulness scores. Browser verified; Langfuse, clean-machine and human acceptance remain open.'}
    (directory/'acceptance-status-2026-11-21.json').write_text(json.dumps(ledger,indent=2)+'\n')
    esc = lambda value: html.escape(str(value))
    def table(rows):
        if not rows: return '<p>No rows</p>'
        columns = list(dict.fromkeys(k for row in rows for k in row))
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(k)+'</th>' for k in columns)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(row.get(k,''))+'</td>' for k in columns)+'</tr>' for row in rows)+'</tbody></table></div>'
    def code(value): return '<pre>'+esc(value)+'</pre>'
    parts = []
    for case in business['cases']:
        response=case['response']; rid=(response.get('management') or {}).get('report_id','')
        evidence=''.join('<details><summary>Logical SQL · executor binds product scope · '+esc(e.get('job_id',''))+'</summary>'+code(e['sql'])+'</details>'+table(e['rows']) for e in response['evidence'])
        parts.append('<article id="'+esc(case['id'])+'"><h2>'+esc(case['id'])+' <span class="pass">'+esc(case['status'])+'</span></h2><p>'+esc(case['question'])+'</p><p class="meta">Report '+esc(rid)+' · '+esc(round(case['seconds'],1))+' seconds</p><h3>Agent answer — exact recorded text</h3>'+code(response['answer'])+'<h3>Agent query evidence</h3>'+evidence+'<details><summary>Independent physical SQL and reference rows</summary>'+code(case['reference_sql'])+table(case['reference_rows'])+'<p>Reference job '+esc(case['reference_job_id'])+'</p></details><label>Your verdict <select data-review="'+esc(case['id'])+'"><option value="pending">Pending</option><option value="accepted">Accepted</option><option value="changes">Needs changes</option></select></label> <textarea data-note="'+esc(case['id'])+'" placeholder="Notes on definition, numbers, limitations, recommendations"></textarea></article>')
    metrics=[dict(metric=k,ragas_mean=v,combined_with_empty_context_rule=ragas['combined_means'][k],**ragas['coverage'][k]) for k,v in ragas['means'].items()]
    body='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Retail assistant — acceptance review</title><style>
:root{color-scheme:light dark;font-family:system-ui;background:#101622;color:#e2e8f0}body{max-width:1180px;margin:30px auto;padding:0 20px}h1{font-size:32px}h2{font-size:22px}h3{font-size:16px;color:#a4c9ef}article,section{background:#192334;border:1px solid #354457;padding:22px;margin:20px 0;border-radius:12px}.meta{color:#a9b8cb;font-size:13px}.pass{color:#79d8ad;font-size:14px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#111a28;padding:16px;border-radius:6px;font:14px/1.6 ui-monospace,monospace}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;border-bottom:1px solid #354457;padding:9px;vertical-align:top}summary{cursor:pointer;padding:10px 0}select,textarea,button{background:#101a2b;color:#e2e8f0;border:1px solid #57708c;padding:10px;border-radius:6px}textarea{display:block;width:95%;min-height:70px;margin-top:10px}a{color:#8cc4ff}nav{display:flex;flex-wrap:wrap;gap:12px}button{cursor:pointer}strong{color:#ffd194}</style>
<h1>Retail assistant · morning review</h1><p>Recorded evidence · 21 November 2026. These reports use real Gemini via DeepInfra and BigQuery. Product scope: 1 and 2. Reports are saved independently of chat.</p>
<section><h2>Readiness</h2><p><strong>Not fully accepted:</strong> Langfuse ingestion, clean-machine installation and human acceptance remain open. Docker recovered; live Open WebUI progress, table, save and new-chat opening passed. Unneeded containers were stopped; no volumes were deleted. Backend: <a href="http://127.0.0.1:8001/health">local health</a>. This page is a review artifact, not an Open WebUI acceptance run.</p><p>Review each answer against its actual rows and independent reference. Check scope, grain, status/window, small samples, unsupported causes and action items. Verdicts below stay in this browser; export to share them. They do not change saved application reports.</p><button id="export">Export my review</button></section>'''
    body+='<nav>'+''.join('<a href="#'+esc(c['id'])+'">'+esc(c['id'])+'</a>' for c in business['cases'])+'</nav>'
    body+='<section><h2>Faithfulness repair and separate evaluation contracts</h2>'+table(faithfulness['comparison'])+'<h3>Fresh live business gates</h3>'+code(json.dumps(faithfulness['business'],indent=2))+'<h3>Earlier Flash report metrics</h3>'+code(json.dumps(faithfulness['fresh'],indent=2))+'<h3>Final Flash planner / Pro reviewer</h3>'+code(json.dumps(faithfulness['final_pro'],indent=2))+'<h3>SQL-aware variant (different NLI contract; not standard Ragas)</h3>'+code(json.dumps(faithfulness['sql_aware'],indent=2))+table(faithfulness['sql_calibration'])+'<h3>Known report-quality flags</h3>'+code(json.dumps(faithfulness['known_flags'],indent=2))+'<h3>Judge calibration traps</h3>'+table(faithfulness['calibration'])+'<p>'+esc(' '.join(faithfulness['limitations']))+'</p><p>Failed v5/v6 runs remain in the evaluation directory. The displayed v9 run uses the v7 prompt, required-answer schema, Flash planning and Pro final review. Earlier Flash metrics above use distinct recorded reports. Saved reports are immutable historical evidence; they are not rewritten after prompt changes.</p></section>'
    body+='<section><h2>Historical Ragas advisory evaluation · '+esc(ragas['status'])+'</h2>'+table(metrics)+'<p>4 reports (1 live + 3 fixture), 8 retrieval examples. Same Gemini judge model family as the application; self-judge bias. Faithfulness uses SQL facts. Retrieval scores use Golden reference methodology. Small synthetic sets are not release thresholds. Empty-context rule zeros are excluded from ragas_mean.</p><p>Faithfulness 0.50 requires review: recommendations and caveats are often not entailed by SQL facts. Do not interpret this as an accuracy pass.</p><p><a href="ragas-faithfulness-diagnostics-2026-11-21.json">Per-statement diagnostic and supported/contradicted calibration</a></p></section>'
    body+='<section><h2>DeepSeek review</h2><p>'+esc(review['summary'])+'</p><p>11 reports = 9 fixture variants and 2 live variants; not an independent review of these 12 business cases. Numeric checks use embedded query rows; independent SQL oracles are recorded separately below.</p><details><summary>Full review</summary>'+code(json.dumps(review,ensure_ascii=False,indent=2))+'</details></section>'
    body+='<section><h2>Historical DeepSeek review of earlier 12 business cases</h2><p>The reviewer found an empty realized-price report mislabeled successful. The guard and acceptance harness were fixed; a new real query/report recheck passed the numeric and minimum-structure checks. The original record remains archived. Review findings below refer to the original run. Model-generated action items still require human review.</p><details><summary>Full twelve-case review</summary>'+code(json.dumps(live_review,ensure_ascii=False,indent=2))+'</details><details open><summary>Finding dispositions and recheck caveats</summary>'+code(json.dumps(disposition,ensure_ascii=False,indent=2))+'</details></section>'
    body+='<section><h2>Acceptance ledger</h2>'+table(checks)+'<p>Two earlier preference failures are preserved. The final live regression passed after schema correction. Case passed means numeric oracle, save and minimum report structure; human quality acceptance remains pending.</p></section>'+''.join(parts)
    body+='<section><h2>Focused Flash rechecks — numeric pass is not report-quality acceptance</h2><p>The no-discounts claim recurred in realized-price. This remains a quality failure and is retained below; the system does not claim every report is faithful.</p>'+''.join('<h3>'+esc(c['id'])+'</h3>'+code(c['response']['answer']) for c in rechecks['cases'])+'</section>'
    body+='''<script>
const key='retail-human-review-2026-11-21';let state={};try{state=JSON.parse(localStorage.getItem(key)||'{}')}catch(e){};
document.querySelectorAll('[data-review],[data-note]').forEach(el=>{const id=el.dataset.review||el.dataset.note;const field=el.dataset.review?'verdict':'note';el.value=state[id]?.[field]||(field==='verdict'?'pending':'');el.addEventListener('change',()=>{state[id]={...state[id],[field]:el.value};try{localStorage.setItem(key,JSON.stringify(state))}catch(e){}})});
document.getElementById('export').addEventListener('click',()=>{const blob=new Blob([JSON.stringify({reviewed_at:new Date().toISOString(),source:'live-business-pro-final-2026-11-21.json',human_reviews:state},null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='retail-human-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)});
</script></html>'''
    return body


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=ROOT/'evaluation')
    args=parser.parse_args()
    target=args.directory/'morning-review-2026-11-21.html'
    target.write_text(build(args.directory))
    print(target)
