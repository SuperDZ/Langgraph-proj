"""Actual HTTP governance chain, persistence and cross-origin rejection."""
import json, sys, threading
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import pytest
from agentloop.core.contracts.models import Run
from agentloop.core.contracts.enums import RunPhase,RunStatus,RunType
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'frontend'))
import server
from platform_api import Platform

@pytest.mark.ac('AC-18','AC-19','AC-22','AC-53')
def test_http_retrospective_review_revoke_and_restart(tmp_path):
    bench=server.Workbench(tmp_path)
    api=Platform(bench)
    project=json.loads((server.ROOT/'src/agentloop/examples/phase1-config.json').read_text())['project_id']
    with api.services() as (store,archive,*_):
        store.put_run(Run(run_id='finished',root_run_id='finished',project_id=project,run_type=RunType.DELIVERY,phase=RunPhase.DELIVERY,status=RunStatus.COMPLETED,trigger_source='TEST',config_snapshot_id='c',baseline_versions={'commit':'c1'}))
        for kind in ('SPEC','ARCHITECTURE','TEST_EXECUTION'): archive.put(run_id='finished',kind=kind,producer='fixture',value={'kind':kind})
    class Handler(server.Handler): pass
    Handler.bench=bench;Handler.static_dir=server.ROOT/'frontend'
    http=server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{http.server_port}'
    def call(path,body=None,headers=None):
        r=Request(base+path,data=json.dumps(body).encode() if body else None,headers=headers or {})
        with urlopen(r,timeout=10) as response:return json.load(response)
    try:
        initial=call('/api/platform?run_id=finished')
        assert initial['retrospectives']==[] and initial['proposals']==[]
        body={'run_id':'finished'}
        with pytest.raises(HTTPError) as rejected:call('/api/platform/retrospect',body)
        assert rejected.value.code==403
        headers={'X-AgentLoop-CSRF':initial['csrf'],'Origin':base,'Content-Type':'application/json'}
        with pytest.raises(HTTPError):call('/api/platform/retrospect',body,{**headers,'Origin':'https://attacker.invalid'})
        result=call('/api/platform/retrospect',body,headers)
        assert call('/api/platform/retrospect',body,headers)==result
        state=call('/api/platform?run_id=finished');assert state['proposals'] and not state['memories']
        pid=state['proposals'][0]['proposal_id']
        approved=call('/api/platform/memory-review',{**body,'proposal_id':pid,'decision':'APPROVE'},headers)
        assert call('/api/platform?run_id=finished')['memories'][0]['status']=='ACTIVE'
        call('/api/platform/memory-revoke',{**body,'memory_id':approved['published_memory_id']},headers)
        # New facade and connection observe persisted governance state, parent stays complete.
        after=Platform(bench).read('finished')
        assert after['run']['status']=='COMPLETED' and after['memories'][0]['status']=='REVOKED'
    finally:
        http.shutdown();http.server_close();thread.join()
