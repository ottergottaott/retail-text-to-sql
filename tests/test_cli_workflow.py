"""Actual CLI subprocess against real HTTP/SSE API and isolated fixture SQL."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def cli_server(tmp_path_factory):
    tmp=tmp_path_factory.mktemp('cli-state')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    code='''
import sys, uvicorn
from retail.api import create_app
from retail.config import Settings
config=Settings(_env_file=None,retail_mode='fixture',embedding_provider='none',
 database_url='sqlite:///'+sys.argv[1],log_path=sys.argv[2],
 api_tokens_json='{"alice-cli":"alice","bob-cli":"bob"}',adapter_secret='',
 langfuse_public_key='',langfuse_secret_key='')
uvicorn.run(create_app(config),host='127.0.0.1',port=int(sys.argv[3]),log_level='critical')
'''
    process=subprocess.Popen([sys.executable,'-c',code,str(tmp/'state.db'),str(tmp/'events.jsonl'),str(port)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    url=f'http://127.0.0.1:{port}'
    try:
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            if process.poll() is not None:pytest.fail('Isolated API process exited during startup')
            try:
                if httpx.get(url+'/health',timeout=.5).status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(.05)
        else:pytest.fail('Isolated API did not become ready')
        yield url
    finally:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill();process.wait(timeout=5)


def run_cli(url,*args,token='alice-cli',input=None):
    env={**os.environ,'RETAIL_API_TOKEN':token}
    return subprocess.run([sys.executable,'-m','retail.cli','--url',url,*args],cwd=ROOT,env=env,input=input,capture_output=True,text=True,timeout=30)


def test_cli_json_progress_save_reopen_and_cross_user(cli_server):
    result=run_cli(cli_server,'--json','--once','Create and save a monthly revenue report')
    assert result.returncode==0,result.stderr
    first=json.loads(result.stdout)
    assert first['outcome']=='succeeded' and first['completed_analysis']
    assert first['evidence'] and first['mode']=='fixture'
    assert '[query:' in result.stderr and 'Conversation:' in result.stderr
    rid=first['management']['report_id']
    assert rid in first['answer']
    listed=json.loads(run_cli(cli_server,'--json','--once','list reports').stdout)
    assert listed['conversation_id']!=first['conversation_id']
    assert rid in listed['answer']
    opened=run_cli(cli_server,'--json','--conversation',first['conversation_id'],'--once','open report '+rid)
    assert opened.returncode==0
    assert json.loads(opened.stdout)['conversation_id']==first['conversation_id']
    assert '100.0' in json.loads(opened.stdout)['answer']
    bob=json.loads(run_cli(cli_server,'--json','--once','open report '+rid,token='bob-cli').stdout)
    assert bob['outcome']=='denied' and 'not accessible' in bob['answer']
    assert '100.0' not in bob['answer']


def test_cli_interactive_reuses_conversation(cli_server):
    result=run_cli(cli_server,input='monthly revenue\nlist reports\n/quit\n')
    assert result.returncode==0,result.stderr
    conversations=[line.split(' |')[0] for line in result.stderr.splitlines() if line.startswith('Conversation:')]
    assert len(conversations)==2 and conversations[0]==conversations[1]
    assert '100.0' in result.stdout and 'Retail chat.' in result.stdout


def test_cli_rejects_invalid_auth_without_traceback(cli_server):
    result=run_cli(cli_server,'--once','list reports',token='invalid-controlled-token')
    assert result.returncode==1
    assert 'Request rejected: 403' in result.stderr
    assert not result.stdout and 'Traceback' not in result.stderr


def test_cli_requires_token_before_call(cli_server):
    result=run_cli(cli_server,'--once','list reports',token='')
    assert result.returncode==2 and 'Set RETAIL_API_TOKEN' in result.stderr
    assert 'Traceback' not in result.stderr


def test_cli_connection_failure_is_clean():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        # Bound but deliberately not listening: no unrelated service can claim it.
        result=run_cli(f'http://127.0.0.1:{port}','--once','list reports')
    assert result.returncode==1 and 'API unavailable or timed out' in result.stderr
    assert 'Traceback' not in result.stderr
