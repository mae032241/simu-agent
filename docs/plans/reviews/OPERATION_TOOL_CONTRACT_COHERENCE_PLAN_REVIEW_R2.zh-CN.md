# Operation 与工具契约一致性修复计划 R2 独立复审

日期：2026-09-11。结论：**PASS（工程计划审查）**。

R1 唯一剩余的清单职责冲突已在 R2 的接口协议中闭合。本次定向复核未发现新的同级阻断。计划足够具体，可以结束本轮计划修订与审查；此结论不代表代码已实施、测试或部署已通过，也不代表科研交接完成或外部执行获得批准。

## 1. 精确审查对象与范围

- 计划：`docs/plans/OPERATION_TOOL_CONTRACT_COHERENCE_REPAIR_PLAN.zh-CN.md`，R2，325 行。
- SHA256：`5e57817f2f4d6567276dc1738643ad60487c8bf0eb13305033f82c20258ce6b3`。
- 对照：`docs/plans/reviews/OPERATION_TOOL_CONTRACT_COHERENCE_PLAN_R1_REVIEWED_SNAPSHOT.zh-CN.md` 和 R1 独立审查报告；已核对 R1→R2 精确文本差异。
- 仓库：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`；HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`，工作树存在既有未提交修改。审查对象是上述确切计划，不把 HEAD 以来修改视为其实施结果。
- 本轮限于 §7.2 两类清单、同一 Artifact 的一次绑定、§8.1 尝试来源及 record_attempts 权限衔接。沿用前两轮已完成的相关源码审查，补核现有重复绑定、恢复生产者和工具证据权限分支；未扩展至无关框架审计。

## 2. R1 阻断的闭合证据

| 必须明确的决定 | R2 对应条款 | 复审判断 |
|---|---|---|
| 原文件恢复证明与上一轮分析证明分工 | §7.2，第 159、173 行 | TCAD recovery_manifest 保留原 receipt/执行证明；独立 prior_analysis_manifest 证明 prior_analysis 的映射与尝试。两者分别核对原 producer，不再要求两个不同生产者共用一份清单。 |
| 同一清单承担两用途时不重复绑定 | 第 161—171 行的绑定表 | 同一清单确为 prior_analysis 的同 producer 直接封存父件时，仅绑定 recovery_manifest 一次。显式错误配对拒绝，不静默回退；全局 input_artifact_duplicate 保留。 |
| 不扩大隐式读取和来源权威 | 第 173—177 行 | 不读未绑定父清单、不修改原 receipt 的 producer；来源按完整 ArtifactRef/lineage 匹配，旧别名使用隔离视图，不覆盖当前输入。 |
| 连续分析可接通 | 第 179 行 | 明确 A 恢复 F/MA→B 只计算并产生 MB→C 分别绑定 MB 与 MA；MB 可以没有接收 records，且不能冒充 F 的接收者。 |
| 失败尝试使用正确清单 | §8.1，第 219—229 行 | attempt 引用遵循 §7.2 的唯一用途选择；当前、历史可信与无收据历史仍分开，旧错误不升级为新工具确认。 |
| 负向验收和有限分析边界 | 第 179 行及 §8.1 验收 | 包含清单对换、错误 producer、缺证明和正式 preflight→tool→submit；有限报告不绕过已经拒绝的错误绑定。 |

源码交叉核对支持这些修订具有明确接入位置：

- `src/scidiscovery/operations/invoke.py:165–178` 当前拒绝重复完整 Artifact 和重复别名。R2 的单清单形状与这条不变量相容，无需放松全局准入。
- `plugins/tcad_artifact/tcad_artifact/result_analysis.py:73–85` 当前用 recovery_manifest 核对恢复文件的原 producer；`:202–214`、`:239–252` 读取原接收记录。R2 保留该来源职责，新增 prior 证明用途，不以后一轮清单冒充原恢复证明。
- `src/scidiscovery/artifact_agent/service/tool_evidence.py:122–147` 当前清单由本 Run 记录和父件生成。R2 §5.2 已明确允许 records 为空但 bindings/attempts 非空，并将快照纳入候选和主输出父链；无需重新接收 F 才能封存 MB。
- `src/scidiscovery/operations/tooling.py:265–269` 的现有清单/接收权限成对判断需要按计划调整。R2 末段明确 record_attempts 只开启控制侧尝试证明，不借用 evidence_ports 获得原字节接收或执行范围权限，解决了权限接线可能混同的实施歧义。

## 3. 累计审查结论

R0 的五项必要问题在 R1 中已有主体修复方案；R2 补齐了其中映射与失败证据的连续跨轮部分。现有计划同时覆盖实际 MCP 错误传输、类型化评分请求、案例映射生命周期、可信失败证据、预计算分析的实际成功门槛，以及通用分析生成 Schema 对内部证据键的正确处理。

这些决定不增加 Operation 注册权威、自动科研路由、映射审批阶段或通用工具成功状态机。精确来源、独立审查、执行批准、历史不可变性和完整成功条件仍保留。验收既包含真实案例的自主纠错与实际计算，也包含共享消费者和三轮交接的正式入口负例，未再依赖仅直接调用校验器的构造正例。

## 4. 非阻断实施提醒与未验证事项

- preflight、tool context、输出校验和重放应实际共用 §7.2 的用途投影；不得在四处分别实现近似选择规则。这是执行现有计划，不要求增加新机制。
- record_attempts、清单独立发布和新增输入/输出 Schema 的编译身份、资源预算及安装入口，应按计划中的定向检查验证。普通未声明 Operation 的权限和单文件行为保持原约束。
- 本轮未运行任何测试、目录编译、wheel 构建、安装或求解器，未调用科研工具或读取科研状态/原产物；真实 PLX 支持、实际数学等价性、部署与 P6 科研交接仍未验证。仅新增本审查报告，未修改计划、源码或他人文件。

本 PASS 仅适用于上列 SHA256 的 R2 工程计划。
