# A2：正式审查不可用后的有限科学改道

状态：独立代码审查 PASS；root 串行定向测试最终10项通过，首次夹具失败与修复保留如下。任务依据为 `THIN_AUTHORITY_REVIEW_REMEDIATION_20261017.zh-CN.md` 第 4 节。A2 起始代码基线 `1f1d407`；并行文档/A4 改动不属于本节点。

## 根因与真实入口

`controller.run → _run → _route → formal_review.request_route` 原来在第二次相同 `failure_key` 时返回 `next_role=None`，随后 `_run` 直接返回通用 `wait`。这绕过既有 `semantic.MAX_AUTHOR_CORRECTIONS`，也没有进入配置好的有限 closeout。只改写 `route_reason` 不能改变 failure_key 的原约束保留。

## 最小修复

- 不可用审查始终返回普通 A 的反馈及实际请求者结论；不创建正式 reviewer，不授资格。任务反馈列普通动作**示例**及其原准入条件，明确未改变对象/身份时正式审查不可用。
- 复用 `author_correction` 的 root/source 原件引用、`MAX_AUTHOR_CORRECTIONS=2` 及原节点/全场预算。每个相同 key 的首次不可用请求之后，最多两次失败补正；在创建下一份任务之前检查耗尽。
- 仅枚举已有 `native-evidence/*/formal-review-unavailable.json` 小控制原件，核对其精确 requester seal 和 failure_key 字段，不重放全科学历史、不读取模型/远端输出、不新增持久重试账。计数为该 key 的不可用请求数减首次请求；E 或普通改道不清除此历史。合法动作可解除当前专属补正，因此某个对象缺资格不全局封锁其他科研；以后同 key 重请求仍沿原 root/count。
- 新对象/身份由 host 重新计算后确实改变 key，才使用新 root。不同措辞不改变 key。schema 保留 `formal_review` 条件选项，允许 A 在同一科学输出选择新对象；反馈和 schema 均解释此条件，不将固定不可用标记误用于所有新对象。
- 独审发现并修正：请求者若已有其他 `author_correction`，不可用审查不能覆盖其 root/reason。现在只更新 source 并保留正式审查不可用反馈，原其他补正额度不重置；仅无其他补正时建立本专属 root。
- 耗尽时，有 delivery_policy 直接调用既有 `_start_closeout`；没有时返回 `formal_review_blocked`、原缺口和恢复条件，明确整体完成未断言。原 `_finish` 仅将状态写入既有 clock ledger，不保存完整结果 JSON；原因原件保留，公开恢复说明在 replay 时从同一封存路由重建，没有第二份状态文件。
- closeout 的 `formal_review` 不回调探索 `_route` 或重复 `_start_closeout`；仍由既有 `delivery.prepare_binding`/有限交付补正拒绝非 deliver 请求。资格、adapter 必需审计、exact 执行批准和远端维护规则均未放宽。

## 精确文件

| 文件 | 责任 |
| --- | --- |
| `src/scidiscovery/research_loop/formal_review.py` | 不可用回普通 A；读取并比较既有失败原件；紧凑反馈 |
| `src/scidiscovery/research_loop/semantic.py` | 原有限补正的绑定、验证、计数和合法改道 |
| `src/scidiscovery/research_loop/controller.py` | 耗尽后原 closeout / 明确 blocked；移除重复请求直接 wait |
| `src/scidiscovery/research_loop/contracts.py` | 既有 schema 和科学视图解释条件动作，无新科学字段 |
| `tests/research_loop/test_formal_review.py` | 最小路由负控及既有正向复用 |
| 本报告 | 根因、边界及未运行账 |

## 定向用例与证明边界

1. 修改既有缺作者身份的 process 用例：步骤 3、4 改写理由但 key 相同；步骤 5 仍可选择 finish，反馈无资格且剩一次补正。
2. 新 process 用例：失败请求经过 `A → E → A` 后再次请求，相同 key 累计到两次补正；步骤 8 之前停止，重跑无新 job/无新机会，原 jobs/失败原件字节保持。显式核原 7 节点、105 observed tokens、原 2000 tokens/60 seconds ceiling、不减少原消费、无正式审查原件。
3. 新 process 用例：配置 export-only delivery_policy 后，耗尽进入原 closeout，source_cutoff=5、actions 为空、无实际提交，重跑不创建第二个 closeout 或回滚 ledger。
4. 两个定向参数覆盖缺 subject 与 unsupported launcher；真实构建/封存 requester，再走 `request_route → semantic.effective_route → build_job`，确认只是普通 A。更换精确选中材料后 host key/root 改变，补正新计。launcher 分支仅用作者事实 stand-in 排除前一诊断优先级，**不证明真实作者身份或通过资格**。
5. 既有实际 home/session 形状的正式通过与作者重叠拒绝用例保留；没有新建模型、TCAD 或安装夹具。
6. 新增既有 decision 补正链负控：`continue_w` 缺科学决定声明生成真实 `a_decision_request_missing`；补正 A 转请求不可用审查后，原 root/reason 和已接受补正次数保留，下一份普通 A 仍通过原补正验证。此例不伪造成功资格。

这些 process 用例的 native/session 事件仍是本地脚本合成事实，不能代替真实 Codex 独立资格。新增 closeout 用例仅证明无 adapter 的未提交收口；未新增真实 adapter 交付、closeout 内反复 formal_review、真实模型/身份或外部副作用验收。原 live 实例的 frozen review contract 包含当前实现身份；本修复不重签旧合同、原件或资格。

## 静态检查与建议 root 执行

已执行 stdlib `ast.parse`：4 个生产文件、1 个测试文件及测试中的 LAUNCHER 字符串；限定文件 `git diff --check` 无报错。未运行 pytest/collect、项目 import、业务 CLI、安装/build、模型、HTTP 或远端作业；未提交。

建议 root 首先串行执行 `tests/research_loop/test_formal_review.py`（现 10 个用例实例，含现有正向/重叠负控）。如有具体剩余风险，再选择 `test_decision_contract.py::test_real_controller_clarification_is_bounded_and_not_counted_as_progress` 与已有 closeout 非法动作补正用例；不运行全功能或安装矩阵。资源边界与运行许可由 root 统一持有。

### root 首轮验证与夹具修补

root 串行验证报告：source 5 passed；process 4 passed / 1 failed。唯一失败为 `test_exhausted_unavailable_review_enters_existing_export_closeout` 的 prepare 夹具配置缺少交付策略必需的四角色 `node_budget_policy`；日志为 `.trial/authority_remediation_20261017/a2-process/batch-001/pytest.log`。失败发生在 `controller.prepare` 的原准入检查，尚未运行该用例的收口路径，不能称其已通过。

本次仅给启用 delivery_policy 的夹具补每角色 100 observed tokens / 5 seconds 原节点预算，总场仍为 2000 tokens / 60 seconds，closeout 原预留仍为 30 tokens / 1 second。没有修改生产检查或增加额度。静态 AST/diff 复核后重冻；由 root **仅重跑上述失败项**，此处尚无重跑结果。其余已通过九项不因该局部配置补齐而重复运行。

## 最终动态验证

独审见 [A2审查](A2_FORMAL_REVIEW_UNAVAILABLE_ROUTING_REVIEW_20261017.zh-CN.md)。使用 `/home/da/miniconda3/bin/python scripts/run_tests.py --config .trial/p_migration_validation_20261017/resources.json`，root唯一串行执行：

- source `test_formal_review.py`：5 passed / 5 deselected，监督2.515秒。
- process同文件：4 passed / 1 failed / 5 deselected，监督12.546秒；失败是fixture缺必需node_budget_policy，在prepare即拒绝。
- 只修测试配置，经独立复审后仅重跑 `test_exhausted_unavailable_review_enters_existing_export_closeout`：1 passed，监督3.496秒。其它配置未改变、不重复已通过项。
- 最终10个独立用例通过；原始日志 `.trial/authority_remediation_20261017/a2-source`、`a2-process`、`a2-closeout-retest`。三批峰值143675392字节（约137 MiB），无内存止损、清理全部完成。无安装、真实模型或远端作业；不证明真实身份资格或实际adapter交付。
