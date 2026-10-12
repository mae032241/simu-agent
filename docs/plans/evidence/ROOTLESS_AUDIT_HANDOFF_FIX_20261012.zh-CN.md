# 审计原件跨科学节点交接修复（2026-10-12）

状态：修复完成，专属源码和安装回归通过，独立复审通过；未为本修复新增付费科研模型场。

## 已发生的缺口

真实场外层 `.trial/rootless-macro-role-cov-20261012/instance` 中，A003 已审计 run2，A004 的任务保存紧邻审计原件引用；H005、W006、A007 不再携带该事实。A007 将公开审计资格保守记为 unknown。随后 W008、A009 进入收口，A009 明确先前回执不可用并再次审计 run2。本修复针对已发生的重复审计，不是推测可能发生的重跑。

定位依据：A003 audit outcome SHA `cc8c394f…8d3eeb`，binding artifact SHA `42152036…4d393`、69011 字节，与 W002 封存 v2 observer 的 run2 模型原件一致；A004 保存 exact candidate_audit 引用。完整原件保留在外层，不复制科学日志。

## 修复范围

- 新 proto9 谱系任务冻结 `audit_projection_version=1`；既有任务缺标记时保留原投影及逐字节重建行为，不修改实例 settings 或科学 schema。
- 从已验证 prefix 内封存任务的原 `candidate_audit` 引用和当前任务的紧邻引用收集、验证、去重。不会扫描当前目录猜最新审计，也不依赖 A 正文。
- 对照已封存 observer 中归档模型的候选 ID、SHA 和字节数。公开栏分别展示 `adapter_result` 和 `artifact_binding`；无原件为 unknown、不同原件为 different。
- 使用已有 readonly 分页输出 `inputs/lineage/audits`，默认 brief 仍统一不超过 4096 UTF-8 字节；超出默认摘录的事实通过页入口读取。
- 适配器状态只具有原 adapter scope，不授予 target、提交或泄漏资格。备注不参与语义判定；泄漏值保留 unknown。原全 unknown 泄漏栏不重复展示，显式事实仍保留。
- 原审计控制事实继续唯一权威，无新账本、预算或审计执行器。

专属回归：`tests/research_loop/test_audit_handoff.py`。冻结清单：`/tmp/scid-audit-handoff-freeze-20261012/manifest-02.json`。覆盖真实 v2 调用与隔离 audit、跨 A/H/W 交接、不同或缺失模型、备注不授资格、旧 proto9 任务重建、原件/页损坏硬拒。作者仅 AST 检查，未执行测试、构建、安装、模型或 git。

## 真实场证据限制

父代理报告该场最终 `delivery_confirmed`，但 driver posthash 返回 3：冻结 manifest 也追踪 repository source，运行过程中本修复改动源文件。旧 wheel、install、config、launcher 未因此改变。本修复不修改原失败记录，也不将该场声称为整体冻结验收通过；实际运行代码身份由父代理另作原冻结包只读比对。

## 验证与保留失败

- 第一轮7文件：83通过、7失败，证据 `.trial/audit-handoff-fix-20261012`。新增夹具使用宿主绝对输出路径，却冻结 `/opt/exp/runs` 别名，候选原件未绑定，审计实际未执行。修正夹具真实namespace映射，未放宽来源断言。
- 独立复审发现收口补正的合法来源集合 `[1,2,4]` 未包含审计节点3。修复仅删除历史回执必须再次处于当前prefix的冗余要求；保留已验证A4冻结引用、精确step关系与原审计事实校验，不继承全祖先。新增成功及损坏负例。
- 最终源码专属9场景通过（50.80秒）：`.trial/audit-handoff-fixed-20261012/batch-001/pytest.log`。第一轮83通过仅为首版证据，不写成最终同一条命令92通过。
- 最终新wheel安装CLI回归通过：`.trial/macro-role-installed-20261012/artifacts-audit-handoff/result/result.json`，20个模块源码/wheel/安装字节一致。
- 在该venv以 `python -I`、独立pytest配置加载安装模块，审计交接专属9场景通过（50.39秒）：同目录 `audit-installed.log` 与 `audit-installed-result.json`；明确为site-packages模块，0模型请求。
- [独立复审](ROOTLESS_AUDIT_HANDOFF_REVIEW_20261012.md)通过；未跑全仓回归、TCAD或新真实科研场。

最终wheel SHA256：`22186e39b80b78254e9b855da97009b171dcf44cfe270505a1f2acb5787442bf`。
