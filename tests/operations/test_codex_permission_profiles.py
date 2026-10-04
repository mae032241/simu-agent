"""Source adapter checks; protocol replies are simulated, no native/model calls."""
import json
import pytest
from scidiscovery.platforms.codex_app_server import HostError
from scidiscovery.platforms.codex_root_host import CodexRootHost,RootIdentity,RootPermissions
from scidiscovery.platforms.codex_progression import CodexProgressionFactory

PROFILE={'filesystem':{':root':'deny',':workspace_roots':'write'},'network':{'enabled':True}}

class Connection:
    def __init__(self, *, profile='isolated',definition=None,network=True):
        self.on_event=lambda event:None;self.failed=False;self.requests=[]
        self.profile=profile;self.definition=PROFILE if definition is None else definition;self.network=network
    def rpc(self,method,params):
        self.requests.append((method,params))
        if method=='config/read':return {'config':{'default_permissions':'isolated','permissions':{'isolated':self.definition}}}
        if method in {'thread/start','thread/resume'}:
            return {'thread':{'id':'root','sessionId':'root'},'approvalPolicy':'never',
                    'activePermissionProfile':{'id':self.profile},
                    'sandbox':{'type':'workspaceWrite','networkAccess':self.network,'writableRoots':[]}}
        if method=='turn/start':return {'turn':{'id':'turn'}}
        return {}
    def notify(self,*args):pass

def named(**kwargs):
    return RootPermissions(permission_profile='isolated',profile_definition=json.dumps(PROFILE),**kwargs)

def test_named_profile_sent_on_fresh_resume_and_turn_without_legacy_override():
    permissions=named()
    for prior in (None,RootIdentity('root','root')):
        connection=Connection();host=CodexRootHost(connection,permissions)
        host.initialize(cwd='/workspace',expected_config={});host.open_root(cwd='/workspace',prior=prior)
        host.start_turn('synthetic source protocol check')
        for method,params in connection.requests:
            if method in {'thread/start','thread/resume','turn/start'}:
                assert params['permissions']=='isolated' and params['approvalPolicy']=='never'
                assert 'sandbox' not in params and 'sandboxPolicy' not in params
                assert 'sandbox_workspace_write' not in params.get('config',{})
    assert len(permissions.declaration()['permission_profile']['sha256'])==64

@pytest.mark.parametrize('reply',[{'profile':'wrong'},{'network':False},
    {'definition':{**PROFILE,'filesystem':{':root':'read',':workspace_roots':'write'}}}])
def test_profile_or_effective_config_drift_fails_before_turn(reply):
    connection=Connection(**reply);host=CodexRootHost(connection,named())
    with pytest.raises(HostError,match='root_permissions_mismatch'):
        host.initialize(cwd='/workspace',expected_config={});host.open_root(cwd='/workspace')
    assert not any(method=='turn/start' for method,_ in connection.requests)

@pytest.mark.parametrize('profile',[{'extends':':workspace',**PROFILE},
    {**PROFILE,'network':{'enabled':False}}])
def test_profile_cannot_change_network_or_inherit_unfrozen_definition(profile):
    with pytest.raises(HostError,match='root_permissions_unsupported'):
        RootPermissions(permission_profile='isolated',profile_definition=json.dumps(profile))

def test_legacy_start_and_turn_keep_their_existing_policy():
    connection=Connection();host=CodexRootHost(connection,RootPermissions())
    host.initialize(cwd='/workspace',expected_config={});host.open_root(cwd='/workspace');host.start_turn('ordinary')
    params=dict(connection.requests)['thread/start']
    assert params['sandbox']=='workspace-write' and 'permissions' not in params
    assert params['config']['sandbox_workspace_write']=={'network_access':True,'writable_roots':[]}
    assert dict(connection.requests)['turn/start']['sandboxPolicy']=={'type':'workspaceWrite','networkAccess':True}

def test_named_profile_rejects_request_overrides_before_rpc():
    connection=Connection();host=CodexRootHost(connection,named())
    host.initialize(cwd='/workspace',expected_config={})
    with pytest.raises(HostError,match='conflicting_override'):
        host.open_root(cwd='/workspace',options={'config':{'sandbox_workspace_write':{'network_access':False}}})
    assert not any(method=='thread/start' for method,_ in connection.requests)

def test_factory_preserves_frozen_network_catalog_and_recovery_checks(tmp_path):
    from scidiscovery.operations.catalog import compile_installed_catalog
    factory=CodexProgressionFactory(project_root=tmp_path,state_root=tmp_path,socket_path='socket',
        approval_base_url='http://127.0.0.1:8765',permissions=named(),catalog=compile_installed_catalog())
    assert factory.root_permissions({}, {}, None)==named()
    with pytest.raises(HostError,match='injected policy differs'):
        factory.root_permissions({'root_network_access':False}, {}, None)
    factory.permissions=RootPermissions(network_access=False,permission_profile='isolated',
        profile_definition=json.dumps({**PROFILE,'network':{'enabled':False}}))
    with pytest.raises(HostError,match='declared network or web_search'):
        factory.root_permissions({'root_network_access':False}, {}, None)
    factory.permissions=named()
    with pytest.raises(HostError,match='unproven'):
        factory.root_permissions({}, {'turn_id':'turn','root_permissions':RootPermissions().declaration()},
            RootIdentity('root','root'))

def test_factory_applies_named_profile_at_real_open_path(tmp_path,monkeypatch):
    import os
    from types import SimpleNamespace
    from scidiscovery.agent_execution_settings import ProgressionSettings
    from scidiscovery.platforms.codex_app_server import AppServer
    from scidiscovery.operations.catalog import compile_installed_catalog
    project=tmp_path/'project';(project/'.codex').mkdir(parents=True)
    config={'mcp_servers':{'scidiscovery':{'command':'scidiscovery-mcp-proxy','args':['--socket','socket']}}}
    (project/'.codex/config.toml').write_text('[mcp_servers.scidiscovery]\ncommand="scidiscovery-mcp-proxy"\nargs=["--socket","socket"]\n')
    home=tmp_path/'home';home.mkdir()
    (home/'config.toml').write_text('default_permissions="isolated"\n[permissions.isolated.filesystem]\n":root"="deny"\n":workspace_roots"="write"\n[permissions.isolated.network]\nenabled=true\n')
    monkeypatch.setenv('CODEX_HOME',str(home))
    connection=Connection();connection.child=SimpleNamespace(pid=os.getpid());connection.close=lambda:None
    rpc=connection.rpc
    def reply(method,params):
        if method=='config/read':
            connection.requests.append((method,params))
            return {'config':{**config,'permissions':{'isolated':PROFILE}}}
        if method=='mcpServerStatus/list':return {'data':[{'name':'scidiscovery','tools':{
            'scid_catalog':{},'scid_describe':{},'scid_call':{}}}]}
        if method=='mcpServer/tool/call':return {'structuredContent':{'management_url':
            'http://127.0.0.1:8765/sessions/sch_'+'0'*32+'?capability=synthetic'}}
        return rpc(method,params)
    connection.rpc=reply
    monkeypatch.setattr(AppServer,'launch',lambda *args,**kwargs:connection)
    factory=CodexProgressionFactory(project_root=project,state_root=tmp_path/'state',socket_path='socket',
        approval_base_url='http://127.0.0.1:8765',command=['synthetic-peer'],permissions=named(),
        catalog=compile_installed_catalog())
    row={'config_json':json.dumps({'effective':{'progression':ProgressionSettings().model_dump()}}),
        'host_json':None,'checkpoint_json':'{}'}
    host=factory(row,lambda event:None)
    try:
        assert host.permissions==named() and host.identity==RootIdentity('root','root')
        assert dict(connection.requests)['thread/start']['permissions']=='isolated'
        assert not any(method=='turn/start' for method,_ in connection.requests)
    finally:host.close()
    # A project cannot replace the host-only definition or reintroduce legacy overrides.
    with (project/'.codex/config.toml').open('a') as file:file.write('\n[permissions.isolated.network]\nenabled=true\n')
    with pytest.raises(HostError,match='conflicting_override'):factory(row,lambda event:None)

@pytest.mark.parametrize('reply',[{}, {'exitCode':1,'stdout':'{}'},
    {'exitCode':0,'stdout':'invalid'}, {'exitCode':0,'stdout':json.dumps({'public_read':True})}])
def test_host_preflight_does_not_accept_rpc_success_as_canary_pass(reply):
    from scripts.probe_covshift_permissions import evaluate
    assert evaluate(reply)[0] is False

def test_host_preflight_uses_only_synthetic_inputs_and_arg0_runtime(tmp_path):
    import shutil
    import tomllib
    from pathlib import Path
    from scripts.probe_covshift_permissions import prepare,sha,NAME,evaluate,REQUIRED
    native=tmp_path/'native';native.write_bytes(b'synthetic native binary')
    root=Path('/tmp')/('scid-covshift-protocol-'+tmp_path.name)
    try:
        prepare(root,native,sha(native))
        config=tomllib.loads((root/'host-codex-home/config.toml').read_text())
        paths=config['permissions'][NAME]['filesystem']
        assert paths[':root']=='deny' and paths[str(root/'public')]=='write'
        assert paths[str(root/'host-codex-home/tmp/arg0')]=='read'
        assert str(root/'host-codex-home') not in paths and str(root/'host-private') not in paths
        assert (root/'host-codex-home/auth-canary.json').is_file()
        assert (root/'host-codex-home/sessions/history-canary.txt').is_file()
        assert {p.name for p in (root/'public').iterdir()}=={'input.txt','canary.py'}
        assert config['permissions'][NAME]['network']['enabled'] is False
        assert evaluate({'exitCode':0,'stdout':json.dumps(dict.fromkeys(REQUIRED,True))})[0] is True
    finally:
        if root.exists():shutil.rmtree(root)

def test_host_preflight_rejects_source_overlay_as_installed_candidate(tmp_path):
    import sys
    from scripts.probe_covshift_permissions import installed_identity
    (tmp_path/'candidate.json').write_text(json.dumps({'python':sys.executable,'head':'synthetic'}))
    with pytest.raises(ValueError,match='installed_candidate_import_mismatch'):
        installed_identity(tmp_path)
