"""Opt-in live model learning demo; SQL always uses an isolated fixture."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from retail.config import Settings
from retail.learning_demo import run_demo
from retail.providers import model_for, embeddings_for


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Billed calls: at most 8 planner/review calls and 6 embedding calls; fixture SQL only.')
    parser.add_argument('--env-file',default='.env')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not args.live:
        report={'status':'untested','reason':'Live model not requested; no settings or providers loaded.'}
    else:
        cfg=Settings(_env_file=args.env_file,retail_mode='live')
        cfg.validate_embeddings()
        report=run_demo(cfg,model_for(cfg),'live',embeddings_for(cfg))
        report['model']=cfg.deepinfra_model if cfg.llm_provider=='deepinfra' else cfg.gemini_model
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,default=str)+'\n')
    print(json.dumps({'output':str(args.output),'model_source':report.get('model_source'),
        'before':report.get('before',{}).get('outcome'),'after':report.get('after',{}).get('outcome'),
        'after_oracle':report.get('after',{}).get('query_oracle_passed')}))


if __name__=='__main__': main()
