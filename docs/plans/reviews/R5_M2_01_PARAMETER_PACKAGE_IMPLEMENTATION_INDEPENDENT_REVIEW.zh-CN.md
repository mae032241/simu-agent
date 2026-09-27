# R5-M2-01 参数证据包实现独立审查

日期：2026-09-01

结论：**FAIL（不通过）**

阶段门：**不得放行 M2-02**。本结论只审查 M2-01，不否定 M0、M1 的历史通过结论，也不把
M2-02、M2-03 或完整 TCAD 科学闭环纳入本轮完成范围。

## 1. 审查范围与方法

审查基线是当前 `baseline/8765-codex` 工作树相对 `HEAD` 的未提交候选。工作树包含大量早于本阶段
且与本阶段无关的修改，因此本报告没有把整棵工作树误称为 M2-01 的精确差异；审查范围由以下活动
文件和符号共同限定：

- `docs/plans/R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md`；
- `docs/plans/evidence/R5_M2_01_PARAMETER_PACKAGE_IMPLEMENTATION_EVIDENCE.zh-CN.md`；
- `docs/ARCHITECTURE.zh-CN.md`、最小设计宪章和 33 项约束登记；
- `tcad_artifact.parameter_operations` 中的参数包、展开、审计和资格投影；
- 两个参数角色提示；
- M2 参数包、目录权威、安装入口、通用 Transform 和后端能力测试；
- 真实 `open_runtime`、Root、`LocalTrustedBackend` 和本地 Worker 的一次性纵向探针。

审查使用了跨边界审查、简化审查和变更范围检查规则。除本报告外，没有修改计划、证据、生产代码或
测试。

## 2. 阻断项

### B1：真实提取 Run 的参数包不能进入确定性展开，独立审查拓扑形成闭环

这是本轮的首要阻断项。

提取 Operation 在
`plugins/tcad_artifact/tcad_artifact/parameter_operations.py:1187` 把
`parameter_evidence_package` 声明为必须由 `tcad.parameter.evidence.audit.v1` 审查的输出；展开
Operation 又在同文件 `:952`—`:960` 以普通 `prior_signal` 输入消费该包。通用准入规则在
`src/scidiscovery/artifact_agent/interfaces/mcp_root_operation_routes.py:1130`—`:1149` 明确规定：一个
待审输出只能直接进入其精确 reviewer，其他 Operation 必须同时绑定已经完成的精确审查结果。

但精确 reviewer 又要求先提供展开后的四个对象和覆盖报告，见
`parameter_operations.py:1004`—`:1033`、`:1203`—`:1228`。于是实际拓扑是：

```text
提取 Run 完成
  -> 展开要求先有审查
  -> 审查要求先有展开和覆盖
  -> 无合法下一步
```

独立探针通过真实 Root 和本地 Worker 完成了提取 Run，再对该 Run 的封存输出执行展开 preflight，
得到：

```text
{'admissible': False,
 'reason_code': 'input_independent_review_missing',
 'port': 'parameter_evidence_package',
 'executor_kind': None}
```

现有正例没有发现该问题，因为
`tests/operations/test_m2_parameter_package.py:226`—`:245` 直接用 `ArtifactService.register` 摄入一个
没有生产 Operation 和 review policy 的包，再测试展开；它没有消费真实提取 Run 输出。

影响：目录、提取 preflight、Run 创建和单文件提交分别都能成功，但计划声明的
“提取→展开→独立审计→资格”科学能力必然中断，未满足 M2 的“公开能力与默认运行能力一致”。

最小修复方向：在现有编译 review 语义内重新放置审查边，使包可以先经过唯一的机械展开，再由审计
绑定原包、展开族、覆盖和冻结来源。可行的小方案是让提取包保持明确的 provisional 语义，把 review
subject 放到展开后的一个精确主对象，并让审计同时核对完整展开族；不得在核心准入中增加
“support Transform 特许绕过 reviewer”的 TCAD 特例或第二准入规则。修复后必须以真实提取 Run 输出
作为展开输入新增正例。

### B2：资格投影仍依赖已删除的旧 Task 来源与父链语义，现行 Run v1 必然拒绝

即使 B1 被解除，当前参数资格审批仍不能建立。

第一处错位是来源类型。Run v1 的通用生产者族只产生
`source_kind="run_input"`，见
`mcp_root_operation_routes.py:414`—`:423`；参数资格投影却只接受
`task_input`、`web_snapshot` 和 `pdf_excerpt`，并只从前两类冻结来源，见
`parameter_operations.py:484`—`:499`。因此任何真实提取 Run 都会命中
`parameter extraction has an unsupported evidence-source kind`。

第二处错位是输出父链。Run v1 在
`src/scidiscovery/artifact_agent/service/runs.py:695`—`:725` 将 Agent 输出父引用定义为精确 Run 输入；
instruction 保存在 Run 请求中，不是一个父 Artifact。参数投影仍在
`parameter_operations.py:579`—`:586` 假定父链前面额外存在一个 instruction，并要求
`parent_refs[1:]` 等于审计输入。真实审计输出因此必然再被拒绝。

这两处不是安全门过严，而是插件仍按旧生命周期解释新的唯一 Run 权威。最小修复应只让 TCAD 投影
消费 Run v1 已有的 `run_input` 和精确输入父链；不得为了兼容插件反向在核心恢复旧 `task_input`、
instruction Artifact、旧 Task 表或双写来源类型。

修复后必须新增一条真正创建资格请求的纵向正例，并分别保留错误 producer family、缺失或增加冻结
来源、父链替换和审计非通过的负例。

### B3：提取输出尚未在提交边界绑定实际来源别名，修订不继承旧审查也没有 M2 专项证据

`ParameterEvidencePackage` 能证明参数观测、来源目录和 intake foundation 在包内闭合，但提取上下文
验证器 `parameter_operations.py:326`—`:338` 只检查可选 checklist 的 objective；输出端口在
`:905`—`:916` 也只把 `required_parameter_checklist` 暴露给该验证器。它没有证明包内
`source_key` 是当前 Run 的真实 `source_material` 别名。

角色提示要求使用精确 task-local source key，审计上下文也会拒绝未绑定别名，但当前错误只会在更晚
的审计阶段暴露。解除 B1 后，这会允许一个来源身份未绑定的 provisional 包先被展开。对于
EVD-001、ROLE-002 和“来源先冻结再使用”，更小且更清楚的边界是在提取提交时用既有 context
validator 核对目录/观测来源与已绑定的 `source_material` 别名；不需要新增来源实体、表或核心分支。

此外，通用核心按精确 subject ref 判断 reviewer，设计上没有观察到 revision 自动继承旧审查的直接
旁路；但 M2 测试没有建立“新参数包 revision＋新展开族＋旧 audit”负例，而当前链路又无法运行到
该边界。因此本轮不能把 revision 语义标为已闭合。返修测试应证明旧 audit 不能满足新包或新展开
主对象的审查要求。

## 3. 通过的设计判断

以下方向是合理的，应保留而不是推翻：

1. `ParameterEvidencePackage` 是领域数据对象，不是新的控制状态；它把一次 Agent 科学判断收成一个
   主结果，再复用既有 Transform 多输出登记，符合 M2-A 的最小方向。
2. Agent 仍负责来源取舍、参数选择、冲突、缺失项和不确定性；
   `expand_parameter_evidence` 只解析已验证包并复制四个规范化对象，没有生成来源、参数或 verdict。
3. 展开结果以包为唯一父引用，幂等指纹和四个输出标签均由统一 `operation_invoke` 路径产生；逐字节
   比较适合证明“机械展开没有改写科学内容”，本轮没有发现为了测试而放宽字节等价的必要。
4. 参数包和展开符号没有进入 `src/scidiscovery`；TCAD 插件仍通过唯一
   `scidiscovery.plugins` 入口和一次 `CompiledCatalog` 编译。五插件目录复算为 47 个 Operation，
   `public/support=26/21`，`Agent/Transform/Approval/Effect=22/21/3/1`，目录摘要与实施证据一致。
5. 没有观察到本阶段新增 Run 状态、集合提交协议、数据库表、Root 工具、第二目录、第二 preflight、
   第二 invoke 或核心 TCAD 名称分支。Root 工具仍为 30 个。
6. 单独看提取 Operation，Local 后端能力投影、catalog、preflight、invoke 和单结果 Run 合同是一致
   的；问题发生在其声明的下一条 support/review 边，而不是又需要实现 Agent collection。

因此，本轮失败不说明“单包＋机械展开”抽象过重。相反，失败来源是新闭包与旧审查/资格合同没有沿
真实 Run 路径接通。

## 4. 33 项约束与奥卡姆判断

本仓库没有逐项证明 33/33 语义符合的自动验证器；结构测试只证明登记中存在 33 个唯一约束。本报告
不把一个绿色结构测试夸大为全部符合。

与 M2-01 直接相关的判断如下：

- AUTH-001、PLG-001、PLG-002：未见新增控制权威、第二入口或核心领域分支；不退化。
- ROLE-001、DET-001、DET-002：Agent/Transform 科学所有权分配和机械展开本体合理；不退化。
- TOP-002、ROLE-002：真实提取输出被同一通用 admission 拒绝进入声明的 support 路径，完整生命周期
  合同未闭合；当前不符合阶段完成要求。
- EVD-001：包内来源能闭合，但与精确 Run 输入别名的绑定发生得过晚，需在既有插件 context validator
  边界补齐；当前证据不足。
- IMM-001：包和四个派生 Artifact 均不可变，父链没有原地修改；未见退化。
- IMM-002、LIN-002：核心精确 ref 规则仍在，但 M2 参数 revision 的旧审查拒绝负例缺失；不宣称闭合。
- SEC-002：Local 原生工具隔离继续保持既有 `known_issue`，本阶段没有扩大或掩盖它。

从奥卡姆原则看，增加一个包 Schema 组件和一个窄 Transform 组件是有独立消费者的净增加，可以接受；
返修不得引入 core 特例、第二来源类型权威或旧 Task 兼容层。当前主要问题不是实体太多，而是现有
review/producer-family 语义连接错误。

## 5. 独立测试证据

全部命令串行执行，使用 7 GiB 虚拟内存上限和 `MALLOC_ARENA_MAX=2`。

### 5.1 聚焦回归

```text
ulimit -v 7340032
export MALLOC_ARENA_MAX=2
pytest -q \
  tests/operations/test_m2_parameter_package.py \
  tests/operations/test_r3_catalog_authority.py \
  tests/operations/test_catalog_installed_entrypoint.py \
  tests/operations/test_general_transform_operations.py \
  tests/operations/test_l6_runtime_capabilities.py

27 passed in 43.36s
```

这证明单包模型、直接摄入包的 Transform、目录编译、干净安装入口和既有后端能力测试通过；它不证明
真实提取输出可以进入展开。

### 5.2 33 项登记结构

```text
ulimit -v 7340032
export MALLOC_ARENA_MAX=2
pytest -q tests/operations/test_architecture_constraint_matrix.py

1 passed in 0.04s
```

### 5.3 真实 Run 负探针

执行命令为：

```text
ulimit -v 7340032
export MALLOC_ARENA_MAX=2
export PYTHONPATH=src:plugins/tcad_artifact:plugins/curve_score
python - <<'PY'
# 用 open_runtime + RootToolFacade 创建实例和冻结来源；
# operation_invoke 创建 tcad.parameter.evidence.extract.v1；
# LocalWorkerMCPRouter 打开 Run、写入合法单包并 worker_submit_result；
# 对该 Run 的封存 output_artifact_name 调用 expand.v1 的 operation_preflight。
PY
```

输出是 B1 记录的 `input_independent_review_missing`。探针使用真实编译目录、Root、RunService、Local
工作区和封存 Artifact，没有直接登记被测参数包。

### 5.4 其他检查

```text
git diff --check
# 通过，无输出
```

本审查没有重复运行证据文件中的全量 213 项：目标聚焦回归全部通过后，真实负探针已经证明阶段门
失败；重复全量测试不能推翻可达的合同断路。

## 6. 返修后重新审查的最小完成门

1. 真实提取 Run 输出能通过统一 preflight/invoke 进入唯一机械展开，不新增 core 例外；
2. 精确独立 audit 同时绑定原包、完整展开族、覆盖和全部冻结 Run 输入；
3. 资格 Approval 通过现行 Run v1 的 `run_input` 和精确输入父链建立，并能生成 loopback 审批请求；
4. 缺失/额外 frozen source、错误 producer family、非规范展开、旧 audit 绑定新 revision 均从真实入口
   失败关闭；
5. 包内来源键在提取提交边界绑定当前 Run 的精确来源别名；
6. 保持零新增 Run 状态、表、Root 工具、注册入口、preflight/invoke 和核心领域分支；
7. 聚焦测试、干净安装入口和全量回归通过，并由新的未参与返修者独立复审。

在以上条件满足前，M2-01 不能标记为完成，M2-02 不得开始。
