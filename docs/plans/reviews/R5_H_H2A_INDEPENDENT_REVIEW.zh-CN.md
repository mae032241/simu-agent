# R5-H / H2a 独立审查报告

审查日期：2026-08-30  
审查对象：H2a——将通用实验 Operation 与组件所有权从 `curve_score` 迁入
`general_science`  
审查角色：独立审查者  
最终结论：**通过，仅放行 H2b**

## 1. 审查边界

本次只审查 H2a，不实施或提前验收 H2b。审查依据包括：

- `docs/plans/R5_H_MINIMAL_CLOSURE_IMPLEMENTATION.zh-CN.md` 第8节与第16节；
- `docs/architecture/SCIENTIFIC_AGENT_DESIGN_CHARTER.zh-CN.md`；
- `docs/architecture/SCIENTIFIC_AGENT_CONSTRAINTS.yaml` 的33项稳定约束；
- `general_science`、`curve_score`、`builtin` 和 `tcad_artifact` 的插件定义、
  Operation 声明、组件声明、编译器边界以及实际 wheel 入口；
- 通用实验、完整对象修订、独立审查、曲线诊断、TCAD 消费者和安装入口测试。

本次不把以下问题误判为 H2a 已解决：核心实验合同仍引用曲线 Schema/算法，且
`curve_score` wheel/插件仍依赖 `tcad_artifact`。二者都是 H2b 的明确输入。

## 2. 第一轮发现与修订

第一轮没有发现生产实现阻断，但发现两项当前文档失真：

1. 中英文 `curve_score` README 仍声称插件只发布六项 `support` Operation，遗漏两项
   曲线诊断 `public` Operation 和一项诊断知识投影 `support` Operation；
2. 约束 `PLG-001` 的证据仍声称曲线插件注册通用科研 Operation，与 H2a 当前实现不符。

上述问题已仅通过文档修订关闭：README 现在准确声明九项目录及其所有权；`PLG-001`
保持 `known_issue`，但证据只保留核心曲线 Schema/算法泄漏并指向 H2b。复核未发现用
文档掩盖实现缺口的情况。

## 3. 核心结论

### 3.1 真实基础 wheel 已形成通用实验结构闭环

干净安装的基础 wheel 只通过 `scidiscovery.plugins` 发布 `builtin` 和
`general_science`。该环境中不存在可导入的外置 `curve_score` 或 `tcad_artifact` 包，
但仍能编译17项 Operation，并解析以下结构链：

```text
science.experiment.design.v1
  -> science.experiment.materialize.v1
  -> science.object.review.v1
```

物化输出 `scidiscovery.experiment-portfolio.v1` 与审查输入严格相同；物化 Operation 的
编译 `ReviewSpec` 精确绑定 `experiment_plan`，审查者仍是独立 Agent Operation。该结论
来自实际 wheel，不依赖源码 checkout 的默认完整插件夹具。

### 3.2 六项通用能力具有唯一所有者

以下六项 Operation 均由 `general_science` 直接拥有，且基础目录无需曲线或 TCAD 插件：

- `science.experiment.design.v1`；
- `science.experiment.revise.v1`；
- `science.object.review.v1`；
- `science.objective.project.v1`；
- `science.experiment.materialize.v1`；
- `science.knowledge.update.validation.v1`。

`curve_score` 的科学 Operation 只剩两项真实曲线诊断和一项基于当前曲线诊断合同的知识
投影。完整目录仍为43项，因此本次所有权迁移没有通过删除能力制造表面解耦。

### 3.3 跨插件组件边界正确

曲线诊断对通用 workspace、受控文件工具、实验/审查 Schema，以及诊断知识投影对通用
知识 reducer/Validator/Schema 的引用，都同时满足：

- `curve_score` 显式声明对 `general_science` 与 `builtin` 的依赖；
- `ComponentRef` 明确携带组件所有者；
- 被引用组件在编译结果中全部标记为 `public=True`；
- 组件实现没有被曲线插件复制、别名注册或二次拥有。

目录编译器仍对未声明依赖和非公开跨插件引用失败关闭。未发现第二组件注册表、代理目录或
按插件名称写入核心分派的做法。

### 3.4 门禁、审查、修订和工具能力没有回退

- 实验设计保留 `experiment_science_cohort` 父链 Guard，并要求精确的
  `scientific_foundation` 资格批准来源；
- 计划物化保留 `experiment_lineage` Guard 和对完整 `experiment_plan` 的独立审查边；
- 实验修订仍以 `revision_base` 加 `change_request` 产生完整新
  `ExperimentPortfolio`，保留完整科学上下文 cohort Guard，不继承旧审查，并重新触发同一
  独立审查 Operation；
- Agent Operation 仍具有 assignment materialize、受控文件创建/修补、输出校验、最终化和
  heartbeat 工具；曲线误差诊断另外只获得声明的确定性曲线分析工具；
- 目标投影、计划物化和知识更新仍是确定性 `support` Operation，没有把科学优先级或结论移入
  Transform；
- 未新增审批捷径，科学资格和执行授权边界未被 H2a 改写。

这与 `AUTH-003`、`LIN-002`、`ROLE-001/002`、`DET-001/002`、`PLG-001/002` 和
`SEC-002` 的本阶段适用要求一致。33项约束中的其他 `pending_review` 或 `known_issue` 状态没有
因 H2a 测试数量而被擅自提升。

### 3.5 复杂度判断

实现没有为 `general_science` 再造独立 wheel、代理 PluginDefinition 或第二注册入口。新增的
两个模块分别承载声明和组件实现，并仍由 `general_science_plugin.py` 单点组合；曲线科学模块从
1,029行缩减到579行，责任已收窄。没有发现为特定测试增加的插件名分支、隐藏目录或重复组件
实现。本次拆分增加的是清晰所有权边界，不是新的运行权威。

## 4. 独立验证证据

所有测试均以串行方式运行，使用 `ulimit -v 7340032` 和 `MALLOC_ARENA_MAX=2`，未超过
8 GiB 约束。

1. 真实 wheel 目录入口：

   ```text
   pytest -q tests/operations/test_catalog_installed_entrypoint.py
   7 passed in 38.16s
   ```

2. 通用科研、通用变换、曲线、TCAD、约束矩阵、InGaAs、R4 审批与执行身份聚焦回归：

   ```text
   pytest -q \
     tests/operations/test_general_science_plugin.py \
     tests/operations/test_general_transform_operations.py \
     tests/operations/test_curve_score_operation_plugin.py \
     tests/operations/test_tcad_operation_plugin.py \
     tests/operations/test_architecture_constraint_matrix.py \
     tests/operations/test_ingaas_operation_plugin.py \
     tests/operations/test_r4_approval_operation.py \
     tests/operations/test_r4_execution_approval_identity.py
   94 passed in 20.36s
   ```

3. 在上述测试生成的干净 core wheel 环境中执行独立结构探针：

   ```text
   installed_base_structural_chain=pass
   intent_owner=general_science
   materialize_owner=general_science
   review_owner=general_science
   operation_count=17
   find_spec(curve_score)=None
   find_spec(tcad_artifact)=None
   ```

4. 源码目录独立编译探针确认：基础/完整目录分别为17/43项；六项通用 Operation 的
   `plugin_id` 均为 `general_science`；曲线三项科学 Operation 的 `plugin_id` 均为
   `curve_score`；所有跨插件组件均为公开组件。

5. `git diff --check` 通过。

独立 pytest 总计101项通过；结构探针和差异检查单独计，不将其虚增为 pytest 数量。

## 5. 剩余风险和放行边界

以下问题明确未关闭，也不允许因 H2a 通过而跳过：

- 核心 `schema/experiment.py` 及相邻实验合同仍引用曲线数据结构；
- 核心仍拥有曲线评分/分析实现；
- `curve_score` 当前仍反向依赖 `tcad_artifact`，基础 wheel 加曲线 wheel 的独立组合尚不是
  H2a 完成事实；
- 非曲线盲插件尚未证明通用实验合同的领域中立性。

因此本报告只证明 Operation 与组件所有权迁移正确，**仅放行 H2b 的 Schema、算法与依赖方向
迁移**；不放行 H3 或后续阶段，也不宣称通用科学合同已完成领域中立化。

## 6. 最终裁决

**H2a 通过。** 当前实现满足本阶段最小目标：真实基础 wheel 可独立发现并编译通用实验结构链，
六项通用 Operation 具有唯一通用所有者，曲线插件只保留真实曲线科学责任，跨插件引用通过统一
目录、显式依赖和公开组件完成，关键 Guard、审查、批准约束、完整对象修订和 Worker 工具能力没有
回退，也没有引入第二注册表或新的运行权威。

下一步只能进入 H2b。
