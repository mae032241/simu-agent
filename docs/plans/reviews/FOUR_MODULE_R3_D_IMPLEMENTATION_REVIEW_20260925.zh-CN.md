# R3 D Root 与机械准备内化：独立静态审查

## 结论与精确候选

**STATIC REVIEW PASS：本次受影响路径未发现阻断缺陷；1 项非阻断的重复计算改进。** 本结论不表示测试、安装、运行资格或整份 R3 运行验收已通过。

- 日期：2026-09-25。
- 仓库：`123/scidiscovery-e5.2`，基于既有清理和 A/B/C 的未提交工作树。
- 候选：`/tmp/scid-r3-d-candidate.json`，32 文件；清单 SHA256：`6792b6ce35e48e5a578e74eaa3024c84899081a6dadba70a968857fdfbb440b1`。
- 审查者逐项重算 32 文件 SHA256，全部匹配；20 个 Python 文件通过 stdlib AST 解析。候选附有各文件修改前 hash 与合同映射，裸 Git HEAD 不能代表本候选。
- 串行审查，无派生 Agent，无实现修改；没有运行测试、pytest collection、catalog 动态编译、项目动态导入、安装、构建或 solver。
- 范围限定 R3 D 的准备合同、Root、审查/授权、预算归属及分析消费者；未重新审计无关历史清理和未变更 runner。

## 非阻断改进

### D-N1：同一调用内重复执行确定性准备

**位置：**`src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py` 的 `_prepare_operation_call`、`_effect_operation_plan`、`operation_preflight` / `operation_invoke`；`interfaces/mcp_root_execution_routes.py` 的 `_effect_admission`、`_invoke_compiled_effect`。

当前 `_prepare_operation_call` 已调用 `_effect_operation_plan`，后者执行 `_effect_admission`，其中会 prepare payload。上层再次调用这些方法：一次 preflight 通常准备 3 次，一次 invoke 通常准备 4 次，包含内部封包前的最后一次 prepare。每次都会重新读取 JSON、重建 TCAD package、校验 schema/语义，并重复查询活动策略。

准备函数确定、输入不可变，因此静态上未发现身份差异或权限绕过；但大项目会付出重复解析和重建成本，本轮没有测量其耗时/内存。

**建议：**在单次调用上下文保留已验证的 prepared payload 与精确输入/compiled digest，在创建前复用；把确有必要的当前策略和预算重新判断独立出来。缓存不能跨请求变成新的资格来源，submit 前的实时策略检查继续保留。

## 已追踪的真实边界

### 1. 编译合同与纯准备

- `ExecutorRef.preparation` 是声明的一部分，Operation ABI 为 19；catalog 将 preparation 引用按 transform 组件解析，纳入 reachable components 和 compiled digest。
- preparation 仅允许出现在 effect；prepared effect 要求 execution_request 与唯一 prepared payload 输出、固定审批 subject 顺序和 payload validator。组件/输出 schema/semantic contract 通过既有编译资源路径绑定。
- `prepare_effect_payload` 从实际 bound inputs 构造 ValidationSources，科学文件只传 exact metadata；验证唯一输出端口、bytes 类型、总量/单项上限、业务 validator 和 JSON Schema，不注册或绑定 Artifact。

### 2. Root 预检、封包与幂等身份

- preflight/invoke 共用输入 admission 和 `_effect_admission`；独立 review/资格检查发生在 `_prepare_operation_call` 内，prepared effect 不跳过这些检查。
- preflight 只读取/验证，不创建包、execution、approval 或预算预留。
- invoke 内部注册的包绑定全部 exact 输入父件；复用键包含 compiled digest、顺序父链、输出端口及内容 SHA256。重复调用或请求改名可复用同一包；旧 binding 复用前还检查父链、原字节与 operation digest。
- 包名通过 `prepared_outputs` 返回，Root 无需自行构造 reviewed package，也无需再派发执行计划投影。
- 源码与角色中的旧 `tcad.execution-plan.project.v1` 入口及 `tcad.reviewed-deck-package.v2` Operation 注册已移除；后者 schema/adapter profile 继续存在，有明确内部用途。

### 3. TCAD 科学审查与两条计划路线

- `tcad.deck.review.v1` version 4 对骨架项目只接受 project 内嵌 execution_plan，拒绝再绑定另一个 experiment_plan；审查工作区从封存 project 生成只读计划副本，最终 review validator 也从该原件取计划。
- `tcad.study.execute` version 3 直接接 project/review/capability/scientific subject。package parentage guard 核对 review 的 project、execution_capability、原科学主体，并核对真实 producer_inputs；骨架路线要求完成的 version 4 reviewer、passing scientific_assessment 和原骨架的真实 producer。
- 通用 producer admission 仍负责独立作者/reviewer、当前资格和匹配 review witness。内部准备没有改为仅凭 report 中的 pass 字段放行。
- SDevice 详细计划分支继续使用原 experiment_plan 及科学审查输入；骨架分支仍显式只支持 SProcess。没有把未支持的 SDevice 骨架当作已完成能力。
- device_grid 仍是 file_reference；内部 package 从 binding descriptors 核对其属于 exact project 的直接父件，构造 resolved_inputs。既有受控流式 adapter 路径未改成 JSON/base64。

### 4. B 的授权、预算与未知提交保持闭合

- 封包前从 bound 输入 refs、封包后从 prepared payload 的父链调用同一 scientific_budget_owner 遍历，未以新包内容或调用名称建立新额度池。
- 原 policy/human 分支继续使用同一 execution 生命周期；D 没有改写已审过的授权历史/current pointer、累计预留与结算逻辑。
- human UI 仍读取 execution_request 与实际封存 payload 的 exact refs；审批 projector、选项和 compiled identity 来自当前编译合同，不把 Root 原始输入列表错误地当审批 subject。
- `execution_start` 仍进入原 Bridge，prepared/unknown 先查询原 submission，submit 前重判策略；本轮未增加重复启动路径。
- 当前 guide 说明配置内自主授权与 UI 人工授权的分支，并保留科学独立审查和明确 collection/recovery 操作。

### 5. 分析消费与导航

- 骨架结果分析从 `reviewed_package.project.execution_plan` 读取计划；guard 要求该 package 的 exact version 4 execution_review、project 与 skeleton 关系，拒绝再混入 standalone experiment_plan。
- 详细计划分析继续绑定原 plan/review，未误切换成骨架合同。
- 分析工作区的 original alias 和 case matrix JSON pointer 指向 `/project/execution_plan/...`；历史来源映射使用 exact package/plan 绑定，C 的 checkpoint_alias 和受控计算记录逻辑未被移除。
- scheduler research/execution/domain-analysis/evidence 和当前中英文文档已反映完整作者任务、内部封包、策略授权、checkpoint 复用。部署前旧安装内的 guides/AGENTS 仍需按完整候选更新，当前文件变化不代表服务已部署。

## 验证限制

本报告根据真实生产调用链作静态检查，阅读到的测试代码仅用于理解预期，不作为已经执行的证据。尚未验证：安装后的 ABI19 catalog、真实作者与独立 review 闭环、policy/human UI 提交、远端 TCAD、2GB 文件内存峰值、配置变化/并发预留/未知提交恢复、分析 checkpoint 运行复用。未报告任何 token 或耗时收益。

上述运行项目须在用户解除相应执行限制并安排资源后验证；当前静态 PASS 不授予部署或科学运行资格。
