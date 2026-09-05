from __future__ import annotations

import tomllib
from pathlib import Path


def test_installed_runtime_has_no_legacy_role_contract_loader(installed_probe) -> None:
    installed_probe(
        "full",
        r'''
from importlib.util import find_spec

assert find_spec("scidiscovery.platforms.roles") is None
assert find_spec("scidiscovery.artifact_agent.service.tasks") is None
''',
    )


def test_only_current_scheduler_role_is_distributed() -> None:
    repository = Path(__file__).resolve().parents[2]
    roles = repository / "roles"
    assert {path.name for path in roles.glob("*.md")} == {"scheduler.md"}
    metadata = tomllib.loads((repository / "pyproject.toml").read_text("utf-8"))
    assert metadata["tool"]["setuptools"]["data-files"][
        "share/scidiscovery/roles"
    ] == ["roles/scheduler.md"]


def test_run_protocol_describes_actual_submit_boundaries() -> None:
    repository = Path(__file__).resolve().parents[2]
    protocol = repository.joinpath("docs/role-result-json-protocol-v1.md").read_text(
        "utf-8"
    )
    for retired_claim in (
        "task_evidence_sources",
        "collection-enabled",
        "state=finalizing",
        "记录 current CAS 结果和 reviewer 待办",
    ):
        assert retired_claim not in protocol
    assert "Run 完成不会自动推进 current" in protocol
    assert "父调度器依据编译 review edge" in protocol


def test_active_l_plan_describes_actual_submit_boundaries() -> None:
    repository = Path(__file__).resolve().parents[2]
    plan = repository.joinpath(
        "docs/plans/R5_L_MINIMAL_DEFAULT_RUNTIME_PLAN.zh-CN.md"
    ).read_text("utf-8")
    for retired_claim in (
        "事务性记录 current CAS 结果",
        "按编译 review edge 创建 reviewer Run",
        "收据、reviewer 待办和唯一 head CAS 结果",
        "完成 Run、记录 head CAS 结果并创建 reviewer 待办",
        "Artifact/终态/current/review 职责 | 迁入唯一 RunService",
        "不作为普通 Operation 必填工具",
        "声明推进一个",
    ):
        assert retired_claim not in plan
    assert "提交事务在两种情况下都不更新\nCurrentBinding" in plan
    assert "父调度器同样在读取完成状态后显式调用 reviewer Operation" in plan
    assert "每个 Agent\nOperationSpec 必须显式引用" in plan
