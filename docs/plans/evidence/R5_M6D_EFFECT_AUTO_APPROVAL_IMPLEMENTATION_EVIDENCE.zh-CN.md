# R5-M6D Effect 自动审批请求实施证据

状态：首次独立审查 FAIL 后的两项根因返工已通过全新独立复审；仅放行 M6 整体回归与独立终审，M7 未放行

## 1. 本阶段回答的问题

旧 Effect 链路先由 `operation_invoke` 创建冻结的 `ExecutionRequest`，再要求调度器调用
`execution_approval_request_create`。第二步重新从同一个编译 `ApprovalContract` 组装 subjects、问题、
选项、展示文档和编译身份。它不是新的用户决定，只是重复的控制面编排；遗漏该步骤就会留下无法进入
人工决定的执行请求。

M6-D 把这一步收回 Effect 行为闭包：`operation_invoke` 创建或幂等找到 Execution 后，立即以同一
编译合同建立精确、待人工决定的 ApprovalRequest，并返回其审批状态与精确回环 UI 地址。

## 2. 当前调用链

```text
operation_preflight（纯查询）
  → operation_invoke
      → 创建/找到不可变 ExecutionRequest
      → 私有 _ensure_execution_approval
      → 返回 Execution 状态 + pending Approval + 精确 review_url
  → 用户仅在回环 UI 作决定
  → approval_status（只读）
  → execution_start（显式副作用边界）
  → 有界 execution_sync
```

`operation_invoke` 不记录人工决定、不调用 adapter submit、不推进 Execution 状态。查询仍不写状态；
只有 `execution_start` 消费已封存的精确 UI 决定并触发领域 adapter。

## 3. 单一合同与失败关闭

私有创建函数从当前唯一 `CompiledCatalog` 和已冻结 ExecutionRequest 解析：

- 精确 Operation id、version、digest 和 approval-contract digest；
- 精确 request/payload subject 顺序；
- 编译问题、选项和 projector；
- projector 生成的受限 `ReviewDocument`。

重复调用只接受同名审批中与上述 kind、subjects、问题、选项、编译身份和展示文档全部相同的请求；
漂移或错误绑定失败关闭。审批标识直接由不可变 `execution_id` 派生，审批服务幂等键也绑定该
Execution；因此 ApprovalRequest 已提交但语义绑定失败时，重试取回同一个请求并补做绑定，不会产生
第二个可决定权威。`execution_start` 继续重新核验当前编译合同和请求标签，因此：

- 审批后合同漂移拒绝；
- 插件卸载拒绝；
- 错误 compiled identity 拒绝；
- 无 compiled identity 的历史请求拒绝；
- 新 execution revision 获得新的 pending 审批，旧 revision 的决定不继承；
- 未决定时 adapter submit 次数保持零。

## 4. 删除和返回面

- 从 `ROOT_TOOLS` 删除公共 `execution_approval_request_create`；
- 删除同名生产方法，只保留 Effect 内部唯一 `_ensure_execution_approval` 调用点；
- 部署安装和 MCP 探针把旧名称列入退役工具负集合；
- Root 公共工具净减 1，当前为 26 个；没有新增数据库表、运行状态、注册表或 Operation 字段；
- `approval_status` 对 pending 请求使用 ApprovalService 已保存的 request-specific `review_path`，返回
  含访问令牌的精确回环地址，不再只返回审批首页；
- 调度器源提示、当前 `AGENTS.md` 和中英文架构说明同步为自动创建链路。

本阶段不改变 `OperationSpec`，Operation ABI 保持 11，既有目录摘要不漂移。

Effect 的唯一编译规则明确固定审批 subject 顺序为：ExecutionRequest 输出在前、执行载荷输入在后。
该顺序与 projector、ApprovalRequest、HumanDecision 和 `ExecutionService.authorize()` 的精确 subject
合同一致；反向声明在目录编译期以 `effect_approval_contract_mismatch` 拒绝，不再延迟到人工决定后的
`execution_start`。

## 5. 自动化证据

Effect 与身份聚焦回归：

```text
pytest -q \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_baseline_effect_lifecycle.py
8 passed（包含返工后的提交/绑定故障恢复负例）
```

覆盖：自动创建、精确 subjects、request-specific URL、旧公共工具不可达、重复调用幂等、新 revision
独立审批、人工决定前不提交、UI 决定后显式 start/sync/collect、合同漂移、插件卸载、错误身份和历史
请求。

返工后的编译与 Effect 聚焦回归：

```text
pytest -q \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_baseline_effect_lifecycle.py \
  tests/operations/test_catalog_negative_cases.py \
  tests/operations/test_catalog_compile.py
51 passed in 40.89s
```

跨边界回归：

```text
pytest -q \
  tests/operations/test_catalog_compile.py \
  tests/operations/test_catalog_negative_cases.py \
  tests/operations/test_l1_minimal_runtime_projection.py \
  tests/operations/test_l6_runtime_capabilities.py \
  tests/operations/test_runtime_plugin_configuration.py \
  tests/operations/test_l4_local_tcad.py \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_baseline_effect_lifecycle.py \
  tests/artifact_agent/test_platform_configuration.py \
  tests/artifact_agent/test_deploy_scripts.py
109 passed in 48.66s
```

最终在 7 GiB 虚拟内存上限下串行运行：

```text
pytest -q
257 passed in 113.30s
```

同时通过 Python 语法编译、旧生产方法/工具声明零命中、部署退役名称断言和 `git diff --check`。
语法编译生成的 TCAD Python 3.6 兼容脚本缓存按既定回归前规则删除，没有作为产品文件保留。

## 6. 首次独立审查与返工

首次审查报告
`reviews/R5_M6D_EFFECT_AUTO_APPROVAL_INDEPENDENT_REVIEW.zh-CN.md` 结论为 FAIL，未放行后续，发现：

1. 旧实现使用随机 approval id，并以该随机 id 构造幂等键；ApprovalService 已提交而 scheduler
   binding 失败后，相同 `operation_invoke` 会创建第二个可决定、可授权请求；
2. 编译器只比较 Effect subject 端口集合，允许反向顺序，但执行授权服务固定按
   `(request_ref, payload_ref)` 校验，导致合法编译合同到人工决定后才失败。

返工没有添加事务协调器、恢复表、清理任务或兼容层：

- `apr_<execution_id>` 成为该 Execution 审批的稳定唯一标识，幂等键为
  `execution-approval:<execution_id>`；
- 故障注入测试在第一次审批绑定抛错后确认数据库仅有一个 pending 请求，重试绑定同一 id，仍只有
  一个请求且 adapter 未提交；
- 目录编译器把已有的单输入/单 ExecutionRequest 输出 Effect 合同进一步闭合为固定 subject tuple，
  并增加反向顺序编译负例。

首次报告永久保留其 FAIL 结论；修订实现不得继承该 verdict，当前等待全新独立复审。

## 7. 未实施内容

- 不自动代替用户决定；
- 不自动调用 `execution_start` 或 `execution_sync`；
- 不合并科学资格审批与外部执行授权；
- 不增加审批恢复状态机或第二 Execution 权威；
- M7 最终安装矩阵、真实 Agent/TCAD 纵向回归和 M6 整体终审尚未放行。
