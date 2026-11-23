"""Explicit supplemental generation after the original two-attempt cap.
Original run files are never mutated. Supports only original failed generations.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path.cwd()))
from retail.config import Settings
from retail.security import safe_output
from retail.faithfulness_experiments import check_answer
from scripts.evaluate_review_prompts import generation_config
from scripts.evaluate_ragas import live
import retail.deepinfra as provider

root=Path('evaluation/wikivibe-flash-iteration-2026-11-23')
variant=sys.argv[1]
assert variant in {'baseline','candidate-v2'}
cases=json.loads(Path('evaluation/faithfulness-v2/validation.json').read_text())
original=root/(variant+'-validation')
out=root/(variant+'-validation-supplement')
out.mkdir(exist_ok=True)
assert not (out/'generation.json').exists(), 'Single supplemental attempt only'
failed=[c for c in cases if json.loads((original/(c['id']+'.json')).read_text())['status']=='failed']
assert len(failed)==1
c=failed[0]
cfg=Settings(_env_file='.env.providers')
assert cfg.llm_provider=='openai_compatible' and cfg.openai_compatible_model=='gemini-3.8-flash'
provider.SYSTEM=(root/(variant+'.txt')).read_text()
report={'id':c['id'],'family':c['family'],'split':c['split'],'original_run':str(original),'supplemental_attempt':1,'generation_timeout_seconds':60,'prompt_sha256':hashlib.sha256(provider.SYSTEM.encode()).hexdigest(),'boundary':'Additional attempt after original run exhausted its preregistered generation cap. Not an original-run success.'}
try:
 d,usage=provider.DeepInfraModel(generation_config(cfg)).decide(c['context'],60)
 safe_output(d.model_dump_json())
 report.update(action=d.action,response=d.text,status='generated' if d.action=='answer' else 'unexpected_action',usage=usage,checks=check_answer(c,d.text))
except Exception as exc:
 report.update(status='failed',error_category=type(exc).__name__)
(out/'generation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report.get(k) for k in ['id','status','checks']}),flush=True)
if report['status']!='generated':sys.exit(3)
sample={**{k:c[k] for k in ['id','question','sql_contexts','source']},'response':d.text}
(out/'samples.json').write_text(json.dumps([sample],indent=2)+'\n')
async def judge():
 return await asyncio.wait_for(live([sample],cfg,'gemini-3.8-flash',4,['faithfulness','sql_factual_faithfulness'],diagnostics=True),timeout=250)
r=asyncio.run(judge())
(out/'judge.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({'status':r['status'],'means':r.get('means')}),flush=True)
