# P2a 共通执行状态实施记录

日期：2026-10-17。范围：基线 `be1b379e408544fab7b2527e36c02470ceb224d5` 上的 P2a 差异；依据[拆分候选](../THIN_P2_P3_IMPLEMENTATION_SPLIT_20261017.zh-CN.md)及其[设计独审](THIN_P2_P3_SPLIT_DESIGN_REVIEW_20261017.zh-CN.md)。实现已冻结、未提交，交[代码独审](P2A_COMMON_EXECUTION_STATE_REVIEW_20261017.zh-CN.md)定点收口；动态未验收。

## 精确文件责任

生产仅五文件：

- `src/scidiscovery/operations/execution.py`
- `src/scidiscovery/research_loop/experiments.py`
- `src/scidiscovery/research_loop/managed_wait.py`
- `src/scidiscovery/research_loop/history.py`
- `src/scidiscovery/research_loop/lineage.py`

定向 fixture/负控仅三文件：

- `tests/research_loop/composed_execution_fixture.py`
- `tests/research_loop/test_composed_execution_results.py`
- `tests/research_loop/test_managed_execution_wait.py`

工作树同期出现的其他来源规则、controller/contracts/CLI 修改属于其他实施者，不在本节点提交或审查范围。没有新状态账、预算、TCAD 特例、注册、Root 或安装入口；未修改 R0 replay_check 接受、完成及 CLI 反馈钩子。

## 变化与不变量

公共 `execution_status` 保留 accepted/submitted/queued/running/cancelling（submitted 为既有别名）；未知/未识别状态归 unknown。新 call 准入、dispatch/reconcile/progress 和 managed waiting 使用同一判定。未知或缺原 external binding 不放新 call，pending 不伪装 running；waiting 原件保留 observed_state，公开等待 reason 使用中性的 pending。

状态字符串不单独授予等待资格：仍须有原 accepted/config/submission 和声明的 query，adapter 负责校验原 prepared/已知 external 绑定。原 native turn 的成功、usage/raw hash、writer 停止、checkpoint、预算与会话 gate 原位保留。真实 local 同步 submit 的 process 原件可能先于 submission，progress 保留已有 running 可见性；准入与异步 waiting 仍要求原绑定。

cancelled 归入工程 known_failed，但要求 completed、observation 同值保留 `native_state='cancelled'`，有完整原件证明且与原 call/scope 绑定；放行后继 call 前再次确认原取消 observation。该状态经 history 校验、lineage 的 A 视图和原 W wake packet 保留，不产生科学不合格判决或候选资格。旧无 native_state 的 observation 按原形状兼容，不补写旧原件；原取消字段被删除或改成 failed 均不能通过校验。

freeze 同时绑定公共状态 helper 的源文件，防止将行为提至 `operations/execution.py` 后遗漏其实现身份。生命周期字段和 observation 版本没有扩张；本节点没有退款、额度增加或新 budget owner。

## 最小负控与静态证据

- 既有 opaque fixture 的 backend acceptance 现在绑定 call/scope/prepared digest/external ID；新增一次篡改 prepared digest 的 CLI reconcile 负控。它证明共通路径消费适配器身份校验，不证明真实远端已提供这些事实。
- 一个既有 case 中用字面状态逐一经过实际 dispatch/progress，断言原 accepted、call 数和原件字节不变；queued/cancelling 另经过真实 CLI run/reconcile 拒绝路径。unknown/未识别状态及丢 external binding 都保持 unknown、不增加 call。
- 既有 async reconciliation 增一条 cancelled 行：覆盖 observation 字段丢失/替换拒绝、重复 reconcile 不读后端、seal→A 取消事实保留且无候选。既有 wait 完整链只增一条 queued→cancelling→cancelled 行：不得提前 wake/seal，原 W 消费取消事实后才封存；没有状态×结果×fragment 笛卡尔积。
- 原 uncertain case 保留 unknown；原 accepted/submitted 在 fixture 有精确 backend acceptance 时现为合法 pending，其阻止新 call 的负控移至上述公共 case。`test_managed_execution_wait.py` 真实进程场景明确标 `process_e2e`，不暗含在默认 source 选择中。
- 八文件及嵌入 LAUNCHER 的 AST 解析、静态空白检查、`git diff --check` 通过；没有 import 测试或生产模块。最终八文件全文及 SHA-256 已本地持久保存，快照整体 SHA-256 为 `fd39722467056b12dc45214712fa822d4c143c57f369d05a52069ce0e19e8e93`，私有快照不提交。

上述负控只已编写、未执行。本轮没有 pytest/collect、CLI/进程、build/install、模型、SSH、许可证或 solver 运行，也没有新的耗时/RSS/内核隔离结果。不得用 AST 或 synthetic fixture 声称实际异步后端、取消实现、跨 boot、真实会话唤醒或生产 TCAD 合格。P2b–d/P3 及主计划原有未验收限制继续保留，真实 TCAD 仍未启用。
