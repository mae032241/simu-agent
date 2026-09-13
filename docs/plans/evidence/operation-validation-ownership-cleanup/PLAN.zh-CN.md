# Operation 校验职责清理

2026-09-13。用户明确授权全面扫描并删除不合理的重复填表校验，同时处理导致连续拒绝的诊断缺陷。此次是源码修复，生产科研暂不继续；不重写旧成果或更改审批。

## 精确回归起点

Fig.4 新计划审查的6份失败提交已通过工具操作记录在内存中还原，未执行历史命令、未读取或转述 Agent 推理及科学结论。6份均在 `payload.findings[5].evidence_keys[1]` 引用 `current_progress_002`，而顶层 evidence 未再次登记该引用。该别名真实绑定 `fig4_morphology_objective_revision_4.output`。原始异常是 `scientific review finding references undeclared evidence`，之后被丢失为泛化 value_error，并套上误导性的 verdict_consistency 规则名。最终恢复草稿对应超时后改写，不能代替6份失败版本。重建最终 payload 与恢复副本一致。

原始诊断与重建证据保存在相邻 fig4-iterative-optimization 目录的 review-rejection-submission-replay.json；通用转换复现见 shared-diagnostic-probe-results.json。

## 实施顺序与边界

1. 从实际注册目录逐个检查 Agent/Transform/Effect、输入准入、输出内容/上下文、工具参数及嵌套模型，建立本轮覆盖表。旧审计只作线索，不能直接沿用已完成结论。静态扫描计数不能当作生产阻断数。
2. 删除把同一来源、引用列表或控制层已知事实要求 Agent 重复登记/复制的阻断。在现有来源绑定边界核验实际使用的引用，保持已绑定来源可引用、未绑定来源被拒绝；引用的科学支撑性继续交给科学角色。保留主对象身份、真实执行/案例/参数对应、数值运算必要条件、不可变记录和精确审批。
3. 修复已知校验失败的具体原因与字段在转换中的损失，检查普通 ValueError、无详情 SemanticRuleViolation 和普通 diagnostic dict 三条路径。工程异常仍归工程故障；不把任意程序异常转换为要求科学 Agent 改答案。对实际删除的规则不再增加说明或提示词来延续重复填表义务。
4. 串行低资源验证：覆盖本次合法引用无重复登记的正例、虚构来源负例、已保留数值/身份约束的精确诊断，以及共享 Schema/Operation/Worker 提交路径。沿实际影响面补齐检查；不以全量测试替代具体回归，不同时运行多个测试进程。
5. 更新本轮删除/保留/职责移位清单、工程验证与原迭代问题记录。明确未部署和真实科研仍待安装后续接，不把源码测试当作仿真结论。

## 基线与资源

HEAD 为 be5da77，修复前存在历史资格兼容改动。以 baseline.json 记录的脏工作树快照作本轮比较，保留所有已有改动。不另建 Operation、状态机、来源注册表或通用依赖图，不扩大到新的平台集成。

每次只运行一个受控测试进程；地址空间和进程树内存上限均512 MiB，CPU120秒、墙钟150秒，BLAS/OMP单线程。必要时拆分定向检查组，禁止并行测试和真实求解。
