# R5-G 直接完整对象修订 D0 独立实现审查

日期：2026-08-30  
审查范围：当前共享工作树中的 D0 精确候选  
审查者：未参与 D0 实现的独立审查者

## 结论

**通过。仅放行 D1；不放行 D2—D4、真实科学对象修订、实验设计或 R5-G 完成。**

未发现阻断项。D0 已把未经独立审查的准入半修复完整撤销，并用失败关闭测试诚实冻结原有合同死锁；它没有把该失败包装成目标行为，也没有提前实现直接完整对象修订。旧的“通过评审→结构化补丁→应用→收据→重新审计”比较基线仍可运行。

## 完成门核验

| 完成门 | 结论 | 证据 |
|---|---|---|
| 撤销四项 Root 半修复 | 通过 | 对生产与测试路径检索 `_REVISION_REQUEST_VERDICTS`、`_revision_admission_subject_refs`、`revision_subject_refs` 均为零命中。`_validate_operation_input_admission` 直接进入通用 producer-output admission；其中不存在按修订 Operation、端口或 verdict 放行 `revision_base` 的分支。 |
| 旧死锁被精确、诚实冻结 | 通过 | `tests/operations/test_general_science_plugin.py:648`—`689` 只把同一精确审计输出的调度信号投影为 `revise`，随后分别验证普通 split 和 `science.intake.revise.v1` 以 `input_independent_review_missing` 失败；紧邻注释明确说明这是 D0 冻结的旧架构死锁，D1 才负责消除合同冲突。 |
| 未把失败冒充目标行为 | 通过 | 失败断言只存在于受限 `monkeypatch.context()` 中；退出后恢复原信号，测试继续要求已通过审查的正常下游成功。计划状态仍写“D0 待独立审查”，没有宣称修订闭环已经修复。 |
| 保留通过评审下的旧补丁基线 | 通过 | 同一真实 Root/Worker 生命周期测试继续执行 `science.intake.revise.v1`，完成 claim/materialize/write/validate/finalize，再执行 `science.revision.apply.intake.v1`、`science.evidence.receipt.intake.v1` 和新的独立 audit，见该测试 `840` 行以后。全 Operation 回归通过。 |
| D0 未偷跑 D1 | 通过 | 当前仍由旧修订 Agent 输出 `StructuredRevision`，Root 仍保留旧 producer-family 递归和 exact applied-revision 识别；未出现 direct-revision classifier、按 usage 的新来源权威、新 Schema/表/状态机或新的完整对象输出合同。`docs/ARCHITECTURE.md` 与 `docs/ARCHITECTURE.zh-CN.md` 未被 D0 改写。 |
| 不改科学对象、审批与私有运行 | 通过 | D0 的真实科学报告和私有假设阶段报告时间均早于 D0 候选；D0 时间窗内私有运行目录无新增文件。候选测试仅在测试临时实例中构造状态，没有执行现场 Agent、UI 决定或持久科学写入。 |
| 指标和文档记录可信 | 通过 | 独立运行 `scripts/r5_current_metrics.py` 得到生产 Python 143 文件/60254 行；通用科学声明后继 941 行，声明加确定性组件 2065 行。冻结生成器 SHA-256 仍为 `718eac8e17569cdbb7adeefe7e0e8cc12efab20cae96b614e4fdc77db40e51f5`。计划总表、README、最小重构计划均只记录 D0 候选待审。 |

## 语义与跨边界判断

### 1. Root 已恢复单一通用准入路径

`src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:1120` 的准入顺序仍是 producer-output admission、compiled cohort 和 claim-evidence 三类通用检查。`1198` 行开始的 producer-output admission 只接受精确 reviewer output、精确 review-bound revision 或旧协议产生的精确 applied revision；不存在“只要 verdict 为 revise/blocked 就把被审对象当成合法修订输入”的额外 subject 集合。

文件中仍出现的 `revision_base` 位于旧 producer-family 重建和旧 applied-revision 验证中。这些是 D0 明确要求保留的比较基线，不是已撤销的 preflight skip，也不是第二准入权威。

### 2. 失败测试冻结的是旧事实，不是新规范

测试同时覆盖两条失败：非通过评审不能进入普通下游，也不能进入旧补丁修订入口。两者返回同一个确定性原因码，准确暴露“要求先通过才能进入修订、但修订正是为修复未通过对象服务”的合同冲突。

测试通过局部替换调度信号制造非通过投影，而不是新建一份持久的非通过科学结果。对 D0 的机械回退门这是足够且较小的覆盖：它命中真实 Root preflight/invoke 和精确 subject 绑定，没有构造新的生产旁路。后续 D1 仍应以真实完整对象 Worker 生命周期覆盖 pass/revise/blocked 和错绑负例；这不是 D0 阻断项。

### 3. D0 消除半修复，没有转移断裂

D0 没有声称解决旧死锁，而是删除在相邻准入层叠加的未经审查例外，使失败重新集中暴露在原 producer-output admission 合同处。因此本阶段消除的是“用局部例外掩盖架构冲突”的半修复；原合同冲突仍原位存在并由测试命名，未被搬到 Task、Worker、Catalog、Approval 或另一个新实体。其修复属于已独立审查过的 D1 范围。

问题分类也与计划一致：合同冲突归为架构/Operation 合同问题；全 Operation 首轮发现的固定行数漂移归为机械测试夹具错误，仅同步实测指标，没有据此放宽科学准入或增加状态。

## 独立复测

所有测试严格串行执行，并在每个进程前设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

执行结果：

1. D0 聚焦矩阵：`36 passed in 40.05s`。
2. `pytest -q tests/operations`：`269 passed in 90.75s`。
3. `python scripts/r5_current_metrics.py`：143/60254、941、2065 与记录一致。
4. 半修复符号生产/测试检索：零命中。
5. `git diff --check`：通过，无输出。

聚焦矩阵包括通用科学真实生命周期、旧 Transform 修订链、盲 producer family、Root 路由、Catalog 阶段以及 TCAD 已评审计划准入，共 36 项；不是只测新增断言。

## 非阻断说明

当前仓库相对于基线提交包含大量既有未跟踪文件，因此无法用单一 Git 提交差异证明 D0 的历史增删。此次结论以当前候选精确字节、两轮已冻结方案审查、当前文件时间边界、静态消费者检查和独立运行的真实测试为准。该限制不影响 D0 门禁判断，但进入 D1 前应继续保持阶段记录和独立审查边界，避免在同一未冻结工作树中混入 D2 变更。

## 放行边界

D1 可以开始，其完成后仍须独立实现审查。D1 必须解决直接完整对象修订的结构分类、精确可选 change request、按 usage 的父链/来源、全新独立复审和普通下游失败关闭；不得重新引入本轮删除的 verdict 列表或 Root 中按 Operation/端口的修订特判。
