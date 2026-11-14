"""Per-role isolation, encrypted storage, safe HTTP credential contracts."""
import json
import os
from pathlib import Path
import sys
import threading
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'frontend'))
from agent_settings import edit_agent, select_run_models
from credentials import CredentialVault
import server
from platform_api import Platform
from agentloop.core.contracts.phase2 import RuntimeConfig
from agentloop.core.runtime.configuration import effective_config,resolve_secret


def settings(tmp_path):
    bench=server.Workbench(tmp_path)
    api=Platform(bench)
    config=api.default_config()
    return bench,api,config


def edit_body(config,role,**overrides):
    e=effective_config(RuntimeConfig.model_validate(config),role)
    return {'role':role,'profile_id':e.primary,'profile':e.models[e.primary].model_dump(mode='json'),
            'fallbacks':[],'token_budget':210000,'cost_budget':500000,'max_steps':25,'concurrency':1,**overrides}


def test_edit_agent_never_changes_shared_model_or_sibling(tmp_path):
    _,_,config=settings(tmp_path)
    profile={**config['models']['primary'],'model':'my-model','temperature':.35,'max_output_tokens':3072}
    changed,effective=edit_agent(config,edit_body(config,'product-analyst',profile=profile))
    assert RuntimeConfig.model_validate(changed).models['primary']==RuntimeConfig.model_validate(config).models['primary']
    before=effective_config(RuntimeConfig.model_validate(config),'product-leader')
    after=effective_config(RuntimeConfig.model_validate(changed),'product-leader')
    assert before.models[before.primary]==after.models[after.primary]
    assert effective['models'][effective['primary']]['max_output_tokens']==3072
    assert effective['token_budget']==210000
    restored,effective=edit_agent(changed,{'role':'product-analyst','inherit':True})
    assert effective['primary']=='primary' and restored['roles']['product-analyst']['agent'].get('primary') is None


def test_validation_rejects_incompatible_thinking_and_denied_endpoint(tmp_path):
    _,_,config=settings(tmp_path)
    bad={**config['models']['primary'],'thinking':'enabled','temperature':1}
    with pytest.raises(ValueError):edit_agent(config,edit_body(config,'backend',profile=bad))
    bad={**config['models']['primary'],'endpoint':'https://unapproved.example'}
    with pytest.raises(ValueError):edit_agent(config,edit_body(config,'backend',profile=bad))
    with pytest.raises(ValueError):edit_agent(config,{'role':'unknown'})
    with pytest.raises(ValueError):edit_agent(config,edit_body(config,'backend',fallbacks=['agent-backend']))


@pytest.fixture
def encrypted_credentials(tmp_path, monkeypatch):
    if sys.platform == 'linux':
        from cryptography.fernet import Fernet

        key_file = tmp_path / 'vault.key'
        key_file.write_bytes(Fernet.generate_key())
        key_file.chmod(0o600)
        monkeypatch.setenv('AGENTLOOP_CREDENTIAL_KEY_FILE', str(key_file))
    elif os.name != 'nt':
        pytest.skip('Encrypted persistence requires Windows or Linux')


def test_encrypted_persistence_rotation_delete_and_no_plaintext(tmp_path,monkeypatch,encrypted_credentials):
    name='AGENTLOOP_TEST_API_KEY';ref='env:'+name
    monkeypatch.delenv(name,raising=False)
    vault=CredentialVault(tmp_path/'credentials.dpapi')
    secret='synthetic-key-only-for-vault-test'
    status=vault.update(ref,secret)
    assert status['configured'] and secret not in json.dumps(status)
    assert secret.encode() not in vault.path.read_bytes()
    if sys.platform == 'linux':
        assert vault.path.suffix == '.fernet'
        assert vault.path.stat().st_mode & 0o077 == 0
    assert resolve_secret(ref)==secret
    monkeypatch.delenv(name)
    reopened=CredentialVault(vault.path)
    assert resolve_secret(ref)==secret
    reopened.update(ref,'rotated-synthetic-test-key')
    assert resolve_secret(ref)=='rotated-synthetic-test-key'
    reopened.update(ref,remove=True)
    assert not reopened.status([ref])[0]['configured']
    with pytest.raises(ValueError):vault.update('env:PATH','not-allowed')
    with pytest.raises(ValueError):vault.update(ref,'bad\nkey')


def test_role_changes_merge_and_do_not_mutate_run_snapshot(tmp_path):
    bench,api,config=settings(tmp_path)
    with api.services() as (store,*_):store.runtime_put('console_run_config','existing-run',config)
    api.act('agent-config-save',{'run_id':'console-config',**edit_body(config,'backend')})
    api.act('agent-config-save',{'run_id':'console-config',**edit_body(config,'frontend',token_budget=12345)})
    saved=api.read()['config']
    assert saved['roles']['backend']['agent']['token_budget']==210000
    assert saved['roles']['frontend']['agent']['token_budget']==12345
    with api.services() as (store,*_):assert store.runtime_get('console_run_config','existing-run')==config


def test_http_secrets_never_return_or_enter_sqlite_and_csrf_is_required(tmp_path,monkeypatch,encrypted_credentials):
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    bench,api,config=settings(tmp_path)
    class Handler(server.Handler):pass
    Handler.bench=bench;Handler.static_dir=server.ROOT/'frontend'
    http=server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{http.server_port}'
    def call(path,body=None,headers=None):
        with urlopen(Request(base+path,data=json.dumps(body).encode() if body else None,headers=headers or {}),timeout=15) as r:return json.load(r)
    try:
        initial=call('/api/platform');headers={'X-AgentLoop-CSRF':initial['csrf'],'Origin':base,'Content-Type':'application/json'}
        key='synthetic-http-key-not-a-real-provider-credential'
        body={'run_id':'console-config','ref':'env:DEEPSEEK_API_KEY','value':key}
        with pytest.raises(HTTPError) as error:call('/api/platform/credential-save',body)
        assert error.value.code==403
        saved=call('/api/platform/credential-save',body,headers)
        assert saved['source']=='local_encrypted' and key not in json.dumps(saved)
        model_saved=call('/api/platform/model-profile-save',{
            'run_id':'console-config','profile_id':'primary','is_new':False,
            'profile':initial['config']['models']['primary'],'api_key':key,
        },headers)
        assert model_saved['credential']['source']=='local_encrypted' and key not in json.dumps(model_saved)
        assert key not in json.dumps(call('/api/platform'))
        with pytest.raises(HTTPError):call('/api/platform/credential-save',{**body,'ref':'env:PATH'},headers)
        for path in (tmp_path/'runs').glob('state.db*'): assert key.encode() not in path.read_bytes()
        call('/api/platform/credential-remove',{'run_id':'console-config','ref':body['ref']},headers)
        assert not call('/api/platform')['credentials'][0]['configured']
    finally:http.shutdown();http.server_close();thread.join()


def test_global_defaults_and_per_run_model_selection_are_isolated(tmp_path):
    bench,api,config=settings(tmp_path)
    result=api.act('global-config-save',{'run_id':'console-config','primary':'reasoning',
        'token_budget':420000,'cost_budget':800000,'max_steps':45,'concurrency':2,
        'run_token_budget':900000,'run_cost_budget':1500000})
    assert result['saved'] and result['applies_to']=='NEW_RUNS_ONLY'
    saved=api.read()['config']
    assert saved['platform']['primary']=='reasoning'
    assert saved['platform']['max_steps']==45
    run_config,effective=select_run_models(saved,{'backend':'primary','testing':'primary'})
    assert effective['backend']['primary']=='primary'
    assert effective['testing']['primary']=='primary'
    assert api.read()['config']['roles']['backend']['agent'].get('primary') is None
    assert run_config is not saved
    with pytest.raises(ValueError):select_run_models(saved,{'backend':'missing'})
    with pytest.raises(ValueError):select_run_models(saved,{'unknown':'primary'})


def test_new_model_and_independent_api_key_can_be_saved_and_removed(tmp_path,monkeypatch,encrypted_credentials):
    ref='env:SECONDARY_MODEL_API_KEY'
    monkeypatch.delenv(ref[4:],raising=False)
    bench,api,config=settings(tmp_path)
    key='synthetic-secondary-model-key'
    registered=api.act('credential-register',{'run_id':'console-config','ref':ref,'value':key})
    assert registered['credential']['configured']
    assert ref in api.read()['config']['platform']['policy']['secrets']
    profile={**config['models']['primary'],'model':'deepseek-secondary','secret_ref':ref}
    saved=api.act('model-profile-save',{'run_id':'console-config','profile_id':'secondary',
        'profile':profile,'is_new':True,'api_key':key})
    assert saved['saved'] and saved['credential']['source']=='local_encrypted'
    current=api.read()
    assert current['config']['models']['secondary']['model']=='deepseek-secondary'
    assert 'secondary' in current['config']['platform']['policy']['models']
    assert next(c for c in current['credentials'] if c['ref']==ref)['configured']
    assert key not in json.dumps(current)
    removed=api.act('credential-remove',{'run_id':'console-config','ref':ref})
    assert not removed['configured']
    deleted=api.act('model-profile-delete',{'run_id':'console-config','profile_id':'secondary'})
    assert deleted['saved'] and 'secondary' not in api.read()['config']['models']
    with pytest.raises(ValueError):api.act('model-profile-delete',{'run_id':'console-config','profile_id':'primary'})
