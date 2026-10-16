# 通用候选登记与选定成果交付

范围：基于 `6677310` 的未提交修改。该报告补充同日 [generic inverse 工具验收](GENERIC_INVERSE_TOOL_ACCEPTANCE_20261016.zh-CN.md)；原报告的执行、归档结论仍有效，其“通用候选与交付尚缺失”描述的是本次修改前状态。本次只授权开发与无模型验收。

## 根因与实现

本地执行已保存明确的指标、成果、输入与终态，`history` 的无领域 observer 分支却固定登记空候选。既有 lineage、selection、shortlist 与交付账本可以通用复用；缺口在结果到候选的投影，以及所有交付均默认要求领域 resolver 与 audit。

`artifacts/result.json` 保持 version 1，增加可选领域结果元数据：

```json
{"candidate":{"label":"operator_ridge","metric":"public_target_stress_mse","artifact":"artifacts/predictions.json"}}
```

`metric` 必须精确指向已声明且具备 `evaluation_key`、`direction` 的有限指标，`artifact` 必须精确指向已声明且已保留的输出。多个指标而未声明候选时只记录测量，不自动选择指标。无效声明保留原进程成功/失败事实与原始文件，但结果标为 invalid；失败或未知进程不登记成功候选。

控制层从精确 scope 与 call_id 生成稳定候选身份，投影到已有 candidate 对象。作者不填写身份、摘要哈希或提交封装。候选保留所选指标口径和方向，其他指标继续保留在实验索引及原件中。可选领域 observer 为空或不可用时，通用登记仍从自己的密封执行原件进行；不借用 observer 的科学资格。

`generic_results` 从同一候选的密封 managed call 解析 accepted 输入清单、完成记录与成果。它不按文件名、时间或“最佳指标”搜索实现。`delivery` 将这些精确原件交给既有选择、intent、outcome、confirmation 与预算链。A 仍只作科学选择并给出局限。

新增 `generic_delivery` 目录适配器，通过现有 descriptor 接口配置目标。控制层在真实 bwrap 命名空间中写入一个以 operation_id 命名的独立目录，包含 `artifact`、`inputs/`、`outputs/` 和复现说明；完整目录原子提升后确认每个成果摘要。只有 promotion 可写目标，confirm 只读；输入、adapter 和运行时均按既有冻结机制校验。目标不得暴露控制根目录。

## 可选能力与 cov 边界

descriptor 可显式声明 `capabilities`。通用目录适配器声明空列表，表示不提供领域 audit 或 smoke；shortlist 保留中性的未配置/未提供状态，不伪称通过检查。旧 descriptor 缺该字段时仍保持必需 audit。显式请求 `candidate_audit_policy` 而 adapter 缺 audit 时，prepare 在创建实例前拒绝。

cov 的执行、评分、领域原件解析、审计和外部双目标提交语义保留，`cov_delivery.py` 未改动，也未删除旧入口。它与目录交付共同复用现有通用选择和交付账本。目录确认的 note 明确是 `exact_local_directory_delivery_confirmed`，只证明指定本地目录成果已交付，不表示远程服务提交或科学目标完成。

工程不确定性不映射为科学拒绝。promotion 或 confirmation 响应丢失后，只允许既有预算内的 confirmation，不重复 submit。发现不确定 `.pending-*` 目录时不覆盖；确认不能证明完成则保持 unknown。已完成确认重读复用原 sealed outcome，不产生新 leaf 调用。

## 验收范围

真实 research CLI 使用默认 `local_execution:command` 执行两个候选和一个显式失败实验，A 读取正式成果，通用 shortlist 登记比较并选定候选，控制层隔离交付并确认。验收随后仅从已交付的 inputs 与复现说明重新执行，逐字节比较全部 outputs。覆盖响应丢失、目标冲突、重复确认、指标歧义、跨 scope 身份隔离、必需审计缺失和可选 observer 故障。

检查均通过 `scripts/run_tests.py` 的 serial_lock/run_one 资源监督执行。最终命令、结果与文件摘要记录于 [机器记录](GENERIC_CANDIDATE_DELIVERY_20261016.json)。没有运行全套平台矩阵、付费模型、真实科学任务或网络 solver。

| 检查 | 结果 |
| --- | --- |
| 当前 generic/local/delivery/cov lineage/control selection 源码边界 | 140 passed、2 skipped；跳过项需要另行提供原始 cov public harness/runtime |
| 额外旧 history 文件 | 11 passed、14 failed；隔离 `git archive 6677310` 上同样 11 passed、14 failed，失败 node IDs 完全一致，均为旧接口/旧路径预期 |
| 新离线 wheel、独立 venv、`python -I` 同一 generic 用例 | 14 passed，37.51s；241 个安装包原件与冻结构建源逐字节一致 |

源码合并检查为 151 passed、14 failed、2 skipped，167.86s，不能表述为全量通过。wheel 构建/安装监督 2.630s，安装检查监督 38.269s；资源监督均完成清理且未触发内存保护。一次既有 watchdog 测试缺少 cleanup 文件，后续原样复核及最终源码检查均通过；保留早期日志，不将其归为本次修复。`git diff --check` 通过。

科学限制：H/W/A 为脚本化 transport；本次证明框架登记、选择绑定、精确成果交付与恢复，不证明模型科学推理。两个评价口径均公开，不使用隐藏分数。search 关闭，mechanism_binding 仍为 null；不虚构 H 机制来源。`goal_completion` 保持 `not_asserted`。
