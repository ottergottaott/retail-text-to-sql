"""Install report Functions using an existing local admin login. Never prints secrets."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse
import httpx


def install(client, root):
    pipe_id = 'retail_assessment_pipe'
    valves = client.get(f'/api/v1/functions/id/{pipe_id}/valves'); valves.raise_for_status()
    private = valves.json()
    existing = client.get('/api/v1/functions/list'); existing.raise_for_status()
    present = {item['id'] for item in existing.json()}
    for fid, name, filename in [
        ('retail_reports_api', 'Retail Reports API', 'openwebui_reports_event.py'),
        ('retail_reports_action', 'My reports', 'openwebui_reports_action.py'),
        ('retail_learning_api', 'Retail Learning API', 'openwebui_learning_event.py'),
        ('retail_feedback_action', 'Give feedback', 'openwebui_feedback_action.py'),
        ('retail_preferences_action', 'My preferences', 'openwebui_preferences_action.py')]:
        form = {'id':fid,'name':name,'content':(root/'integrations'/filename).read_text(),
                'meta':{'description':'Authenticated Retail Reports library'}}
        response = client.post(f'/api/v1/functions/id/{fid}/update' if fid in present else '/api/v1/functions/create',json=form)
        response.raise_for_status()
        if fid in {'retail_reports_api','retail_learning_api'}:
            r=client.post(f'/api/v1/functions/id/{fid}/valves/update',json={
                'API_URL':private['API_URL'],'ADAPTER_SECRET':private['ADAPTER_SECRET']})
            r.raise_for_status()
        if not response.json()['is_active']:
            r=client.post(f'/api/v1/functions/id/{fid}/toggle');r.raise_for_status()
    # Attach Action only to Retail Intelligence; preserve workspace settings/grants.
    r=client.get('/api/v1/models/model',params={'id':pipe_id})
    if r.status_code==200 and r.json():
        model=r.json()
        model['meta']={**(model.get('meta') or {}),'actionIds':sorted(set((model.get('meta') or {}).get('actionIds',[])+['retail_reports_action','retail_feedback_action','retail_preferences_action']))}
        r=client.post('/api/v1/models/model/update',json=model)
    else:
        r=client.post('/api/v1/models/create',json={'id':pipe_id,'name':'Retail Intelligence',
            'meta':{'actionIds':['retail_reports_action','retail_feedback_action','retail_preferences_action']},'params':{}})
    r.raise_for_status()
    print(json.dumps({'installed':True,'action_scope':pipe_id,'restart_webui_required':True}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--webui-url',default='http://127.0.0.1:3000')
    args=parser.parse_args()
    if urlparse(args.webui_url).hostname not in {'localhost','127.0.0.1'}:
        parser.error('Installer is restricted to local WebUI.')
    token=os.environ.get('WEBUI_ADMIN_TOKEN')
    if not token:
        parser.error('Provide WEBUI_ADMIN_TOKEN in the process environment.')
    with httpx.Client(base_url=args.webui_url,headers={'Authorization':'Bearer '+token},timeout=60) as client:
        install(client,Path(__file__).resolve().parents[1])


if __name__=='__main__': main()
