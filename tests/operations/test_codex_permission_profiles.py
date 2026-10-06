"""Source adapter checks; protocol replies are simulated, no native/model calls."""
import json
import pytest
from scidiscovery.platforms.codex_app_server import HostError
from scidiscovery.platforms.codex_root_host import CodexRootHost,RootIdentity,RootPermissions
from scidiscovery.platforms.codex_progression import CodexProgressionFactory

PROFILE={'filesystem':{':root':'deny',':workspace_roots':'write'},'network':{'enabled':True}}

# Actual 0.159.2 config/read shape captured under the default guard. Runtime
# path grants are remapped to this synthetic profile; empty optional fields are
# preserved verbatim. No auth/model/provider configuration belongs in this fixture.
OBSERVED_PROFILE={**PROFILE,'description':None,'extends':None,'workspace_roots':None,
    'filesystem':{**PROFILE['filesystem'],'glob_scan_max_depth':None},
    'network':{'enabled':False,'proxy_url':None,'enable_socks5':None,'socks_url':None,
        'enable_socks5_udp':None,'allow_upstream_proxy':None,
        'dangerously_allow_non_loopback_proxy':None,'dangerously_allow_all_unix_sockets':None,
        'mode':None,'domains':None,'unix_sockets':None,'allow_local_binding':None,'mitm':None}}

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
    root_instructions='Root scheduler instructions from the project configuration.'
    config={'developer_instructions':root_instructions,'mcp_servers':{'scidiscovery':{'command':'scidiscovery-mcp-proxy','args':['--socket','socket']}}}
    (project/'.codex/config.toml').write_text('developer_instructions='+json.dumps(root_instructions)+'\n[mcp_servers.scidiscovery]\ncommand="scidiscovery-mcp-proxy"\nargs=["--socket","socket"]\n')
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
    launches=[]
    def launch(command,**kwargs):
        launches.append(command)
        return connection
    monkeypatch.setattr(AppServer,'launch',launch)
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
        assert 'developer_instructions='+json.dumps(root_instructions) in launches[0]
    finally:host.close()
    config.pop('developer_instructions')
    starts=sum(method=='thread/start' for method,_ in connection.requests)
    with pytest.raises(HostError,match='effective_config_missing'):factory(row,lambda event:None)
    assert sum(method=='thread/start' for method,_ in connection.requests)==starts
    config['developer_instructions']=root_instructions
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

def test_actual_config_read_empty_defaults_preserve_frozen_profile_digest():
    expected={**PROFILE,'network':{'enabled':False}}
    policy=RootPermissions(network_access=False,permission_profile='isolated',profile_definition=json.dumps(expected))
    before=policy.declaration()
    policy.verify_config({'permissions':{'isolated':OBSERVED_PROFILE}})
    assert policy.declaration()==before
    assert json.loads(policy.profile_definition)==expected

@pytest.mark.parametrize('section,key,value',[(None,'unknown_optional',None),
    (None,'extends',':workspace'),(None,'workspace_roots',['/extra']),
    ('filesystem','/extra','read'),('filesystem','unknown_optional',None),
    ('filesystem','glob_scan_max_depth',3),('network','unknown_optional',None),
    ('network','allow_local_binding',True),('network','proxy_url','http://proxy'),
    ('network','enabled',True)])
def test_normalization_rejects_unknown_null_and_nonnull_profile_changes(section,key,value):
    import copy
    actual=copy.deepcopy(OBSERVED_PROFILE)
    (actual if section is None else actual[section])[key]=value
    with pytest.raises(HostError,match='root_permissions_mismatch'):
        RootPermissions(network_access=False,permission_profile='isolated',
            profile_definition=json.dumps({**PROFILE,'network':{'enabled':False}})).verify_config(
                {'permissions':{'isolated':actual}})

def test_preflight_permission_diagnostic_excludes_unrelated_and_proxy_credentials():
    from scripts.probe_covshift_permissions import permission_diagnostic,NAME
    reply={'config':{'auth':'private-auth-value','model_providers':{'credential':'private-provider-value'},
        'permissions':{NAME:{**OBSERVED_PROFILE,'network':{'enabled':False,'proxy_url':'private-proxy-value'}}}}}
    snapshot=permission_diagnostic('config/read',reply)
    rendered=json.dumps(snapshot)
    assert not any(value in rendered for value in ('private-auth-value','private-provider-value','private-proxy-value'))
    assert snapshot['selected_profile']['network']['enabled'] is False
    assert len(snapshot['selected_profile']['network']['proxy_url']['sha256'])==64
    assert permission_diagnostic('thread/start',{'activePermissionProfile':{'id':NAME},'approvalPolicy':'never',
        'sandbox':{'type':'workspaceWrite'},'thread':{'turns':['private history']}})=={
            'activePermissionProfile':{'id':NAME},'approvalPolicy':'never','sandbox':{'type':'workspaceWrite'}}


# Both ordinary-host Covshift preflights returned this 0.159.2 shape. Only
# private trial path prefixes/profile id are replaced; no auth/config/history.
MULTI_WRITE_ROOTS=['/opt/exp/runs','/submission','/task-tmp',
    '/trial/project/.scidiscovery-runs','/trial/project/runs',
    '/trial/project/submission','/trial/project/workspace','/workspace']
MULTI_WRITE_PROFILE={'filesystem':{':root':'deny',':minimal':'read',
    '/trial/project':'read','/opt/exp':'read',
    **{path:'write' for path in MULTI_WRITE_ROOTS}},'network':{'enabled':False}}
MULTI_WRITE_REPLY={'approvalPolicy':'never',
    'activePermissionProfile':{'id':'isolated','extends':None},
    'sandbox':{'type':'workspaceWrite','writableRoots':MULTI_WRITE_ROOTS,
        'networkAccess':False,'excludeTmpdirEnvVar':True,'excludeSlashTmp':True}}


@pytest.mark.parametrize('prior',[None,RootIdentity('root','root')])
def test_observed_named_multi_write_projection_matches_frozen_profile_on_start_and_resume(prior):
    import copy
    connection=Connection(definition=MULTI_WRITE_PROFILE,network=False)
    rpc=connection.rpc
    def reply(method,params):
        value=rpc(method,params)
        return {**value,**copy.deepcopy(MULTI_WRITE_REPLY)} if method in {'thread/start','thread/resume'} else value
    connection.rpc=reply
    permissions=RootPermissions(network_access=False,permission_profile='isolated',
        profile_definition=json.dumps(MULTI_WRITE_PROFILE))
    declaration=permissions.declaration()
    host=CodexRootHost(connection,permissions)
    host.initialize(cwd='/trial/project',expected_config={})
    host.open_root(cwd='/trial/project',prior=prior)
    assert host.identity==RootIdentity('root','root') and not connection.failed
    assert permissions.declaration()==declaration
    assert not any(method=='turn/start' for method,_ in connection.requests)


@pytest.mark.parametrize('change',['extra','missing','cwd_read_only','duplicate','network','approval','profile','extends'])
def test_named_multi_write_projection_rejects_unfrozen_or_incomplete_policy(change):
    import copy
    reply=copy.deepcopy(MULTI_WRITE_REPLY)
    if change=='extra':reply['sandbox']['writableRoots'].append('/host-private')
    elif change=='missing':reply['sandbox']['writableRoots'].remove('/workspace')
    elif change=='cwd_read_only':reply['sandbox']['writableRoots'].append('/trial/project')
    elif change=='duplicate':reply['sandbox']['writableRoots'].append('/workspace')
    elif change=='network':reply['sandbox']['networkAccess']=True
    elif change=='approval':reply['approvalPolicy']='on-request'
    elif change=='profile':reply['activePermissionProfile']['id']='other'
    elif change=='extends':reply['activePermissionProfile']['extends']=':workspace'
    with pytest.raises(HostError,match='root_permissions_mismatch'):
        RootPermissions(network_access=False,permission_profile='isolated',
            profile_definition=json.dumps(MULTI_WRITE_PROFILE)).verify(reply,cwd='/trial/project')


@pytest.mark.parametrize('roots',[[],['/trial/project']])
def test_named_cwd_write_projection_can_omit_the_declared_cwd(roots):
    reply={**MULTI_WRITE_REPLY,'sandbox':{**MULTI_WRITE_REPLY['sandbox'],'writableRoots':roots}}
    RootPermissions(network_access=False,permission_profile='isolated',
        profile_definition=json.dumps({'filesystem':{':root':'deny','/trial/project':'write'},
            'network':{'enabled':False}})).verify(reply,cwd='/trial/project')
