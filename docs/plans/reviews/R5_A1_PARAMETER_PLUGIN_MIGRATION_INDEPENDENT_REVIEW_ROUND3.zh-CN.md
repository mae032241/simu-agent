# R5-A1 设备参数插件迁移第三轮独立审查

日期：2026-08-29  
审查对象：当前共享工作树中的 R5-A1 第二轮修复候选  
结论：**通过**  
门禁决定：**放行 R5-A2**

## 1. 审查范围

本轮未参与实现，只复核第二轮报告中的两个阻塞及修复是否产生新旁路。审查前重新完整读取了
`scid-cross-boundary-review`、`scid-find-simplifications`、
`scid-change-scope-checks` 三项技能，并核对当前架构、R5-A1 门和 33 项行为约束的使用方式。

审查沿以下真实边界进行：已安装 full wheel → 编译 Operation → Task 输入别名 → 两个 Worker 的
PDF 工具调用 → Task finalize 父链 → producer family → 参数资格 projector → Approval UI →
uncertainty → TCAD author/reviewer。只写入本报告，没有修改生产代码、测试或实施状态。

当前工作树仍包含 R1—R5 的大范围未提交候选，Git HEAD 不是 R5-A1 的独立干净基线；本报告只对
审查时精确工作树作出结论。

## 2. 紧凑证据审计

来源只声明一次：

| 键 | 来源 |
|---|---|
| S1 | `plugins/tcad_artifact/tcad_artifact/parameter_operations.py` |
| S2 | `plugins/tcad_artifact/tcad_artifact/roles/parameter_evidence_extractor.md` 与 `parameter_evidence_auditor.md` |
| S3 | `src/scidiscovery/operations/invoke.py` |
| S4 | `src/scidiscovery/artifact_agent/service/tasks.py` |
| S5 | `src/scidiscovery/artifact_agent/interfaces/mcp_root.py` |
| S6 | `tests/fixtures/r5_parameter_chain_probe.py` |
| S7 | `tests/operations/test_r4_approval_operation.py` 与 `test_r5_frozen_baselines.py` |
| S8 | 本轮独立运行的 5 项 PDF/资格聚焦测试、1 项 clean-wheel 目录测试和 `git diff --check` |

| 检查 | 结论 | 证据 |
|---|---|---|
| PDF 原始来源与受控读取视图 | 通过：原 PDF 是唯一科学来源；提取与审计 Worker 各自实际调用注册 PDF 工具；摘录不进入资格来源集合 | S1、S2、S4、S5、S6、S8 |
| 别名—ArtifactRef 精确绑定 | 通过：审计输出的有序输入父链必须与生产者族来源逐项相等；额外、重排、替换和遗漏均失败关闭 | S1、S3、S4、S7、S8 |
| checklist/web/source 与真实 finalize 顺序 | 通过：可选 checklist 的有无和位置与编译端口顺序一致；当前参数 Agent 未注册 web-fetch，现行链没有隐含 web 父引用 | S1、S3、S4、S5、S7 |
| 复杂度与领域边界 | 通过：修复只收紧既有 producer family/projector 与角色合同；无新实体、表、注册表、状态机或核心参数分支 | S1、S2、S7、S8 |
| 安装目录与核心泄漏 | 通过：core/full/full+InGaAs 仍为 28/51/52，核心参数扫描为空 | S7、S8 |

## 3. 第二轮阻塞复核

### F1-R2 已关闭：PDF 摘录不再冒充第二个科学来源

当前 producer family 仍如实登记任务输入、冻结 web snapshot 和 PDF 摘录，但参数 projector 只把
`task_input` 与当前可达的冻结科学来源纳入资格集合，并明确排除 `pdf_excerpt`。原 PDF 引用必须
作为 `frozen_sources` 审批主体；摘录只保留为从该任务输入生成的受控页视图（S1：
`parameter_operations.py:364`—`388`）。这避免了上一轮“原 PDF 与摘录同名而自相冲突”，也没有
新增来源对象或复制来源权威。

两个参数角色的模型可见合同都要求：对每个 PDF 调用已注册 PDF 工具，引用原任务输入别名并保留
页码 locator，不把对方生成的摘录当作替代来源（S2）。该要求有实际服务端能力支撑，而不是只靠
提示：工具仍来自同一 compiled Operation，`worker_extract_pdf_text` 只能处理本任务已绑定且非
`handoff_only` 的 PDF。

full clean-wheel 探针现注册一个真实、可由 `pdftotext` 读取的单页 PDF。提取 Worker 在
`r5_parameter_chain_probe.py:512`—`524` 实际调用工具并检查页文本；审计 Worker 在
`605`—`618` 对同一原 PDF 独立再次调用工具。随后整链继续经过受控输出封存、coverage、独立审计、
UI 决定、uncertainty、计划复审和 TCAD author/reviewer。本轮从已安装 full wheel 独立复跑通过。

### F2-R2 已关闭：别名与引用不再分别满足两个子集门

Operation 预检按编译端口顺序生成 `BoundInput`，同一集合按调用中冻结的 Artifact 顺序生成
`source_material_001` 等别名（S3：`invoke.py:152`—`176`）；Root 按该顺序创建 `TaskInput`
（S5：`mcp_root.py:1253`—`1268`）。Task finalize 的父链固定为：

```text
instruction_ref + ordered task input refs + cited frozen web refs
```

（S4：`tasks.py:4174`—`4193`）。参数审计 Operation 当前没有注册 web-fetch 工具，因此现行审计
链的尾部就是完整有序任务输入；审计者自己创建的 PDF 读取视图不进入科学输出父链。

projector 现在根据 extraction family 重建原始冻结来源引用，按审计 Operation 的编译端口顺序构造
预期输入，并要求 `audit.parent_refs[1:]` 与其长度和顺序完全相等（S1：
`parameter_operations.py:439`—`455`）。随后又按同一来源数量重建审计任务本地别名，并要求审计
evidence 覆盖这些别名（`461`—`468`）。因此上一轮利用“名称子集＋引用子集”分离而加入 C、D
冒充 A、B 的路径已消失。

新增负例分别改变父链长度、交换来源顺序和替换精确引用，均在 projector 的“exact ordered review
set”门失败；未审来源和 checklist 漂移的既有负例继续通过。本轮复跑这些负例和真实多来源链均
通过。

## 4. 顺序、可选项与边界检查

- **可选 checklist**：extract 与 audit 的 checklist 都是编译端口顺序中的第一个可选输入；
  producer family 必须恰好包含同一 checklist 引用，projector 再把它放在 audit primary 之后、
  三个 typed sibling 之前。无 checklist 的 projector 正例和有 checklist 的真实 PDF 整链都成立；
  内容漂移继续失败关闭。
- **source 集合**：extract 和 audit 对同数量、同顺序原始来源生成相同任务本地别名。资格审批的
  `frozen_sources` 又要求逐项等于 producer family 原始来源引用，不能通过 UI 输入重排补救。
- **web**：通用 producer family 能描述 `web_snapshot`，Task finalize 也把实际引用的冻结 web
  证据放在普通输入之后；但当前两个参数 Agent 的工具闭包只注册 PDF 工具，没有
  `worker_fetch_web_evidence`，所以 web 并非本轮现行参数来源能力，不能产生隐藏父引用或旁路。
  将来若显式给参数 Operation 增加 web-fetch，必须同时解决 snapshot Schema、任务本地别名和
  安装态正负例；这是未来能力变更要求，不是当前失败。
- **指令父引用**：projector 跳过父链首项符合 TaskService 对 Agent 输出的唯一 finalize 合同；
  该输出仍必须来自带精确 operation id/version/digest 的已完成审计任务。任意额外输入或审计时
  新增冻结 web 证据都会改变长度并失败关闭。

## 5. 奥卡姆与架构目标

修复没有引入 SourceIdentity 新 Schema、来源映射表、数据库列、第二注册表或新生命周期。它复用：

- producer family 已有的 `(source_kind, source_name, ref)`；
- Operation 编译端口的确定顺序；
- Task 输出已有的不可变有序父链；
- 既有 PDF 缓存和任务绑定摘录；
- 既有 Approval projector 和 UI 生命周期。

领域判断仍由提取/审计 Worker 完成，控制面只核对“审计的是不是同一组字节”；PDF 摘录不获得
独立科学身份，人工决定仍只来自 UI。核心源码扫描未发现设备参数 Schema、参数 Operation 或领域
资格分支。修复符合“若非必要勿增实体”、单一 compiled catalog、Worker 最小上下文和插件闭包
目标，没有出现为了关闭两个漏洞而建立新权威或复杂度反噬。

## 6. 独立运行证据

所有命令均严格串行，并先执行：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

本轮结果：

```text
pytest -q \
  tests/operations/test_r5_frozen_baselines.py::test_r5_a1_full_clean_wheel_runs_parameter_chain_through_tcad_review \
  tests/operations/test_r4_approval_operation.py::test_parameter_approval_rejects_extra_or_substituted_audit_inputs \
  tests/operations/test_r4_approval_operation.py::test_parameter_approval_treats_pdf_excerpt_as_a_bound_read_view \
  tests/operations/test_r4_approval_operation.py::test_parameter_approval_rejects_a_changed_supplied_checklist \
  tests/operations/test_r4_approval_operation.py::test_metadata_only_parameter_source_crosses_the_compiled_tcad_operations
# 5 passed in 27.82s

pytest -q \
  tests/operations/test_r5_frozen_baselines.py::test_r5_a1_clean_wheel_catalog_delta_matches_parameter_migration
# 1 passed in 24.75s

git diff --check
# 通过
```

实现方记录的 92 项跨边界和 255 项全仓回归与当前候选一致，但本轮没有把它们冒充独立复跑；两个
已复现阻塞都有更窄、能直接失败的拥有者测试及安装态正链，重复全仓测试不会增加本轮判定信息。

## 7. 最终结论

**通过。**

第二轮两项承重问题已经按最小方式关闭：PDF 摘录成为原 PDF 的受控读取视图而非第二来源；审计
别名与 ArtifactRef 由真实有序父链一一绑定，额外、重排、替换和遗漏均失败关闭。修复没有新增
实体、注册表、核心领域分支或科学控制权威，且真实 PDF full-wheel 整链通过。

本报告仅放行下一内部阶段 **R5-A2**。它不证明 R5-A2 的破坏性删除已经正确，也不放行 R5-B；
R5-A2 完成后仍须按计划进行自己的真实启动入口、旧调用失败、目录摘要、完整回归和独立审查。
