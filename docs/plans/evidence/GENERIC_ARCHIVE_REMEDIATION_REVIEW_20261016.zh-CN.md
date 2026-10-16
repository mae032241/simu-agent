# 归档 R1 / R2 修复独立复审（2026-10-16）

**PASS，限定于下列冻结差异。** 本审查者独立发现前轮两个 P2，未编写修复；此次重新读取生产实现、完整 Worker handler 正控及原始测试日志，不复用原 F2 PASS。未发现本次差异中需要阻断修复的剩余缺陷。

基线为 `53798e9798f6634bd2b62ecedb2bc03e742a7411`，复审其上的四个生产文件与一个测试文件。并发执行/交付修复不属于本结论。收尾逐项核对以下 SHA256 与执行者冻结清单一致；未修改生产/测试、未提交。

| 冻结文件 | SHA256 |
| --- | --- |
| `plugins/tcad_artifact/tcad_artifact/debug_archive.py` | `402ad01a5fa2de59bc2d2d41c85e249677fc9027a8537dc04cfbf210fe32dcad` |
| `src/scidiscovery/artifact_agent/service/instance_archive.py` | `33c89eea93d5b4b3b133f1ff41933619ef48e8a076da899f7977e8f33b7a9ae6` |
| `src/scidiscovery/artifact_agent/service/instance_archive_files.py` | `f03a1d5a23a502f8da875d76cf282e9b5868626ac769bcc121dfa7a538e396ba` |
| `src/scidiscovery/operations/runtime_plugins.py` | `28b64c6f928c1cc853b2db88f8abdbdc3d8b5a8d49020fe7cb61161e7389910d` |
| `tests/operations/test_instance_archive_debug_storage.py` | `5a8cce14cf86b07a2d65955be1f59b8cfd0debd1d1d259844efd66fb3706a8ac` |

R1 已修复。reader 解释生产 `diagnostic_context()` 的 `experiment-workspaces/<task_origin>`，由核心 `run_owner(..., require_task_origin=True)` 查询实际控制 Run 并验证恢复根，而非相信文件名自行授权。当前实例完整私有目录交给既有 `Files.add` 迁移，其他实例保留。没有预算目录、仅准备工作目录的失败前状态也可按控制来源归属，未制造 reservation 或重置预算。旧/未知目录、非 origin、跨实例恢复来源、symlink、普通文件冒充目录仍拒绝。

本次正控 `test_worker_debug_handler_preserves_other_instance_and_allows_real_generic_archive` 从 `LocalWorkerMCPRouter.call_tool("worker_experiment_debug", ...)` 进入生产 `experiment_capability.debug()`，贯穿实际 `diagnostic_context()`、真实 debug service 收集、原件发布与报告封存；合成 adapter 将 submission 放在实际传入的 exchange 目录。B completed/诊断 collected 后，A 通过生产 `InstanceArchive` 真正归档并在关闭 provider 配置后恢复，B 全部 debug 文件字节保持一致。这补上了前轮 service 直调遗漏。领域目标自身的完整目录/ledger/receipt 迁移恢复另用明确的同步 fixture 验证，不外推 native writer 静止。

R2 已修复。`archive_file_roots()` 保留全部基础根，并仅把实际文件或带路径的 missing gap 引用的 plugin root 视为依赖。新空 provider 声明不写入快照；旧快照恢复时只计算必要根的验证视图，不改 sealed manifest/snapshot。新、旧空根正控均恢复原 CAS 字节并再次归档/恢复，明确断言旧 manifest/snapshot 原字节不变。实际 plugin 文件和仅缺失原件 gap 两类负控，均继续拒绝 provider 缺失或 root 改变；未整体放宽恢复根、后端或 schema 校验。

预算锁忙、目标 accepted/running/终态但未 collected、坏 receipt、错误所有权、缺锁、未知残留、预览后原件改变和扫描后 maintenance writer 抢占，仍由既有负控拒绝。此次新增目录识别不启动适配器/solver，不扩大 writer 权限；冻结、复制、控制库 switch、清理和恢复仍走原核心路径。

独立读取以下原始日志和资源记录，未为重复计数或形式验证重跑通过批次：

| 受管命令 | 结果 |
| --- | --- |
| `python -B scripts/run_tests.py --output /tmp/scid-archive-r1r2-fix-01 tests/operations/test_instance_archive_debug_storage.py` | 31 passed，18.37 秒；监督 19.149 秒，RSS 150118400 bytes。 |
| `python -B scripts/run_tests.py --output /tmp/scid-archive-r1r2-final-compat tests/operations/test_instance_archive.py tests/operations/test_instance_archive_debug_storage.py::test_controlled_workspace_before_reservation_is_owned_without_inventing_budget` | 67 passed，3 deselected，47.44 秒；监督 47.960 秒，RSS 150593536 bytes。 |
| 独立 `git diff --check` | 通过。 |

两批共 **98 个不同用例通过**，均持 `serial_lock/run_one`，exit=0、cleanup_complete=true、无资源止损。首批后只新增末批单例，四个生产文件不变。原始 `result.json`、`batch-001/pytest.log` 和 `batch-001/resource.json` 保留在各 output 根；测试器按既有 finally 清理临时状态目录，不能把残余临时文件称作完整原件集。三项 deselected 是原 archive 文件的 process_e2e 参数化用例，未运行。

本结论不涵盖全套回归、安装 wheel、真实 daemon/browser、solver、模型或原生写者压力场景。现有生产 backend 对 native Run 未确认 quiescence 仍保守拒绝，未因本修复取消。未扩大到 rootless-MCP 融合或研究循环外部交付目标的整体迁移。原反例与证据保留于 [新审查报告](GENERIC_ARCHIVE_FRESH_REAUDIT_20261016.zh-CN.md)，本次 PASS 仅关闭其中归档 R1/R2。
