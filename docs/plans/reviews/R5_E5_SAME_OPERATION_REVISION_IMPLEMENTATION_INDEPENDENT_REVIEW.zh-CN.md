# R5 E5 同一 Operation 创建／修订实现独立审查

日期：2026-09-05  
审查轮次：P4 第一轮  
结论：**FAIL**  
阻断项：**1 项（包含两个同源调用面）**  
部署放行：**否**

## 1. 审查范围与方法

本轮只审查以下计划、实现证据、生产实现和对应测试，没有修改生产代码或测试：

- `docs/plans/R5_E5_SAME_OPERATION_REVISION_PLAN.zh-CN.md`；
- `docs/plans/evidence/R5_E5_SAME_OPERATION_REVISION_IMPLEMENTATION.zh-CN.md`；
- 通用直接修订合同、Run assignment／workspace／submit 和 Root admission 实现；
- 可选图插件的 Operation、父链 guard、问题指纹和下游 figure bundle guard；
- 盲插件、图证据闭环、既有必需基线修订、插件所有权和33项约束测试。

审查口径是：`OperationSpec` 是唯一行为事实源；静态函数只识别能力，动态函数只从本次冻结输入派生
是否激活修订；核心不得认识图领域；创建和修订均须失败关闭；不得新增模式状态、平行注册表或针对
当前 E5 实例的兼容分支。

## 2. 结论摘要

总体设计已被正确实现了绝大部分：同一个
`science.evidence.extract.figure.v2` 可以创建或修订 `ScientificIntake`，修订端口严格全有或全无，
旧结果保持不可变，每版必须重新经过独立 figure audit，修订次数和无进展规则闭合，下游也不再维护
Intake producer-id 名单。核心实现没有图领域名称、额外状态或第二注册表。

但“唯一 `active_direct_revision_ports()` 覆盖所有动态调用面”尚未真正成立。一个 Run 调度入口自行
重算是否存在修订基线，另一个提交校验入口把源文件名集合当成端口名集合传给该 helper。当前端口
基数限制使真实 E5 测试碰巧仍能通过，但这已经形成第二套隐式激活约定，违反本计划为避免再次发生
多层行为断裂而设立的核心收口条件。因此 P4 不能通过。

## 3. 阻断项

### 3.1 动态修订激活仍有两处未服从唯一总函数

#### A. `RunService.schedule()` 自行按 usage 推断激活

`src/scidiscovery/artifact_agent/service/runs.py:135` 直接在冻结输入中寻找
`usage == "revision_base"`，再据此执行单后继检查。这个判断在当前合法合同上与 helper 结果相同，
但它仍是一个独立的动态模式判定面。以后如果直接修订形状继续收紧或变化，Root、workspace 和 Run
调度可能再次出现不同解释。

最小正确修复是：对 `frozen_inputs` 调用
`active_direct_revision_ports(compiled, (item.port_name ...))`，只从其返回的 base 端口取得精确
`artifact_ref`；后续既有 `_revision_successor()` 查询、SQLite 状态和错误语义均不改变。

#### B. submit 校验向 helper 传入了错误命名空间

`src/scidiscovery/artifact_agent/service/run_outputs.py:125` 调用
`active_direct_revision_ports(compiled, input_bytes)`。这里 `input_bytes` 的键是 `source_name`，而
helper 的公开合同要求 `actual_bound_port_names`。目前 direct revision base 被限定为单项，binder 恰好
令该项 `source_name == port_name`，所以测试通过；但这是未声明的跨层命名耦合，不是由 helper 或
函数类型保证的事实。一旦输入别名规则调整，unchanged-base 校验会被静默跳过。

最小正确修复是：让 `validate_run_output()` 显式获得本次冻结的端口名集合，并只把该集合传给 active
helper；现有按 `source_name` 索引的字节映射继续供基线取值和 context validator 使用。不要把
helper 放宽成同时猜测端口名和源名，也不要增加 `revision_mode` 参数或持久化字段。

这两处属于同一个阻断：动态激活权威尚未唯一化。除此之外，没有发现第三个动态模式判定旁路。
历史链遍历和 `_revision_successor()` 内对已冻结 `usage` 的查询是在解释既有父链，不是为当前调用
另立激活权威；catalog、声明默认值和 Hardened 能力判断则属于静态能力面，可以继续使用静态合同。

## 4. 其他审查结果

| 审查项 | 结论 | 依据 |
| --- | --- | --- |
| 可选形状编译门 | 通过 | 只接受唯一 `0..1` base/request、恰好二成员且无审批的 cohort、同型单输出、精确 reviewer、正数上限和问题指纹；任一畸形均由 catalog 失败关闭 |
| 既有必需基线修订 | 通过 | `(1,1)` 分支保留原语义；通用、假设及 TCAD 相关测试未发现本改动造成的回归 |
| 同一图 Intake Operation | 通过 | 可选插件中只有 `science.evidence.extract.figure.v2`；未注册 `science.intake.revise.figure.v1` |
| 创建路径 | 通过 | 未绑定二端口时无 revision assignment、无预填草稿、无修订次数／单后继门；同 digest 的零 base／零 request Run 是合法链根 |
| 修订路径 | 通过 | 全有或全无；写时复制完整对象；精确非通过审查、同一完整图族、差异、无进展、两次上限和新审查均有实现与测试 |
| 下游 producer 解耦 | 通过 | `figure_parentage` 不特判 Intake producer operation id，只检查 Intake 输出端口、完整族父链、精确新 figure audit 父链与 pass；Root 仍按编译 review edge 验证真实 producer/reviewer |
| 角色边界 | 通过 | evidence Agent 创建／修订，独立 auditor 审查；Worker 不授予资格、不改曲线点、不继承旧 verdict |
| 插件边界 | 通过 | 图族 guard、指纹、prompt 和工具均在可选插件；通用核心未出现 `figure`、`curve` 或 Intake 领域分支 |
| 奥卡姆与状态面 | 通过 | 复用现有端口、cohort、review、Run 和 Artifact；没有新增模式字段、数据库状态、注册表、兼容层或修订状态机 |

下游 guard 仍明确要求 request、materializer 和 figure audit 的稳定 Operation 身份，这是可选图插件
内部对完整族来源的领域合同，不是 Intake 创建／修订 producer 名单，也没有构成核心硬编码或准入
旁路。

## 5. 独立测试证据

所有测试均串行、禁用 pytest 外部插件并限制虚拟内存为 4 GiB。

### 5.1 P3 聚焦矩阵

```text
56 passed in 7.90s
最大常驻内存：109024 KiB
swap：0
```

覆盖盲可选合同正负例、创建／修订 assignment、草稿、unchanged 拒绝、图族创建—两次修订—逐版
独立审查—bundle、半组／错族／无进展／超限拒绝、插件投影和既有必需修订公共路径。

### 5.2 必需基线补充回归

`test_hypothesis_review_routing.py` 与 `test_l4_local_tcad.py` 的结果为：

```text
20 passed, 1 failed in 4.18s
最大常驻内存：119460 KiB
swap：0
```

唯一失败是既有 Hardened TCAD 初始 author 负例期待
`runtime_backend_capability_missing`，实际入口返回 `operation_runtime_unavailable`。该用例不执行
修订、可选输入或图插件；同一运行中的必需基线修订测试通过。因此它不是本次 P4 阻断，但正式全量
回归时仍应由其所属改动统一修正测试与当前错误合同，不能把本轮结论写成全仓测试全绿。

### 5.3 33项约束结构门

```text
1 passed in 0.06s
最大常驻内存：47484 KiB
swap：0
```

该测试证明约束账本结构门通过；本报告对最小授权、单一编译权威、不可变结果、独立审查、插件解耦
和无新增控制实体另做了语义审查，未把结构测试等同于全部33项行为实证。

## 6. 最小返修与复审边界

只需修改以下生产边界：

1. `src/scidiscovery/artifact_agent/service/runs.py`：Run 调度的当前调用激活判断改用唯一 helper；
2. `src/scidiscovery/artifact_agent/service/run_outputs.py` 及其唯一调用者：把冻结端口名显式交给提交
   校验，字节映射仍保持 source-name 语义；
3. 对应测试增加两个定点断言：Run 调度不自行解释 `revision_base`；提交差异校验使用实际端口名，
   而不是依赖 singleton source-name 巧合。

返修后重跑本报告的56项聚焦矩阵，并至少重跑
`test_hypothesis_review_routing.py` 和 `test_l4_local_tcad.py` 中修订相关用例。无需修改图插件、
OperationSpec ABI、数据库、目录、审批、Hardened 后端、生产部署或历史兼容层；也不得借此扩大为
通用模式系统。

## 7. 最终判断

**FAIL，阻断项 1。** 科学拓扑和插件方案本身正确、最小且已被测试实证；当前唯一未闭合的是动态
修订激活仍有两个同源调用面没有严格服从唯一总函数。完成上述小范围收口并通过复审后，才可进入
构建、部署和真实 E5 创建／审查／修订链。

---

## 8. P4 第二轮独立复审

日期：2026-09-05  
结论：**PASS**  
剩余阻断项：**0**  
构建与部署放行：**是**

### 8.1 首轮阻断关闭情况

| 首轮问题 | 第二轮核对结果 | 状态 |
| --- | --- | --- |
| `RunService.schedule()` 自行按 usage 判断当前调用是否激活修订 | `src/scidiscovery/artifact_agent/service/runs.py:135` 现在对冻结输入的 `port_name` 调用唯一 `active_direct_revision_ports()`，并只从返回的 base 端口取得精确 Artifact 引用；既有单后继查询和状态未改变 | 已关闭 |
| submit 把 source-name 集合误作 port-name 集合 | `validate_run_output()` 新增显式 `input_port_names`；唯一生产调用者从冻结 `RunStatus.inputs` 传入端口名，active helper 不再读取 `input_bytes` 的键 | 已关闭 |

提交校验仍用 source-name 字节映射取得基线内容和构造 context validator 输入。这是该映射原有且明确
的职责；是否激活修订已经只由冻结端口名决定。即使未来 source-name 规则变化，错误映射最多导致
“基线缺失”并失败关闭，不会再静默绕过 unchanged-base 规则。

### 8.2 唯一调用面复核

再次全局检索后：

- assignment、草稿预填、workspace、Run 调度、提交差异检查、Root 单后继、Root 修订次数／无进展
  和 producer direct-base 均调用同一个 `active_direct_revision_ports()`；
- catalog 编译、Worker 后端能力判断和 Worker 可见静态合同继续调用
  `direct_revision_ports()`，职责仍是静态能力识别；
- 历史链遍历与 `_revision_successor()` 对已冻结 `usage` 的读取只用于恢复父链和查询后继，不推断
  当前调用模式，不是第二激活权威；
- 没有新增 `revision_mode`、active 标志、数据库字段、缓存、注册表或兼容分支。

因此首轮指出的单一事实源偏差已经实质消失，而不是通过更改命名或增加状态掩盖。

### 8.3 第二轮独立测试

测试保持低内存、串行执行：

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

结果：

```text
56 passed in 7.36s
最大常驻内存：108756 KiB
swap：0
```

该矩阵同时经过了 `validate_run_output()` 新参数的全部现有直接调用，继续证明可选创建、同 Operation
修订、unchanged 拒绝、完整图族、精确独立审查、无进展、两次上限、下游 bundle 和既有必需基线
公共路径。

遵照复审任务边界，本轮没有重跑或扩展首轮已经明确隔离的 Hardened 错误码期望失败；其状态仍是
非本轮问题，不影响 E5 同 Operation 修订实现判定。

### 8.4 架构与范围判断

返修只改动通用 Run 调度和输出校验之间的参数传递，没有修改图插件、OperationSpec ABI、数据库、
Artifact、审批、Hardened 后端或任何科学 Schema。可选图插件仍只有一个 Intake 生产 Operation，
下游仍不维护 Intake producer-id 名单，独立审查与完整族门没有放宽。

这符合 `OperationSpec` 单一事实源、最小上下文、不可变结果、独立审查、插件解耦、失败关闭和奥卡姆
原则，也没有为了当前 E5 实例引入专用补丁。

### 8.5 第二轮最终判断

**PASS，剩余阻断项 0。** 首轮唯一阻断已按报告规定的最小方案关闭；P4 实现审查通过，可以进入
clean 构建、部署，并在新 Operation digest 下从图 Intake 创建开始继续真实 E5
创建—独立审查—同 Operation 修订—再次独立审查链。
