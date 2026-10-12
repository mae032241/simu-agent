# T0 独立设计审查

日期：2026-10-12。审查者：`/root/n1_runtime`；独立于设计与测量作者。

## 结论

**PASS：仅限 T0 设计、责任划分、测量解释和合成语义夹具冻结。无剩余设计阻断。**

本结论允许 T0 收口并按冻结范围实施 T1；不授予尚未实现的 wrapper、统一投影、T3 搜索效果或 T4 科学评估能力生产资格。本次没有运行测试、科研模型、训练或评估器，没有修改生产源码、真实实例或预算，没有提交。

## 精确审查对象

源码基线：`287b2e26478a2c563a7ae2c41cb34cd10e6512e0`。

| 对象 | SHA256 |
| --- | --- |
| `docs/plans/ROOTLESS_T0_LINEAGE_DESIGN.zh-CN.md` | `00f7a64ded7dae4457a9cfef5253d63c3a9b7062664f477281641f2e7c49e337` |
| `docs/plans/fixtures/rootless-lineage-v1.json` | `78f4d4b3bc79f59a3e3b73d49e66ec30c80ffa21de877dcd8d203ea850196177` |
| `docs/plans/evidence/ROOTLESS_T0_MEASUREMENT_20261012.zh-CN.md` | `caf09039d43508b3dd17b69100145e9857de22a21eed141fc204c559a8741b82` |
| 外层 `.trial/t0-design-20261012/measurement.json` | `90e14eaa030214b848037c3bdbf9762d4530d52b01e49d9790df61e4d4f0dba6` |

最终设计119行，合成夹具12例。已读取最终全文、夹具及测量归档，并复核最终 SHA。父代理此前文档结构检查仅证明链接、JSON与边界声明的静态一致性；其11例旧快照不能冒充最终12例产品测试。

## 关键边界

1. **单权威可落实。** 原 job/seal、成功 execution attempt、observer 原件、selected receipts、control-ledger 与 delivery 动作保持权威。新增 lineage 只读、可重建，不另存余额、资格、当前 attempt 或科学处置状态。低层原件读取→关系/机制 fold→render 单向；明确禁止 fold 回调现有重建入口形成环。函数迁移表与新路径删除证据足以约束 T1/T2，旧 renderer 仅作冻结兼容。

2. **关系不冒充科学证明。** 派生、复用、支持分栏；可见父输入、H 观察范围、候选推荐、代理最高和附件名不能推导父方案。`declared` 只说明作者意图与执行归属，不证明算法因果使用或结果正确。未知旧来源保留 unknown；科学资格不沿父边继承。

3. **唯一 B 入口实用且足够薄。** 实际 launcher→exp_cli→runner 接口没有 request key 或 run 恢复。新领域 wrapper 只增加科学父方案名称/显式新建和可选改变意图，委托原 run 一次；自动冻结调用上下文，以同调用 stdout 完整 row、脚本及产物原件绑定。禁止以台账差分、最新行或文件名替代回执。节点锁不重取实例 writer，不新建 executor 或预算；故障缺回执保未知、不重发，不要求未知必能恢复。该方案能够为未来运行产生可追溯 P→Q 与回退 P→R，而不是仅把全部候选标未知。

4. **最终唯一发现已解决。** 原 runner 在训练失败时仍输出完整 failed row 并退出1。最终第3节及 `exact_failed_row_is_known_failure` 明确：精确回执、进程退出和清理可确认才是 known failed；保成本/诊断，无模型资格，可在原科学范围和剩余额度内有理由修复，但不自动重试。仅 transport、缺回执或执行不确定为 unknown。此前“异常即 unknown”的过宽措辞已消除。

5. **无新的机械填写。** 模型只作科学父方案选择，不手写 hash、路径、调用ID或逐候选关系数组。省略父方案为未知，显式 null 为新建，与 implementation_selection 的 null carry 分开。复用仍走原 immediate-hop/null/clear/replace；名称缺失或歧义只阻依赖调用，保其他科学结果，不静默 fallback。科学协议8保留；host/plugin合同v2提供真正执行选择面，当前不需要空升9。

6. **旧协议与 N6/N6c 不被投影侵入。** 新布局由新冻结 host marker 选择；旧无 marker 的1..8 job/schema/task/seal保持原解释。成功 continuation 读取集中 execution 接口，不回落初次失败 raw。未知外部执行、计量、额度、repair/author root、N4 trigger/ack、收口 slots 和交付资格继续由原规则负责。未来 rollout 回退不得改已冻结 marker 或原封存对象。

7. **默认工作集与全集可达同时冻结。** 合并谱系 brief≤4096 UTF-8字节；按行数和实际字节双限分页，候选/实现17项及节点9项仍可读，不复制全部祖先附件。容量、截断、遗漏与原件入口明确；缓存删除能重建但不能替代原始观察原件或降低完整性门槛。

8. **A 的科学责任充分保留。** 现有 progress verdict、科学正文和 limitations 足以表达全局贡献、负结果、代理盲区、适用范围与未知；控制只绑定真实被评原件和去重，不把 raw 新身份当 verified science。N4 科学计数、sticky pause、exact ack 不由候选数或分叉清零。T4 不把 proxy 胜者、A 推荐和实际提交混为一槽，不跨未知评估组造排名或目标总分。

## 测量所支持与未支持的范围

- 已有 W 用量、响应输入、工作包 bytes 和公开调用顺序支持先统一摘要/原件读取，并由原生 W 在有界范围中按观察选择下一实验。live02已有局部细化与保留旧候选的事实，不需先增加辅助者系统。
- 小历史包仍伴随约76K响应输入峰值，因此不能把上下文增长全归因于历史；UTC阶段时长不是 active 预算，bytes不是token，协议与恢复条件不同的两场不是效率对照。
- 辅助者启动、独立上下文、名额释放和成本未资格，最终首版 T3 明确禁用，已从依赖移除。
- 92候选隐藏结果只供事后开发诊断，不回灌科研模型、运行选择或阈值调参。缺 audit 不能制造 leakage=false；历史记录审计不自动绑定当前模型。当前证据不能承诺 T3/T4 提高正式分数或效率。

## 后续产品门禁，非当前阻断

T1必须以实际新 wrapper 验证正常/已知失败绑定、丢 stdout、身份失配、accepted 后崩溃查询不重发、节点锁与真实 lifecycle；静态 JSON 不能替代这些门禁。T2必须验证 joint brief、分页完整性、成功 attempt、全角色旧8字节兼容与没有第二份装配。T3/T4效果、公开规则回测和独立科学验收尚未执行。各节点独立差异、定向/安装验证和独审，超过冻结规模须说明新职责。

**最终判定：设计范围 PASS；零模型、零产品测试，不宣称未实现能力通过。**
