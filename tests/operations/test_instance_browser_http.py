from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import http.client
import json
from urllib.parse import parse_qs, urlencode, urlparse

import pytest

from scidiscovery.artifact_agent.approval_ui.read_model import InstanceReadModel
from scidiscovery.artifact_agent.service.instance_management import (
    InstanceManagementCapabilityError, issue_instance_management_capability,
    verify_instance_management_capability,
)
from tests.operations.test_m6a_direct_instance_management import _root, _setup


def _request(base, method, path, *, form=None, cookie=None):
    url = urlparse(base)
    connection = http.client.HTTPConnection(url.hostname, url.port, timeout=5)
    headers = {} if cookie is None else {"Cookie": cookie.split(";", 1)[0]}
    if form is not None:
        headers.update({"Origin": base, "Content-Type": "application/x-www-form-urlencoded"})
    connection.request(method, path, body=None if form is None else urlencode(form), headers=headers)
    response = connection.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    connection.close()
    return result


def _snapshot(state):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (state/"database").glob("*.sqlite3")}


def test_bound_management_link_refresh_is_read_only_and_optional(tmp_path):
    runtime, state, secret, ui, base = _setup(tmp_path)
    session = "sch_"+"a"*32
    instance = runtime.scheduler_bindings.create_instance_and_bind_session(
        session_key=session, name="browser.origin", title="Original", objective="Original objective")
    root = _root(runtime, session_key=session, secret=secret, base=base)
    try:
        before = _snapshot(state)
        expired = issue_instance_management_capability(session_key=session, secret=secret,
            now=datetime.now(timezone.utc)-timedelta(hours=2))
        with pytest.raises(InstanceManagementCapabilityError):
            verify_instance_management_capability(expired, secret=secret)
        first = root.call_tool("instance_current", {})
        second = root.call_tool("instance_current", {})
        assert first["management_url"] != second["management_url"]
        token = parse_qs(urlparse(second["management_url"]).query)["capability"][0]
        assert verify_instance_management_capability(token, secret=secret).session_key == session
        assert first["name"] == instance.name
        assert _snapshot(state) == before
        root.facade.approval_base_url = None
        assert "management_url" not in root.call_tool("instance_current", {})
    finally:
        ui.stop()


def test_instance_browser_grants_read_without_rebinding_or_cross_instance_access(tmp_path):
    runtime, state, secret, ui, base = _setup(tmp_path)
    ui.read_model = InstanceReadModel(artifacts=runtime.artifacts, bindings=runtime.scheduler_bindings,
        runs=runtime.runs, approvals=runtime.approvals, executions=runtime.executions,
        operation_catalog=runtime.operation_catalog)
    session = "sch_"+"b"*32
    first = runtime.scheduler_bindings.create_instance_and_bind_session(
        session_key=session, name="browser.first", title="First", objective="First objective")
    second = runtime.scheduler_bindings.create_instance_and_bind_session(
        session_key="sch_"+"c"*32, name="browser.second", title="Second", objective="Second objective")
    root = _root(runtime, session_key=session, secret=secret, base=base)
    try:
        capability = parse_qs(urlparse(root.call_tool("instance_current", {})["management_url"]).query)["capability"][0]
        before = _snapshot(state)
        status, _, _ = _request(base, "GET", f"/api/instances/{second.instance_id}/overview")
        assert status == 403
        status, headers, _ = _request(base, "POST", "/instances/access", form={
            "capability": capability, "csrf": ui.session_id,
            "instance_id": second.instance_id, "scope": "read"})
        assert status == 303
        cookie = headers["Set-Cookie"]
        status, _, body = _request(base, "GET", f"/api/instances/{second.instance_id}/overview", cookie=cookie)
        assert status == 200 and json.loads(body)["instance"]["name"] == second.name
        assert _request(base, "GET", f"/api/instances/{first.instance_id}/overview", cookie=cookie)[0] == 403
        assert runtime.scheduler_bindings.session_instance(session_key=session) == first.instance_id
        assert _snapshot(state) == before
    finally:
        ui.stop()


def test_client_registers_at_transport_start_and_pause_blocks_only_new_work(tmp_path):
    from scidiscovery.artifact_agent.interfaces.mcp import build_root_router
    from scidiscovery.artifact_agent.interfaces.mcp_root import RootToolError
    runtime,state,secret,ui,base=_setup(tmp_path)
    key='sch_'+'d'*32
    secret_file=tmp_path/'approval.secret'
    secret_file.write_bytes(secret);secret_file.chmod(0o600)
    try:
        transport=build_root_router(project_root=tmp_path/'project',state_root=state,
            approval_secret_file=secret_file,approval_base_url=base,scheduler_session_key=key,worker_backend='hardened')
        assert any(x['session_key']==key for x in runtime.scheduler_bindings.clients())
        root=transport.router
        assert root.call_tool('instance_current',{})['state']=='unbound'
        instance=runtime.scheduler_bindings.create_instance_and_bind_session(
            session_key=key,name='paused.client',title='Client',objective='Exact objective')
        runtime.scheduler_bindings.set_client_enabled(session_key=key,enabled=False,expected=True)
        assert root.call_tool('instance_current',{})['state']=='paused'
        assert root.call_tool('run_list',{})['runs']==[]
        for action,args in (
            ('operation_preflight',{'name':'paused.preflight','operation_id':'science.experiment.design.v1','inputs':[]}),
            ('operation_invoke',{'name':'paused.invoke','operation_id':'science.experiment.design.v1','inputs':[]}),
            ('execution_start',{'name':'paused.execution'})):
            with pytest.raises(RootToolError,match='paused by the workbench'):
                root.call_tool(action,args)
        assert runtime.runs.active_ids(instance_id=instance.instance_id,limit=10)==()
        runtime.scheduler_bindings.set_client_enabled(session_key=key,enabled=True,expected=False)
        assert root.call_tool('instance_current',{})['name']==instance.name
    finally:
        ui.stop()
