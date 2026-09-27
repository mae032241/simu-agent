# R5-G 直接完整对象修订 D2 独立实现审查

日期：2026-08-30  
审查范围：D2 曲线实验修订、未知盲插件、实际消费者与安装态迁移  
审查者：未参与本轮实现的独立审查者

## 结论

**通过。只放行 D3。**

D2 已把最后两个实际消费者迁到“精确旧对象 + 精确修改请求 → 原专业 Agent 输出完整新对象 →
全新独立评审”的路径。曲线实验修订复用原实验 Agent、工具、工作区和提示资源；未知插件只通过
自己的 `scidiscovery.plugins` 声明完成完整对象修订。真实 Root/Worker 生命周期证明旧评审不能
作用于新对象，同 Schema 附件不能晋升为主对象，clean-wheel 能发现未知插件声明。

未发现按 Operation id、Schema、插件、角色或端口名增加的核心分派，也未发现第二注册表、持久
状态、资格权威或兼容入口。旧 apply/receipt 类型、实现和 support Operation 仍在目录中，但当前
评估脚本、冻结夹具和直接修订 Agent 已无实际消费；它们严格属于计划已冻结的 D3 删除对象，不能
据本结论继续保留到发布完成。

## 跨边界核验

### 1. 曲线实验修订闭包

`plugins/curve_score/curve_score/science_operations.py:136`—`:145` 的编译提示明确区分首次设计和
修订：修订返回完整 `ExperimentPortfolio`，禁止补丁和继承 verdict。声明 `:412`—`:440` 与首次
设计使用同一 `experiment_agent`、`experiment_prompt`、通用 science workspace 和同一基础 Worker
工具；输出是一个完整 `experiment_plan`，复用原 Schema、validator、semantic contract 和
`science.object.review.v1`。

工程/科学边界保持有界：旧计划与 `ScientificReview` 必需；科学 foundation/objective/portfolio/
critic 四项共用同一可选 cohort。Root 的通用 cohort 门保证全有或全无，foundation 仍需原批准；
`experiment_science_cohort` 复核四者父关系；完整计划 context validator 对 scientific plan 再要求
objective 和 hypothesis，并检查目标键、假设键和 mandatory target。engineering plan 可以不绑定
科学 cohort。没有领域条件进入 Root。

`tests/operations/test_curve_score_operation_plugin.py:305`—`:331` 冻结完整对象结构以及 Agent、
workspace、prompt、tools 复用；`:334`—`:454` 真实经过 Root invoke、Task/Worker 文件生命周期、
完整输出 validate/finalize 和新 reviewer。新对象父链包含精确旧计划和修改请求；旧 review 用于新
对象的下一次修订时以 `input_change_request_mismatch` 失败，新对象必须获得新的 review。

### 2. 未知插件通用性证明

`tests/fixtures/plugins/producer_family_operation_plugin/blind_producer_plugin/plugin.py` 只有一个
`PluginDefinition`。初始 Transform 仍产生一个主对象和两个同 Schema 附件；插件自行声明 reviewer；
`blind.domain.revision.propose.v1` 是 Agent，输入用途仅为 `revision_base` 与 `change_request`，输出
单一完整 `blind.object.v1` 并重新声明同一 reviewer。fixture 已无 patch、apply、delta、change-log
Schema、组件或 Operation；runtime 提示也明确禁止补丁和 verdict 继承。

`tests/operations/test_r5_blind_producer_family.py:205` 起的真实链经过 Root、Worker claim/materialize、
受控写入、validate/finalize、新 review 和 Approval projector。它证明：

- 初始对象审批必须带齐同一生产者族附件；
- 修订对象不伪造旧 sibling family；
- 初始 pass review 不能批准修订对象；
- 新对象经新的精确 review 后才可进入审批；
- 同 Schema 附件即使另建 review，也因不是冻结 review subject 而在真实 Root 准入失败，且不创建
  Task；
- clean-wheel 从唯一 entry point 编译并发现 produce/review/revision，且真实 invoke 初始 producer。

clean-wheel 没有复制完整 Worker 生命周期符合冻结合同：安装探针验证发现和入口，源码态测试负责
一次完整生命周期，未引入第二测试运行器或产品分支。

### 3. 资格、父链和来源

`direct_revision_ports()` 只读取编译后的 executor/consequence、输入用途与基数、单输出的 Schema、
媒体、codec/schema-resource 和 ReviewSpec 结构。Root 仍通过唯一
`_validate_producer_output_admission()` 执行输出用途、冻结 review 合同和精确 subject-review 关系；
`change_request` 使用 TaskService 原有精确 reviewer 查询且 `accepted_verdicts=None`，因此 revise、
blocked 或 pass 只说明修改来源，不给新对象资格。

新 Artifact 的直接父链保留旧对象、change request、科学上下文和任务指令。生产者族的
`evidence_sources` 仍只按声明的 evidence usages 投影，不把 `revision_base`、`change_request` 或
`prior_signal` 当事实证据。旧评审不能通过普通 producer admission 被新对象继承；同一实例、输出
用途和冻结 producer identity 的既有门均未放宽。

### 4. 消费者、目录和入口

定向 `rg` 证明：

- `scripts/r5_g_science_chain.py`、`tests/fixtures/r5_e2e_tcad/manifest.json` 和未知插件夹具不再引用
  `revision_diff`、`unchanged_evidence_receipt` 或旧 apply Operation；
- 模型实际使用的 `roles/scheduler.md` 只要求从唯一 compiled catalog 选择并 preflight/invoke，不
  指挥旧补丁链；Agent 的实际 prompt 来自编译资源，而不是角色名分派；
- 旧协议命中只剩 D3 待删声明/实现、相应遗留协议测试、`roles/common.md` 的迁移期 Worker 分支及
  只读历史基线；没有当前脚本或新 Agent 输出声明 `revision_base_port`；
- `src/scidiscovery` 没有新增 experiment/blind Operation id、Schema 或插件名分派；唯一目录仍为
  `scidiscovery.plugins` 和一个 `CompiledCatalog`。

四目录冻结结果由当前全仓安装态测试复核：core-only 是 `builtin + general_science`，而不是单独
编译零 Operation 的组件包；其 15 项 Operation 与历史 R3/安装入口定义一致。full 为 49 项，
full+InGaAs 为 50 项。把首次“纯 builtin”探针失败归类为验收定义错误是合理纠正，候选没有为其
放宽 `component_unused` 或新增目录例外。

## 奥卡姆与阶段边界

D2 没有新增修订实体、manager、session、policy、表、缓存、注册表或状态机。生产净增 5 行来自
曲线声明迁移，仍在 D1 已审查的 40 行临时重叠内；核心计量不变。其价值是删除两个实际旧链消费
者，而不是把同一责任横移成新服务。

当前 `roles/experiment_designer.md` 仍保留一段旧“structured revision”文字，但仓内没有代码、
entry point 或生成器读取该文件；编译后的 curve experiment prompt 已由插件资源替代，因此它不是
D2 运行消费者。本文件作为安装包中的死资源仍可能误导人工阅读，D3 删除协议时应与
`roles/common.md` 和 MANIFEST 一并执行零命中核对。该项不改变本轮运行语义，记为非阻断清理。

科学型 experiment revision 的“缺完整 cohort”目前由通用 cohort 门、父关系 guard 与已复用的
context validator 三层共同失败关闭；D2 专项只显式断言 cohort 结构，未再复制一个完整科学对象
生命周期负例。代码路径明确且全 Operation 回归覆盖这些通用门，因此本轮不把重复测试缺失列为
阻断；D3 最终删除回归宜加入一个精确 scientific missing-cohort Root/Worker 负例，以冻结集成行为。

## 独立复测

每条测试命令均严格串行，并先设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

结果：

1. curve 完整修订 2 项 + blind 主链/附件/clean-wheel 3 项：`5 passed in 31.60s`；
2. `pytest -q tests/operations`：`272 passed in 97.62s`；
3. `pytest -q`：`309 passed in 100.11s`；
4. `python scripts/r5_current_metrics.py`：生产 Python `143/60313`，operations 包 `7/2097`，Root
   聚合 `3146`，TaskService 聚合 `6221`，与实施记录一致；
5. `git diff --check`：通过；D2 关键生产/测试文件 `python -m py_compile`：通过；
6. 当前安装态/冻结基线回归复算 core-only/full/full+InGaAs Operation 数为 `15/49/50`。

这些测试不等同真实科学 Agent、solver 或人工 UI 科学效果；D2 的完成门是协议消费者迁移和通用
生命周期，不应把未来 D4/R5-G 科学观察错误写成当前通过证据。

## 放行边界

只放行 D3“原子删除旧补丁协议并完成发布回归”。D3 必须删除旧 apply/receipt Operation、Schema、
Task/Worker patch 分支、Root 递归生产者族逻辑和迁移期提示，并把直接修订结构升级为 catalog 硬门；
不得以本报告宣称 D3、D4、R5-G 或 R5 已完成。
