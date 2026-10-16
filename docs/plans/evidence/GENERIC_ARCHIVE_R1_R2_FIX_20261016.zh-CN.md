# 归档 F2-R1 / F2-R2 定向修复

基线：`dev@53798e9798f6634bd2b62ecedb2bc03e742a7411`。依据独立新审查 `GENERIC_ARCHIVE_FRESH_REAUDIT_20261016.zh-CN.md` 与其中两个受管反例；本记录不覆盖同时实施的执行观察/通用候选修复。未提交或推送 Git。

## 修复内容

**R1：正常私有实验目录的控制归属。** TCAD reader 现在处理生产 `diagnostic_context()` 保留的 `experiment-workspaces/<task_origin>`。核心通过现有 Run 记录和不可变 recovery lineage 确认该身份确为原 task origin、家族 instance 一致；插件据此选择目标实例的完整私有 namespace，交给原 `Files.add` 做路径、链接、数量、摘要、复制及恢复。其他实例目录保留原位，未知 Run、非 origin、跨实例 lineage、错误目录形状和符号链接仍拒绝。

目录内部普通文件属于该受控私有 namespace，作为机械原件完整保留，不授予科学资格。活动/未知/未收集诊断、预算锁占用、损坏 ledger/receipt 和未知残留的原拒绝保持。`diagnostic_context` 可能先建目录、后校验预算或准备失败；这种已有控制 origin、尚未创建 reservation 的目录也可保留，不制造预算或外部执行事实。原 maintenance guard、durable marker、native writer quiescence 和关键切换前 inventory 复查均沿用。

**R2：恢复只依赖实际原件。** 新 snapshot 只保留实际选中文件和明确缺件 gap 使用的 plugin roots。恢复旧 snapshot 时从已验证的原文件/gap计算必需 root；空 provider 声明不再成为纯通用实例的恢复依赖。含真实 plugin 文件、目录或相关 missing gap 的归档仍要求原 provider 和相同 root。基础 roots/backend 验证保持。

这只改变必需 root 的计算；不会重写旧 manifest、snapshot、指纹或维护 journal。legacy 空 root 回归在封存前模拟旧 producer，恢复时直接验证其原档案，并断言 manifest/snapshot 字节未变。未配置插件但存在真正未知 TCAD 残留的 explicit unsupported 策略保持。

## 入口与负控验证

所有检查使用 `scripts/run_tests.py` 的 `serial_lock/run_one`，与执行侧代理协调串行；无模型、solver、全量套件或并发测试。

| 实际命令 | 结果与证据 |
| --- | --- |
| `python -B scripts/run_tests.py --output /tmp/scid-archive-r1r2-fix-01 tests/operations/test_instance_archive_debug_storage.py` | 31 passed，18.37秒；监督19.149秒，采样tree RSS高水位150,118,400 bytes，cleanup=true。 |
| `python -B scripts/run_tests.py --output /tmp/scid-archive-r1r2-final-compat tests/operations/test_instance_archive.py tests/operations/test_instance_archive_debug_storage.py::test_controlled_workspace_before_reservation_is_owned_without_inventing_budget` | 67 passed、3 deselected，47.44秒；监督47.960秒，采样RSS150,593,536 bytes，cleanup=true。 |
| `git diff --check` | 通过。 |

两批共98个不同用例通过，第二批没有重跑首批31项；3个省略是原文件的 process_e2e lane 测试，source lane 明确不运行。每批 `batch-001/pytest.log` 和 `resource.json` 保留原始记录，无资源止损。受管 runner 在 finally 正常清理 `tmp`/`scratch`，本执行者没有另行清理；残留文件不构成完整临时产物保留，证据范围为原始日志、资源记录与源码断言。首批后只新增一个 reservation 前私有目录回归，生产代码未变。

完整入口正控为 `test_worker_debug_handler_preserves_other_instance_and_allows_real_generic_archive`：通过真实 `LocalWorkerMCPRouter.call_tool('worker_experiment_debug', ...)`、生产 handler、`diagnostic_context` 和调试服务运行；合成 adapter 的 submission 放入实际 `exchange_directory`，不再使用管理根外的 fixture 位置。B收集且任务完成后，A无Run的生产 `InstanceArchive` 完成 archive，关闭 provider 后 restore，普通CAS字节和B全部debug字节保持原样。

目标私有目录自身迁移/恢复使用既有同步归档 fixture，断言全部原字节与预算恢复；A归档后B仍可归档。新/legacy空root均执行关闭provider恢复与再次archive/restore；实际文件/相关gap缺provider或root改变均拒绝。原活动、坏归属、损坏receipt、缺锁、held lock、扫描后writer、未知目录与规范路径负控保持通过。

不把同步fixture当作真实native Worker静止资格。没有运行新wheel、daemon/browser、跨主机恢复、真实TCAD或native writer压力场；既有生产 `backend_writer_guards` 的保守拒绝没有放宽。

## 冻结文件

本次仅以下4个生产文件、1个测试文件及本报告属于归档修复；其余 execution/history/generic_results 等工作树改动属于另一执行者。

| 文件 | SHA-256 |
| --- | --- |
| `plugins/tcad_artifact/tcad_artifact/debug_archive.py` | `402ad01a5fa2de59bc2d2d41c85e249677fc9027a8537dc04cfbf210fe32dcad` |
| `src/scidiscovery/artifact_agent/service/instance_archive.py` | `33c89eea93d5b4b3b133f1ff41933619ef48e8a076da899f7977e8f33b7a9ae6` |
| `src/scidiscovery/artifact_agent/service/instance_archive_files.py` | `f03a1d5a23a502f8da875d76cf282e9b5868626ac769bcc121dfa7a538e396ba` |
| `src/scidiscovery/operations/runtime_plugins.py` | `28b64c6f928c1cc853b2db88f8abdbdc3d8b5a8d49020fe7cb61161e7389910d` |
| `tests/operations/test_instance_archive_debug_storage.py` | `5a8cce14cf86b07a2d65955be1f59b8cfd0debd1d1d259844efd66fb3706a8ac` |

状态：实现与定向验证完成，`archive_fresh_reaudit` 独立复审 PASS，见 `GENERIC_ARCHIVE_REMEDIATION_REVIEW_20261016.zh-CN.md`；五个生产/测试文件 SHA 与冻结记录一致。未提交或推送。
