# R4-D-C 执行审批编译身份独立复审

## 结论

**通过，允许进入 R4-D-D。**

当前实现把外部执行授权闭合在同一个启动编译 Operation 合同内：Effect 创建请求时冻结完整审批身份，审批创建时重新解析当前目录和 projector，启动时再次解析当前目录，ExecutionBridge 只传递该身份，ExecutionService 最终核对请求、审批请求、决定和精确两个 subjects。缺身份、合同漂移、插件卸载、错误审批身份及已经决定的旧 fallback 均不能启动执行。

本轮未发现第二执行注册表、领域路由表、新资格状态机或核心 TCAD 审批特判。执行生命周期仍由既有 ExecutionService 和 ApprovalService 唯一持久化，领域插件只提供 Effect plan、适配器和只读 projector。

## 审查范围与口径

本轮在 `baseline/8765-codex` 上的大型未提交 R1—R4 工作树中审查，没有假设不存在的远端或提交基线。依据总计划 7.3、7.5、7.7 和已经通过的 R4-D-A/D-B 边界，沿以下真实路径逐段核验：

```text
compiled Effect
→ operation_invoke
→ immutable ExecutionRequest 与 Artifact 标签
→ compiled execution approval/projector
→ ApprovalRequest 与 UI HumanDecision
→ execution_start 当前合同复核
→ ExecutionBridge
→ ExecutionService.authorize
→ adapter prepare/submit
```

重点文件包括：

- `src/scidiscovery/artifact_agent/schema/execution.py`；
- `src/scidiscovery/artifact_agent/service/executions.py`；
- `src/scidiscovery/artifact_agent/execution_bridge.py`；
- `src/scidiscovery/artifact_agent/interfaces/mcp_root.py`；
- `src/scidiscovery/builtin_plugin.py`；
- `plugins/tcad_artifact/tcad_artifact/{plugin.py,runtime_plugin.py}`；
- `tests/operations/test_r4_execution_approval_identity.py` 及三组受影响的安装/运行时跨边界测试。

## 审查结果

### 1. Effect 请求正文身份与 Artifact 标签同源：通过

`operation_invoke` 对 `executor.kind == "effect"` 只使用已经 preflight 的 `BoundOperationCall`，并把该 exact compiled call 传给 `execution_request_create`。后者从 `bound.compiled.approval_identity` 一次构造 `CompiledApprovalIdentity`，同时用 `_operation_artifact_labels(bound)` 写入：

- operation id；
- operation version；
- operation digest；
- approval contract digest。

同一身份进入 ExecutionRequest 正文、创建指纹和 Artifact 标签。启动与审批创建共同调用 `_current_execution_contract`，它重新从当前 catalog 得到完整身份，并逐项比较请求正文、Effect executor/preparation profile 和四项 Artifact 标签。标签不是旁路权威，而是正文和当前编译合同的第二份不可变一致性证明。

安装态真实回归进一步验证新请求正文四项身份等于 compiled Effect，ApprovalRequest 身份与 ExecutionRequest 完全相等，审批 subjects 精确为 request Artifact 和输入 payload。

### 2. 审批创建对缺身份、漂移和插件缺失失败关闭：通过

`execution_approval_request_create` 不再包含旧 presentation fallback。它必须先通过 `_current_execution_contract`，再从当前 compiled Effect 读取审批 kind、问题、选项、subject 顺序和 projector；任何失败发生在创建 ApprovalRequest 之前。

证据包括：

- legacy `execution_request_create` 生成的缺身份请求不能创建新审批；
- Effect 合同改变后，旧请求不能创建审批，且没有审批 binding；
- 独立补充负例创建“正文含正确完整身份但 Artifact 缺四项标签”的请求，结果为 `execution request labels differ from compiled identity`，没有创建审批；
- 独立补充负例在 Effect 请求创建后卸载插件，再创建审批，结果为 `execution request operation is not installed`，没有创建审批；
- 上述路径 adapter 提交次数始终为零。

审批的幂等重放还会比较既有 ApprovalRequest 的 exact subjects、compiled identity 和 ReviewDocument；合同漂移会先改变完整 compiled identity，不能复用旧决定。

### 3. 架构与 TCAD projector 均来自编译合同并返回固定 ReviewDocument：通过

核心通过 `compiled.implementations[projector_key]` 调用 ApprovalContract 中冻结的 projector 引用，不按领域 Schema 在 Root 中分派 renderer。返回值必须是 `ReviewDocument`，随后由 ApprovalService 继续校验 subject index、JSON pointer、数量和字节界限。

架构 fixture projector：

- 严格要求 `builtin.test.effect`；
- subjects 顺序固定为 `effect_request`、`effect_input`；
- 严格解析 ExecutionRequest；
- 只返回固定 ReviewDocument。

TCAD projector：

- 严格要求 `tcad.study.execute`；
- subjects 顺序固定为 `execution_request`、`reviewed_package`；
- 严格解析 ExecutionRequest 和完整 ReviewedDeckPackage；
- 检查请求 operation id/version/digest 与 projector context 一致；
- 只通过固定 JSON pointers 展示 executor、preparation profile、操作身份、工程、独立审查、求解能力和 resolved inputs，不返回 HTML、模板、URL 或领域 UI callable。

当前 compiled contract 的完整 approval identity 已在调用 projector 前由 Root 复核；其中 approval contract digest 不由 TCAD projector重复实现，避免插件形成第二身份权威。

### 4. execution_start 至服务层重新比较完整身份和精确 subjects：通过

`execution_start` 每次启动都重新调用 `_current_execution_contract`，不复用审批创建时的检查结果。当前完整身份作为显式参数经过 ExecutionBridge 传入 `ExecutionService.authorize`。服务层依次验证：

1. ExecutionRequest 保存的身份等于当前传入身份；
2. Approval 状态已经决定，且选项是两个允许的 execution authorize 选项之一；
3. HumanDecision 绑定该 exact ApprovalRequest；
4. ApprovalRequest kind 为 `execution_authorization`；
5. ApprovalRequest 的 compiled identity 等于当前完整身份；
6. ApprovalRequest.subject_refs 和 HumanDecision.subject_refs 都精确等于数据库冻结的 `(request_ref, payload_ref)`，顺序也一致；
7. 只有全部通过后才写出授权 payload、推进状态并允许 adapter prepare/submit。

独立补充负例使用正确当前 compiled identity，但让 ApprovalRequest/HumanDecision 覆盖错误 payload subject。服务以 `human decision does not bind the exact request and payload` 拒绝，执行保持 `created`，adapter 提交次数为零。说明“身份正确”不能替代“审批对象正确”。

### 5. 决定后的漂移、卸载和旧 fallback 均不可启动：通过

专项真实负例覆盖：

- 审批决定后 Effect 合同变化；
- 审批决定后插件卸载；
- subjects 正确但 ApprovalRequest operation digest 错误；
- 无 compiled identity 的 legacy ExecutionRequest 人为附加一个已经决定、表面允许执行的 ApprovalRequest。

四类请求均不能 authorize/start，状态保持 `created`，adapter 提交次数为零。正向安装态测试则通过真实 loopback UI 决定完成 `created → submitted → collected`，并证明只提交一次。

### 6. 单一控制权威与复杂度边界：通过

生产调用搜索显示 `ExecutionService.authorize` 只有 ExecutionBridge 一个调用方。Root 没有新增执行身份表、缓存、allowlist 或领域审批注册表；身份来自已有 compiled catalog，执行与审批继续写入已有服务。

通用核心的执行身份路径不包含 TCAD、InGaAs 或 curve-score 分支。TCAD 的解析和展示留在 TCAD 插件 projector，适配器副作用留在 runtime plugin。新增可选身份字段只用于严格读取历史 ExecutionRequest；没有把历史对象升级为可授权对象。

因此本实现没有为了闭合授权而再造一套执行状态机，也没有把领域知识搬回核心。其复杂度与“外部副作用必须绑定当前编译合同和精确人类决定”这一必要保证相称。

## 独立执行证据

固定 14 项命令：

```bash
PYTHONDONTWRITEBYTECODE=1 pytest -q \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_baseline_effect_lifecycle.py \
  tests/operations/test_operation_invoke_installed.py \
  tests/operations/test_runtime_plugin_configuration.py
```

结果：`14 passed in 26.83s`。

其余证据：

- `PYTHONDONTWRITEBYTECODE=1 pytest -q tests/operations`：`207 passed in 66.48s`；
- `PYTHONDONTWRITEBYTECODE=1 pytest -q`：`241 passed in 71.56s`；
- 六个生产实现文件和专项测试使用 Python `compile(..., "exec")` 静态编译通过；
- `git diff --check` 通过；
- 安装态架构 Effect 真实 loopback UI 生命周期、源码态 TCAD Effect/projector/收集链均包含在上述测试中；
- 正确身份但错误 subjects、正确正文身份但缺 Artifact 标签、审批前插件卸载三个独立补充负例均失败关闭。

计划明确把根发布清单重建放在本报告纳入后一次完成，因此本轮没有把审查前的临时清单误称为最终发布证据。R4-D-D 仍需独立完成固定安全 renderer、历史 raw fallback 和浏览器安全负例；这些尚未实现的内容不属于本次执行身份阶段的放行声明。
