# R5-A1 设备参数插件迁移第二轮独立审查

日期：2026-08-29  
审查对象：当前共享工作树中的 R5-A1 首轮修复候选  
结论：**打回**  
门禁决定：**不放行 R5-A2**

## 1. 审查范围与方法

本轮未参与修复，只复核首轮 F1—F4 及其跨边界后果。审查前完整阅读了
`scid-cross-boundary-review`、`scid-find-simplifications` 和
`scid-change-scope-checks` 三项技能，并沿真实
Operation 调用、输入别名、Worker 来源访问、任务输出父链、producer family、资格 projector、
Approval UI 和 TCAD author/reviewer 路径核对当前精确工作树。

当前分支相对 `baseline/8765-codex` 仍包含 R1—R5 的大范围未提交改动，因此本报告不把 Git HEAD
误称为 R5-A1 的干净外部基线。代码、测试与实施记录均按审查时工作树字节核对。所有执行命令均严格
串行，并先设置 7 GiB 虚拟内存上限。

## 2. 证据审计摘要

来源只在本表声明一次：

| 键 | 来源 |
|---|---|
| S1 | `plugins/tcad_artifact/tcad_artifact/parameter_operations.py` |
| S2 | `src/scidiscovery/artifact_agent/service/tasks.py` |
| S3 | `src/scidiscovery/artifact_agent/interfaces/mcp_root.py` |
| S4 | `src/scidiscovery/operations/invoke.py` |
| S5 | `src/scidiscovery/general_transform_operations.py` |
| S6 | `tests/fixtures/r5_parameter_chain_probe.py` 与 `tests/operations/test_r5_frozen_baselines.py` |
| S7 | 本轮 5 项聚焦测试、1 项 clean-wheel 目录测试及只读内存复现 |

| 检查 | 结论 | 证据 |
|---|---|---|
| F1：审计 Worker 能读全部精确冻结来源 | **失败**：普通文本已闭合，但合法 PDF 摘录路径会被资格门自身拒绝，且审计端口不能绑定摘录 Schema | S1、S2、S3、S4、S6 |
| F2：未审来源和 checklist 漂移均失败关闭 | **失败**：简单遗漏和 checklist 漂移已关闭，但来源别名与 Artifact 引用未形成同一精确身份，可被审计专用额外输入错配 | S1、S2、S4、S7 |
| F3：full wheel 整链 | **通过（机械闭环）**：文本源真实经过提取、coverage、审计、UI 决定、uncertainty、计划复审及 TCAD author/reviewer | S6、S7 |
| F4：通用 intake split 去领域特判 | **通过**：审计端口已必需，描述无参数或 legacy 例外 | S5 |
| 核心泄漏、目录权威与复杂度 | **通过本轮范围**：core/full/full+InGaAs 为 28/51/52；未发现新注册表、状态机或核心参数分支 | S5、S6、S7 |

## 3. 阻塞问题

### F1-R2（阻塞）：PDF 是公开支持的来源类型，但提取后无法通过精确来源资格闭包

`source_material` 明确接受 `application/pdf`，提取和审计 Agent 也都声明了 PDF 提取工具；这不是未来
扩展，而是当前公开合同。Worker 调用 PDF 提取后，控制面登记一个
`scidiscovery.pdf-excerpt-set.v1` 摘录，并保留原输入名作为摘录 `source_name`（S2：
`tasks.py:1692`—`1723`）。producer family 又同时登记原始任务输入与该 PDF 摘录，二者
`source_kind` 和引用不同，但 `source_name` 相同（S3：`mcp_root.py:1523`—`1550`）。

资格 projector 随后要求所有 family 来源的 `source_name` 全局唯一（S1：
`parameter_operations.py:364`—`378`），因此任何真正调用 PDF 提取工具的合法参数提取任务都会在
创建资格请求时失败。即使删除该唯一性检查，当前审计 `source_material` 端口只接受 Schema
`opaque`（S1：`parameter_operations.py:716`—`736`），而 Operation 预检要求精确 Schema 相等
（S4：`invoke.py:357`—`367`），所以摘录 Artifact 仍不能作为“每个精确冻结来源”绑定给审计者。

现有安装态整链没有覆盖该合同：它只注册并读取一个 `text/plain` 的 `opaque` 来源，随后只断言
PDF 工具名称可见，没有实际调用该工具（S6：`r5_parameter_chain_probe.py:451`—`480`、
`541`—`568`）。因此“PDF 来源已闭合”的实施记录不成立。

最小修复不是新增来源实体、数据库表或第二注册表，而是统一现有来源身份合同：

1. 明确 producer family 中原 PDF 与派生摘录的关系和稳定唯一键；若摘录属于必审来源，就给它独立、
   可绑定的来源键并让审计端口接受其精确 Schema；若摘录只是原 PDF 的受控读取视图，就不得又把它
   当作第二个同名必审来源，但必须保留其父链和页码定位证明。
2. 资格 projector、审计输入和审计输出必须对同一组 `(来源种类、稳定来源键、ArtifactRef)` 做精确
   集合核对，而不是分别核对名称集合与引用集合。
3. 增加 full clean-wheel PDF 正例：实际调用 `worker_extract_pdf_text`、读取冻结摘录、完成独立审计并
   通过资格；同时增加缺摘录、替换摘录或错配原 PDF 的负例。

### F2-R2（阻塞）：审计证据键与被审 Artifact 引用仍可独立满足门禁

Operation 每次按当前端口集合顺序生成 `source_material_001` 等任务本地名称（S4：
`invoke.py:152`—`176`）。任务输出验证只要求审计声明的 `source_key` 属于该审计任务的输入名称
（S2：`tasks.py:5042`—`5059`）；任务输出父链则包含全部任务输入引用，但不保留“该引用对应哪个
来源键”的映射。

资格 projector 对引用只做 `required_parents.issubset(audit.parent_refs)`，对名称只做
`expected_source_keys.issubset(audit.evidence.source_key)`（S1：`parameter_operations.py:429`—`447`）。
两项之间没有同一身份约束，且父引用允许超集。

因此存在真实可达的错配：提取 family 的来源为 A、B；审计任务额外绑定 C、D，并通过调整审计端口
顺序让 C、D 获得提取阶段预期的 `source_material_001/002` 名称，同时也把 A、B 作为后续输入绑定。
审计结果只引用 001/002，任务输出验证会接受；父链又包含 A、B，资格 projector 的名称子集和引用
子集也都会接受，但真正被声明审查的是 C、D，而不是 A、B。

本轮用当前 projector 做只读内存复现，结果返回 `ReviewDocument`，证明这不是仅凭推测的不可达状态。
现有负例只追加一个未声明名称，没有覆盖“额外审计输入导致同名异物”的情况。

最小修复：在现有 Operation/producer-family 边界上保存或确定性重建精确的来源键—引用映射，并要求
审计任务消费的来源集合与提取 family 的必审来源集合严格相等；资格 projector 应核对审计声明、
审计任务输入和提取 family 的同一三元身份。增加来源重排、额外输入、同名异引用和正确同序/异序
映射测试。无需新增可变注册表或状态机。

## 4. 首轮其余问题的复核结果

### F3 已闭合：安装态文本源纵向链成立

full clean-wheel 探针从已安装包解析编译目录，清除源码 `PYTHONPATH`，真实通过
`operation_invoke`、Worker claim/materialize、受控文件封存、coverage、审计 Worker、通用 intake
split、本地 Approval UI HTTP 决定、uncertainty、实验计划复审、带有界假调试 adapter 的 TCAD
author 以及只读 reviewer。聚焦复跑通过。该测试证明“资格 cohort 能贯穿到 author/reviewer”的
机械闭环；它不能替代 F1 的 PDF 来源闭包，也没有证明 deck 内容实际使用了某个参数值，后者可作为
后续科学效果测试增强，但不单独构成本轮新门禁。

### F4 已闭合：通用核心不再保留参数例外

`science.intake.split.v1` 的 `evidence_audit` 已为必需端口，模型可见描述是领域中性的独立审计合同
（S5：`general_transform_operations.py:470`—`490`）。生产核心扫描未命中设备参数 Schema、参数
Operation id 或旧参数桥名称。本轮未发现以新 facade、第二目录或核心领域分支替代旧桥。

### 架构目标与奥卡姆检查

修复候选仍把六个参数 Operation、Schema、算法、角色提示、工具引用和资格 projector 聚合在一个
`tcad_artifact` 插件闭包，复用统一编译目录、Artifact/Task/Worker/Approval 生命周期。F1/F2 是同一
“来源身份没有贯穿边界”的局部合同错误；应在现有身份与 guard 上收紧，不应为此引入新的科学对象、
资格状态机或并列注册表。除该错误外，未发现本轮修复造成复杂度反噬或偏离“轻控制面、插件闭包、
Worker 最小上下文、人工决定唯一”的目标。

## 5. 独立复核命令

所有命令均在以下前置条件下严格串行运行：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

结果：

```text
pytest -q \
  tests/operations/test_r5_frozen_baselines.py::test_r5_a1_full_clean_wheel_runs_parameter_chain_through_tcad_review \
  tests/operations/test_r4_approval_operation.py::test_parameter_approval_rejects_a_changed_supplied_checklist \
  tests/operations/test_r4_approval_operation.py::test_parameter_approval_rejects_an_unreviewed_frozen_source \
  tests/operations/test_r4_approval_operation.py::test_metadata_only_parameter_source_crosses_the_compiled_tcad_operations \
  tests/operations/test_tcad_operation_plugin.py::test_parameter_cohort_is_all_or_none_and_approved_together
# 5 passed in 28.87s

pytest -q \
  tests/operations/test_r5_frozen_baselines.py::test_r5_a1_clean_wheel_catalog_delta_matches_parameter_migration
# 1 passed in 25.01s

只读内存复现：在审计父链加入额外来源并让审计声明使用提取阶段预期别名，
当前 PASS_PROJECTOR 返回 ReviewDocument。

git diff --check
# 通过
```

已有实现方全仓 `253 passed` 可作为回归记录，但本轮在承重语义缺陷已经复现后没有重复全仓测试，
也不把该数字写成独立复跑结果。

## 6. 最终结论

**打回。**

首轮 F3、F4 已闭合，普通文本来源的可读性、简单来源遗漏、checklist 漂移、cohort 以及 clean-wheel
目录差值也通过独立复核；但 F1 对已公开支持的 PDF 路径仍不可执行，F2 又允许来源键与被审 Artifact
引用错配。两项都直接破坏“每个精确冻结来源经过独立科学审查后才可资格化”的承重边界。

完成上述最小来源身份修复并加入 PDF 正例及错配负例前，R5-A1 不通过，**不得放行 R5-A2**。
