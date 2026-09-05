# R5-G 运行前预算修订独立审查

日期：2026-08-30  
审查者：未参与本次修订的独立审查者  
结论：**通过**

## 1. 审查边界

本轮只审查任何 R5-G 科学结果产生前，对冻结比较预算中模型字段的纠错。审查不重新评价已冻结
任务、来源、量表、拓扑、工具、token 或墙钟预算，也不提前运行或评价 R5-G 科学效果。除本报告
外，审查者未修改生产代码、测试、冻结清单或计划状态。

## 2. EvidenceAudit

### 2.1 来源声明

- S1：`docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 4.2、11、15 节；
- S2：`docs/plans/R5_0_BASELINE_AND_DELETION_INVENTORY.zh-CN.md` 第 5 节当前修订；
- S3：`tests/fixtures/r5_e2e_tcad/manifest.json`、`task.zh-CN.md`、`rubric.json`；
- S4：当前 general-science 与 TCAD 插件的九个必需 Agent `OperationSpec`，以及
  `operations/catalog.py`、`platforms/codex.py`；
- S5：`tests/operations/test_r5_frozen_baselines.py` 与本轮 clean-wheel 专项输出；
- S6：R5-0 三轮历史独立审查，仅用于确认原冻结边界，不继承其结论到已修改预算。

### 2.2 检查记录

| 检查键 | 结论 | 证据 |
| --- | --- | --- |
| `amendment_needed` | 通过；原 `gpt-5.6-sol` 与九个不可变编译 Agent 的 `gpt-5.4` 冲突，若不修只能非法覆盖生成配置 | S2、S3、S4 |
| `pre_result_timing` | 通过；当前没有 R5-G 科学输出，修订发生在两臂运行和评分之前 | S1、S2 |
| `two_arm_fairness` | 通过；两臂均改为 `gpt-5.4/high`，其余输入、工具、token、墙钟、容差和量表未变 | S2、S3 |
| `single_authority` | 通过；多 Agent 模型按精确 OperationSpec 映射，禁止补丁生成 profile；没有新增配置权威或调度覆盖 | S3、S4 |
| `current_mapping_correctness` | 通过；当前九个 mandatory Agent id 与九个预算键一一相等，所有 clean-wheel 编译模型和单 Agent 模型均为 `gpt-5.4` | S3、S4、S5 |
| `drift_test_completeness` | 通过；预算键集合精确等于 mandatory Agent id 集合，模型集合与单 Agent 闭合，并以直接索引逐项核对 clean-wheel 编译模型 | S5 |
| `frozen_content_integrity` | 通过；19 项输入、task、rubric 和 replay plugin closure 摘要均匹配，任务/量表摘要未因预算修订变化 | S3、S5 |
| `associated_truth_updates` | 通过；R5-0 记录精确纠错，R5 总计划仍用“相同模型等级”表述且无矛盾；历史审查无需改写 | S1、S2、S6 |
| `scope_and_occam` | 通过；只改一个预算对象、一个冻结事实说明和拥有者测试，没有新增生产实体、注册表或状态 | S2、S3、S5 |

## 3. 判断

### 3.1 修订是必要纠错，不是运行后调参

当前 `ExecutorRef.model` 是 OperationSpec 编译身份的一部分，生成 Agent profile 也必须与同一
compiled catalog 相等。九个必需 Agent Operation 当前全部声明 `gpt-5.4`。保留原清单中的
`gpt-5.6-sol` 有且只有两种结果：实际运行违反冻结预算，或评估器覆盖编译后的 Agent profile。
前者使比较无效，后者破坏 R5 的单一 Operation 权威。因此应把预算修正为产品实际可运行的
`gpt-5.4`，不应为了维护文字冻结而修改九个生产 OperationSpec。

修订发生在任何科学输出、评分或两臂观察之前；两臂同时采用同一模型，reasoning effort、原始
输入、领域工具、120000/60000 token 上限、7200 秒墙钟上限以及 10%/20% 对照容差保持不变。
这保持相对公平性，也使 R5-G 测量当前真实产品而不是临时评估配置。

`model_authority=compiled_operation_spec` 对多 Agent 一路的含义由逐 Operation 映射和禁止 profile
补丁明确限定；单 Agent 并不伪装成编译 Operation，只采用同一模型等级。R5-G 仍必须记录两路
实际模型和 reasoning；任何实际值不符应使该次运行无效，而不能在看到结果后修正预算。

### 3.2 映射完整性阻断已关闭

首轮候选的 clean-wheel 测试曾使用：

```python
expected_model = budget["multi_agent_models"].get(step["operation_id"])
if expected_model is not None:
    assert operation["model"] == expected_model
```

它只能证明“已经写入映射的键值正确”，不能证明预算完整描述全部九个必需 Agent：

- 删除任一必需 Operation 的预算键，`get()` 返回 `None`，比较被静默跳过；
- 加入一个不存在或非必需的 Operation 键，没有消费者会检查它；
- 单 Agent 的硬编码断言没有证明其值等于多 Agent 映射的唯一实际模型集合。

当前修复先计算 mandatory Agent id 集合，并断言预算映射的键集合与其完全相等；因此遗漏和额外
预算键都失败。随后断言多 Agent 模型值集合精确等于只含 `single_agent_model` 的集合，并对每个
mandatory Agent 用直接索引核对 clean-wheel 编译目录返回的模型。非 Agent executor 会返回
`None`，同样无法通过 `gpt-5.4` 比较。当前两侧均为九个唯一 id，全部模型为 `gpt-5.4`。

## 4. 修复范围复核

修复只修改 `tests/operations/test_r5_frozen_baselines.py` 的现有 clean-wheel 模型断言：

1. 从 `mandatory_agent_steps` 计算精确 operation id 集合；
2. 用集合相等拒绝遗漏和额外预算键；
3. 用模型集合相等绑定单 Agent 模型；
4. 用直接索引核对每个 clean-wheel 编译模型。

没有修改生产 OperationSpec、manifest 当前值、任务、量表、token/墙钟预算、插件、调度器或新增
预算 Schema，也没有增加平行预算权威。修复严格落在首轮要求的最小测试边界内。

## 5. 独立验证

```text
pytest -q tests/operations/test_r5_frozen_baselines.py
=> 首轮候选 7 passed in 39.85s
=> 修复后独立复审 7 passed in 33.77s

git diff --check（本次三个候选文件）
=> 通过

冻结文件/任务/量表/replay closure 摘要复算
=> 无不匹配

当前 manifest SHA-256
=> 805545064dd4ffa8607c89bf22573d4a1dd4c4c33bc2d7814d7d914877a41238
```

专项当前同时证明冻结输入摘要、预算映射完整性和安装态目录模型一致；源码审查确认不再存在
`.get()` 跳过路径。

## 6. 门禁结论

**结论：通过。**

预算从 `gpt-5.6-sol` 修正为两臂 `gpt-5.4/high` 是运行前必要、诚实且公平的单一权威纠错；任务、
量表和其他预算没有被重开。首轮唯一缺口已由精确键集合、单/多 Agent 模型闭合和 clean-wheel
逐项直接比较关闭，且没有扩大修复范围。**现放行 R5-G 科学运行；不继承任何科学效果结论。**
