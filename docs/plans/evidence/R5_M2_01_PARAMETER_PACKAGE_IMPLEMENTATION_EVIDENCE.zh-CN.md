# R5-M2-01 参数证据包实现证据

日期：2026-09-01

状态：首轮独立审查 FAIL 的三项阻断已返工并通过全新独立复审；M2-01 完成，仅放行 M2-02

对应计划：`../R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md`

## 1. 本阶段回答的问题

旧参数提取 Operation 要求一个 Agent 在同一 Run 中提交四个带集合协议的输出。默认
`LocalTrustedBackend` 不实现 Agent 集合提交，因此目录虽然公开该能力，preflight 却必然以
`agent_collection_outputs` 拒绝。继续扩建 Run 集合状态机会使轻量主干重新变重。

M2-01 改为：

```text
参数提取 Agent
  -> 一个 ParameterEvidencePackage
  -> tcad.parameter.evidence.expand.v1 确定性展开
  -> ScientificIntake / ParameterRequirements / DeviceParameters / SourceCatalog
```

Agent 仍拥有来源判断、参数选择、缺失项和不确定性；展开 Operation 只验证同一个包内四类对象的
科学闭合关系并机械复制规范化字节，不产生科学选择。

## 2. 实现边界

### 2.1 单一 Agent 输出

`tcad.parameter.evidence.extract.v1` 现在只有一个输出端口
`parameter_evidence_package`，`max_files=1`。新 `ParameterEvidencePackage` 复用既有四个领域模型，
并在一个模型验证器中检查：

- 四类对象共享同一精确研究目标；
- 参数需求、选值和来源满足既有确定性覆盖规则；
- 参数观测只引用包内已声明来源；
- 来源目录被科学基础中的来源闭合覆盖；
- 同一来源在目录与科学基础中的来源类型一致。

没有增加集合草稿、集合提交、Run 状态、数据库表或领域专用任务实体。

### 2.2 确定性展开

新增 support Operation `tcad.parameter.evidence.expand.v1`。它消费一个已验证证据包，输出四个既有
类型对象。四个结果都以证据包为唯一父 Artifact；相同名称和相同请求保持幂等。

独立审计 Operation 同时消费原始证据包和四个展开对象。审查边位于展开后的
`scientific_intake`，因此原始包可先进入唯一机械展开，审计者再同时核对完整展开族。上下文验证器
要求展开对象与包内对应对象的
规范化字节完全相同，拒绝重新解释或静默修订。参数资格审批也分别绑定：

- Agent 提取 Run 的单成员 producer family；
- 确定性展开的完整 producer family；
- 四个展开对象到原始包的精确父链；
- 原提取 Run 的冻结来源和可选参数清单；
- 独立审计、确定性覆盖和既有人工决定合同。

通用 Transform producer family 原先没有投影其已编译 `ReviewSpec`，导致审批投影看不到 Transform
审查边。Root 的唯一 producer-family 构造现与 Agent producer family 一样，从同一
`CompiledOperation.spec.review` 投影 reviewer 和 subject outputs；没有新增目录、审查表或 TCAD
分支。

资格投影不再接受旧 Task 的 `task_input/web_snapshot/pdf_excerpt` 来源类型，也不再假定 instruction
Artifact 位于父链首项。它只消费当前 Run v1 已有的 `run_input`，并要求审计输出父引用精确等于按
OperationSpec 顺序绑定的全部输入。

### 2.3 角色合同

参数提取者提示明确只写一个完整证据包，不再要求 sibling 文件或集合提交；参数审计者提示明确同时
核对包与确定性展开，差异必须拒绝。没有将机械拆包工作交给 Agent。

## 3. 跨边界验证

新增 `tests/operations/test_m2_parameter_package.py`，覆盖：

1. 参数提取 Agent 只有一个输出且默认 Local 后端支持；
2. 公开目录包含该 Operation，同一请求的 preflight 可通过，且 preflight 不创建 Run；
3. support 展开通过统一 `operation_invoke` 执行，相同请求幂等；
4. 四个输出的内容、标签和唯一父引用精确绑定原始包；
5. 包内研究目标漂移在进入运行时前失败关闭；
6. 审计上下文拒绝任何不同于证据包的展开字节。
7. 真实 Local Run 完成参数提取后可以依次进入展开、覆盖、独立审计、intake split，并实际创建待人工
   决定的参数资格请求；
8. 提交边界要求包内来源键集合精确等于当前 Run 的 `source_material` 局部别名，并保留可选 checklist
   的完整科学字段；
9. 缺失或增加冻结来源、伪造展开族、失败审计、来源别名造假、用旧 audit 审查新 revision 均失败
   关闭。

目录权威和安装入口测试同步冻结：提取单输出、审查边、展开 support Operation 和完整 47 项
Operation id。没有新目录、第二 preflight 或第二 invoke。

## 4. 复杂度与能力变化

| 指标 | M1 | M2-01 | 变化 |
|---|---:|---:|---:|
| `src/scidiscovery` Python | 96 文件 / 26,116 行 | 96 文件 / 26,126 行 | +10 行 |
| 插件 Python | 45 文件 / 22,763 行 | 45 文件 / 22,875 行 | +112 行 |
| 插件组件 | 220 | 222 | +2 |
| Operation | 46 | 47 | +1 support Transform |
| public / support | 26 / 20 | 26 / 21 | 0 / +1 |
| Agent / Transform / Approval / Effect | 22 / 20 / 3 / 1 | 22 / 21 / 3 / 1 | 0 / +1 / 0 / 0 |
| Local 可运行公开 Agent | 19 / 22 | 20 / 22 | +1 |

新增的两个组件只是一份包 Schema 资源和一个确定性展开实现。核心增加 10 行只是让 Transform
producer family 投影其本来已经编译的通用 review 元数据；未增加注册入口、运行服务、状态、表、
Root 工具、部署进程或兼容适配层。

生产 Python 树摘要：

```text
b0433da132d880f2451818fc56d0988752978320db39028735798a43336ee1c3
```

完整五插件目录摘要：

```text
11861b6d551aa9bee7dbec018867d9aade7155f455018af798f2ed321446cd70
```

默认 Local 仍有两个公开 Agent 因集合输出不可运行：论文图证据和曲线诊断，分别属于 M2-03 和
M2-02；本阶段没有掩盖它们。

## 5. 测试结果

全部 pytest 串行执行，设置 `ulimit -v 7340032` 与 `MALLOC_ARENA_MAX=2`：

```text
pytest -q tests/operations/test_m2_parameter_package.py
7 passed in 2.14s

pytest -q
215 passed in 65.90s
```

返工前第一次全量运行有 212 项通过、1 项部署测试因先前聚焦测试遗留的
`remote_runner_py36.cpython-312.pyc` 失败。只删除该精确生成物后从干净状态重跑得到上述 213 项
通过；没有修改部署代码或测试来掩盖环境污染。返工后从同样的干净生成物状态得到 215 项通过。

## 6. 首轮独立审查与返工

首轮报告 `../reviews/R5_M2_01_PARAMETER_PACKAGE_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md` 结论为
FAIL，并明确复现三项阻断：

1. 原始包先被要求审查，而审计又依赖展开，形成审查拓扑闭环；
2. 参数资格投影仍解释已删除的 Task 来源类型和 instruction 父链；
3. 提交边界未将包内来源键绑定真实 Run 输入别名，且缺少 revision 旧审查拒绝证据。

返工没有给 support Transform 增加准入特例，也没有恢复 Task 兼容层：审查边改放到展开主对象；
producer family 从同一通用编译事实投影 Transform review；插件只认 Run v1；来源别名在现有输出上下文
验证器中闭合。真实纵向测试现在覆盖首轮报告第 6 节要求的全部正负路径。

## 7. 尚未完成

- 首轮 FAIL 历史继续由独立报告保留；返工后独立复审报告为
  `../reviews/R5_M2_01_PARAMETER_PACKAGE_IMPLEMENTATION_INDEPENDENT_REREVIEW.zh-CN.md`，结论 PASS 并只放行
  M2-02。
- 尚未处理曲线诊断 Agent 的集合输出和 Metric/科学判断边界。
- 尚未决定论文图证据是否退出默认插件。
- M2 整阶段要求的真实通用 Agent 与 TCAD Agent 启动测试尚未执行。
- 没有声称参数提取科学准确率、真实论文证据资格或完整 TCAD 研究闭环已由本阶段证明。
