# R5 E5 同一 Operation 创建／修订实现证据

日期：2026-09-05  
状态：完成。P4 第二轮独立复审 PASS、剩余阻断 0；clean release 与安装前 dry-run 通过，允许部署
并继续真实 E5。

## 1. 实现结果

图证据 Intake 现在只有一个公开生产行为：`science.evidence.extract.figure.v2`。

- 只绑定完整图证据文件族时，执行创建模式；
- 同时绑定 `prior_draft` 与 `change_request` 时，执行写时复制的完整对象修订模式；
- 两个修订端口只允许 `0..1`，由一个无审批 `InputAdmissionSpec` 保证全有或全无；
- 独立审查仍是 `science.figure.evidence.audit.v1`；
- 没有注册 `science.intake.revise.figure.v1`，没有模式字段、数据库状态或调度器名称分支。

## 2. 通用运行时边界

`direct_revision_ports()` 继续静态识别 Operation 是否具备修订能力。新增的
`active_direct_revision_ports()` 只根据本次实际冻结输入端口判断修订是否激活：

- catalog 编译和 Hardened 后端能力判断仍使用静态合同；
- assignment、草稿、workspace、提交差异检查、Root 修订策略和 producer direct-base 准入统一使用
  active 结果；
- active 结果不持久化，Run 冻结 inputs 是恢复时唯一事实；
- 同一 digest 的普通创建 Run 是可选双模式 Operation 的合法链根；半截 base/request 历史仍拒绝；
- Worker 可见的 `runtime.revision` 对可选基线明确写明条件，不把创建调用描述成修订。

可选形状只有在唯一 base/request、严格 `0..1`、二成员无审批 cohort、完整同型输出、精确 reviewer、
有界修订次数和问题指纹全部成立时才能编译。既有必需基线修订形状未改变。

## 3. 图插件边界

图插件只声明：

- 同一原提取 Operation 的两个可选修订输入；
- 修订基线与审查共同绑定原完整图族的无内容父链 guard；
- 排除自由文本的未通过审查项问题指纹；
- 同一 Agent、提示、Schema、validator、工具、完整生产族和 review edge；
- 最大两次修订。

下游 `figure_parentage` 不枚举创建／修订 producer id，只检查输出端口、完整图族父链、精确新审查父链
和通过 verdict；Root 仍按冻结 Operation digest 与 ReviewSpec 验证 producer 和 reviewer。

## 4. 聚焦测试

命令：

```text
ulimit -v 4194304
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q \
  tests/operations/test_incremental_revision_runtime.py \
  tests/operations/test_m5_figure_review_closure.py \
  tests/operations/test_m2_optional_figure_plugin.py \
  tests/operations/test_m5_plugin_ownership_and_default_surface.py \
  tests/operations/test_m6b_operation_input_admission.py \
  tests/operations/test_m6c_producer_topology_removal.py \
  tests/operations/test_agent_contract_alignment.py \
  tests/operations/test_l2_local_run.py
```

初次结果：`56 passed in 7.09s`；最大常驻内存 `108840 KiB`，无 swap。

另以干净 wheel/虚拟环境运行安装态目录与插件探针（仅排除下述已知不相关 Hardened 夹具失败），结果
为 `9 passed, 1 deselected in 47.28s`，最大常驻内存 `74688 KiB`，无 swap。

覆盖包括：

- 盲插件合法可选形状和十类畸形编译负例；
- 创建 assignment 无 revision／无预填草稿；
- 同一盲 Operation 修订自己的创建输出；
- 修订 assignment 写时复制及 unchanged 拒绝；
- 图 Intake 创建、两次修订、每版新独立审查和最终下游 bundle；
- 半组、错图族、旧审查、相同问题指纹和超限在 Run/Artifact 创建前拒绝；
- 通用、实验、TCAD 等既有必需基线修订相关聚焦回归。

一次更宽的安装测试运行得到 `42 passed, 1 failed`。失败项为既有
`test_clean_installed_pure_mcp_plugin_completes_a_hardened_run`：测试夹具的 blind reviewer 声明原生 shell，
Hardened 后端因此在作者调用前报告 `operation_runtime_unavailable`。本轮未修改该 reviewer、Hardened
策略或安装探针，也不以无关放宽掩盖该失败；它不属于本次同 Operation 修订改动的部署通过证据。

## 5. P4 首轮阻断及修复

首轮实现审查报告
`reviews/R5_E5_SAME_OPERATION_REVISION_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md` 判定 FAIL、阻断
一项：Run 调度仍按 input usage 自行判断本次修订，提交校验则把 source name 当作 port name 交给
active 总函数。

修复严格限制为两个调用面：

- `RunService.schedule()` 对冻结输入调用 `active_direct_revision_ports()`，只从返回的精确 base 端口
  取得单后继检查对象；
- `validate_run_output()` 显式接收冻结 `input_port_names` 并交给同一 active 总函数；原
  `input_bytes` 继续只承担 source-name 到内容的映射；
- 未修改图插件、OperationSpec、ABI、数据库、状态、Hardened 后端或错误分类。

修复后同一 56 项矩阵结果：`56 passed in 7.71s`；最大常驻内存 `110536 KiB`，无 swap。

## 6. P4 复审和发行

P4 第二轮结论已追加到
`reviews/R5_E5_SAME_OPERATION_REVISION_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`：`PASS`，剩余
阻断项 0。独立测试为 `56 passed in 7.36s`，最大常驻内存 `108756 KiB`，无 swap。

已生成：

```text
deliverables/r5-e5-same-operation-revision-clean-release/
deliverables/r5-e5-same-operation-revision-clean-release.tar.gz
```

发布目录包含 240 个清单化文件；`sha256sum -c MANIFEST.sha256` 全部通过。以真实 M7 workspace、四
插件组合、8765 端口和既有 TCAD adapter 执行安装前 `--dry-run` 通过；最大常驻内存 `48068 KiB`，
没有修改包、状态、服务或平台配置。

## 7. 尚未完成

- 新合同下的真实 Intake 创建、独立审查、同 Operation 修订及再次独立审查；
- 后续真实标准曲线包和完整科学闭环。
