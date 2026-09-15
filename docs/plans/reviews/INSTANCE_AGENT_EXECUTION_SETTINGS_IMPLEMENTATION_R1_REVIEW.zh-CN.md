# 实例 Agent 执行配置实施 R1 独立审查

2026-09-15。结论：**REVISE**。发现一项 P2 旧归档故障回退兼容问题；未发现 P0/P1 问题。此结论针对本次冻结候选，不能由计划审查或其他测试通过替代。

## 发现

### P2：旧版空实例归档在恢复提交前失败，回退误判为数据库已提交

位置：[instance_archive.py:566](../../../src/scidiscovery/artifact_agent/service/instance_archive.py#L566)，`_migrated()` 的空实例分支；调用方为 `rollback()` 第 878 行。

旧档恢复的预检、事务导入及完成前检查已使用四列有限兼容视图，但这个数据库切换判定仍执行 `dict(row) == snapshot["tombstone"]`。旧墓碑没有实例配置的三列，迁移后的活动墓碑包含固定 NULL/0；即使其他字段完全相同，该比较也必定为 False。空实例没有可检查的 Artifact、Run 或其他业务行，会进入此分支。`rollback()` 将 False 解释为恢复数据库已经提交，拒绝本来安全且由页面提供的恢复回退。

独立复现步骤：

1. 使用既有 `archive_system` 建立无成果、无 Run 的合成实例；移除本次四个新增列，使用正式 `save_archive()` 生成旧结构归档。
2. 调用安装所用 `_initialize()` 添加四列；`restore_preview()` 返回 ready。
3. 在既有 `after_restore_copy` 故障点抛出异常。该点位于数据库切换之前。
4. 用新的 `InstanceArchive` 服务对象执行 `rollback()`。

实际输出：

```text
restore fault: test: before database switch
index state: restoring
database instance state: closed
rollback incorrectly rejected: ArchiveError restore database switch committed; resume is required
```

新格式空归档使用同一故障点的对照结果为 `rollback: archived`。因此本问题是此次旧档跨列恢复的遗漏，而非既有回退行为。没有科学结果丢失；影响是工程状态判定错误，原可回退操作被迫转为继续恢复。继续恢复仍可用，故定级 P2。

修复应让这个旧墓碑比较复用现有 `execution_settings_tombstone()`，保留旧身份及已有新字段的完整比较；不需要扩大迁移范围或新增状态机。补充空旧档在提交前中断后回退成功、提交后中断仍拒绝回退并要求续接的定向验证。

独立验证记录：首次脚本因 `/tmp` 启动缺少测试导入路径失败；添加明确仓库/源码路径后复现成功。最终复现耗时 1.006 秒、峰值 67.47 MiB；新档对照耗时 0.906 秒、峰值 67.16 MiB。均使用既有 `instance-workbench/run_bounded.py`，512 MiB、自有进程树限制、串行执行。临时证据为 `/tmp/scid-settings-review-repro-r1.json/.log`、`/tmp/scid-settings-review-control.json/.log`；脚本为 `/tmp/scid-settings-review-repro.py` 与 `/tmp/scid-settings-review-control.py`。上述步骤及完整关键输出已保存在本报告，不依赖临时文件长期存在。

## 精确范围和已检查路径

按 [scid-cross-boundary-review 技能](/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/.agents/skills/scid-cross-boundary-review/SKILL.md)进行只读实施审查。基线为 `da220ce31c8cc9f9a60542a018b279e2f331f4c0` 加本轮之前已存在的工作树修改；以 [BASELINE.json](../evidence/agent-execution-settings/BASELINE.json)、冻结副本和 [IMPLEMENTATION_DIFF.patch](../evidence/agent-execution-settings/IMPLEMENTATION_DIFF.patch)识别本轮责任范围，未用 HEAD 全量 diff 归责已有 UI 工作。

独立核对 [CANDIDATE_R1.json](../evidence/agent-execution-settings/CANDIDATE_R1.json)全部 37 项文件散列一致，计划散列为 `d76e5ee486c1595fa7dc77c5776f3319b0650c9992f1914190b6ed69c9c731ec`，与实际文件一致。未修改生产源码或测试；仅新增此报告。

已沿代码和已有证据检查：

- 配置解析、逐字段优先级、停用 Operation 覆盖保留、配置错误定位；控制/UI 公共文件启动快照和实例数据库 CAS。语言不进入科学参数、资格、审批或成果校验，Worker 两后端从冻结 Run/assignment 获取语言，不重读全局文件。
- Root preflight→normalized_request→invoke→Run 持久快照→assignment→submit→run_status/UI。行为值进入请求身份，来源说明不制造新身份；预检后设置变化不改原标准请求，提交不以最新设置否定旧 Run。
- 新请求默认预算、恢复源预算与显式预算优先级；恢复省略 profile 时继承原快照，旧记录 NULL 使用兼容值。恢复归属、输入、摘要、草稿和次数检查仍保留，实例默认不自动扩张恢复链。
- 动态角色生成及安装核对；已检索 `src`、`plugins`、`scripts` 的模型消费位置。CLI launcher、两个 live probe 使用队列快照，编译器中的旧模型仍仅作为兼容默认和旧摘要成分。同角色复用要求已知实际模型/推理匹配，语言在新 assignment 读取；未知配置不声明匹配。未发现按模型新增角色或修改科学权限的路径。
- UI 同源、CSRF、实例管理权限、只读状态、CAS、维护锁及独立于科学操作的保存路径。设置页面和 Run 元数据标注请求配置，不把它们当作实际模型遥测。
- 归档的四列共享定义、原字节不变、完整结构/已有行比较、预检与提交边界、含 Run 的新旧档提交后续接。除上述空实例回退分支外，未发现额外结构被放宽或新字段被静默清空。
- 安装器首次创建、升级保留、非普通文件拒绝、事务备份和控制/UI 服务同路径；未引入额外配置存储或通用调度机制。

## 已有实际证据与验收边界

已阅读 [IMPLEMENTATION.zh-CN.md](../evidence/agent-execution-settings/IMPLEMENTATION.zh-CN.md)与相关记录。P0、P6 的平台 `session_meta/turn_context` 记录支持同一编译角色分别运行 Luna/low、Sol/medium；固定模型角色负对照实际使用固定 Sol，能证明旧角色模型覆盖请求的风险。P6 两实例、同 role/Worker/digest 的受控完成记录支持中英文新摘要分别生效。这些结论来自平台记录及控制结果，不采信 Agent 模型自述。

隔离安装证据覆盖 50 个 Operation 合同与 25 个动态角色，Root Schema 变化仅为 preflight/invoke 新控制参数；实际旧 `/opt` 安装归档的新版本恢复及原字节保持、浏览器保存和 412px 页面无横向溢出已有证据。审查时隔离 r2 wheel 与候选源码还差 `read_model` 一行可选属性兼容，因此当前轮不能声称最终精确包已验收。

已核对定向测试记录的范围与失败披露。既有 recursive_current 及 hardened stdio 失败有冻结基线复现，不归责本候选；hardened 配置/提交/恢复证据来自合适的进程内夹具，不能据此宣称原 hardened stdio 通过。独立审查未重新执行全量测试、CLI、浏览器、真实科研任务或外部求解。

修复此 P2 后，应保留本 R1 结论，生成精确修订候选与独立复核记录，再从最终源码重建四 wheel 并核对隔离安装。生产安装后的实际实例设置和正常科研任务新语言验收仍属于后续安装验收，不能由合成 P6 替代。
