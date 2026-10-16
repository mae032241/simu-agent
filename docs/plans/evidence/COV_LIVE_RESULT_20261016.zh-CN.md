# 2026-10-16 cov 真实场：完成 H/W/A，候选审计工程失败，未确认交付

当前框架对应提交 `8ab844f422be16b5a5c9aa8a1876978af2426a90`；安装身份与场前门禁见 [准备证据](COV_LIVE_PREPARATION_20261016.zh-CN.md)。用户授权此场2,000,000 token／1,200秒，与generic独立场并发，由根统一共享serial_lock/run_one监督。没有重启、增加预算、修改科学输出或启动隐藏评分。

## 实际结果

**真实验收未通过。**三个模型科研节点均成功封存：H001→W002→A003。5次正式注册实验全部得到known_success回执；W002单次原生执行后主动review，没有观察到new_context fragment。A003明确暂选run-2并要求audit，尚未授权直接交付。候选审计实际执行后返回`engineering_error / audit_training_error / cleanup_confirmed=true`，控制停止为`engineering_repair_budget_unavailable`。没有交付确认，没有隐藏目标分数，`goal_completion=not_asserted`。

| 节点 | 配置模型／effort／tier | input | cache（已包含于input） | output | 合计tokens | 节点advance秒 | 返回 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| H001 | gpt-6.1-sol／high／default | 143,343 | 119,680 | 2,788 | 146,131 | 89.929 | experiment |
| W002 | gpt-6.1-sol／high／default | 695,170 | 595,712 | 8,699 | 703,869 | 250.874 | review |
| A003 | gpt-5.6-sol／high／default | 194,192 | 142,720 | 3,322 | 197,514 | 136.235 | audit run-2 |
| 总计 | 全部3节点／3attempts | 1,032,705 | 858,112 | 14,809 | **1,047,514** | — | unknown_steps=[] |

未缓存input为174,593，未缓存input＋output为189,402。缓存不重复计费到token合计。全部native outcome return0、stop_reason=null、cleanup=observed_group_cleaned；W超过650k软目标后以原结果封存，没有当作硬预算异常。整场driver单调计时483.175秒，控制active482.924458秒；预算余额952,486 token／717.075542 active秒。冻结输入末次核对完全未变。角色模型表为冻结job/intent/argv配置事实，不声称本报告独立审核了provider每次实际推理的模型别名。

## 正式实验与选择

| 公开run | public val_score | harness wall秒 |
| --- | ---: | ---: |
| run-1 | 0.9044 | 0.71 |
| run-2 | 0.9097 | 0.95 |
| run-3 | 0.8974 | 0.86 |
| run-4 | 0.1265 | 0.63 |
| run-5 | 0.8974 | 5.74 |

A003暂选run-2并明确要求官方honesty审计；该选择不能当作目标条件下最优或最终提交。25次多样实验、8次平台期、无泄漏提交与交付确认等原题停止条件仍未满足。公开验证分不等于隐藏covariate-shift分。

## 审计为何失败

精确原件：`instance-03/native-evidence/003/candidate-audit/{outcome.json,adapter-result.json,binding.json}`与`host-delivery/leaf-output/*-audit-1.audit.stdout`。候选已解析、实际隔离leaf审计已调用，外层进程return0，但harness报告audit unavailable；框架据事实保留engineering_error，没有把stdout中的submitted字样当作合格或交付确认。

冻结`source.py`原件SHA `3b22c03bc176e3fd520994e6f7e723f8373f38ac049c5e2978f5933cd44df871`第95–97行显示：`train()`将`screen_convex.json`和`hold_convex.pkl`诊断输出写到原W002/work的硬编码绝对目录。正式实验时该目录存在，隔离审计仅授予精确原件/harness/scratch，不挂原工作树；第一次write_text即FileNotFoundError。**这是写入诊断输出的父目录不存在，不是读取辅助训练数据失败。**不应通过暴露原W临时树或把隔离审计算作已通过来规避。

该范围仅证明此候选不可在当前交付隔离布局重训。一般多文件依赖闭包、任意模型可移植性不由本场授予；本次没有修代码或重放审计。submission根仅出现native自动创建的隐藏辅助目录，无正式模型/提交回执，且没有last_confirmed。

## 为何剩余95万token仍无法修复

`controller._repair_funds`（controller.py:775）要求完整维修W、随后A和外部交付floor都可容纳，实际计算为：

- tokens：W650,000＋A150,000＋floor200,000＝**1,000,000**；实际余952,486，少47,514。
- 时间：W480＋A120＋floor120＝**720秒**；实际余717.075542，少2.924458秒。
- 步数：余20≥要求4；unknown_steps=[]，execution_blocked=false。

所以停止由冻结的维修预留准入规则触发，两个额度条件均不满足，不是全场已耗尽、账单未知或一般20分钟超时。该检查当前对soft node模式也按完整目标额预留；这解释行为，不代表本报告已论证该策略是否适合小额真实场。没有自动降低目标、增加额度或重派W。

## 原始证据范围

本场持久目录为仓库`.trial/cov_live_20261016`：`final-result.json`、`controller.log`、`frozen-manifest-v3.json`，实际`instance-03`的各job/native-intent/outcome/usage/result-identity、calls和公开runs/results.jsonl均保留；计量来自原控制记录，不按mtime推算。双场共享资源监督原件由根保存，本文不把单场driver退出当作整个共享树已清理。尚未执行隐藏评分或原生对照，不复用本场科学解法到其他场。
