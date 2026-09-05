# R5 E5 生产输出族完整性独立评估

日期：2026-09-05

结论：**选择 B；当前缺陷阻断继续执行 E5 正例。**  
方案 A：**拒绝**  
方案 B：**接受，但必须实现为消费者声明、核心机械验证的单一可选合同**  
方案 C：**拒绝**

## 1. 当前负控证明了什么

`science.evidence.extract.figure.v2` 的 `curve_tables` 端口声明 `min_items=1,max_items=32`。因此一个
物化调用真实产生两张表时，只绑定 `curve_tables_001` 仍满足普通端口基数；当前 Operation 又没有
声明跨端口 producer-family 合同或 guard，故 preflight 返回 admissible。

这不是 JSON Schema 缺陷，也不能由 manifest payload 解析补救。缺失事实是：该消费者宣称消费
“同一次确定性物化的完整输出族”，但 OperationSpec 只表达了每个端口自身的基数，没有表达：

- 五组输出必须来自同一个 transform invocation；
- 每组必须覆盖该 invocation 实际登记的全部成员，包括变长 `curve_tables`；
- `paper_source` 与 `figure_request` 必须是该 transform 的精确输入父链。

Root 现有 `_transform_output_family` 已能通过 producer labels、operation digest、invocation fingerprint、
实例 bindings 和已编译输出端口重建完整输出族。它是控制面已有的机械事实，不需要读取 manifest 或
任何领域 payload。当前缺的只是**消费者在自己的 OperationSpec 中声明它需要完整族**。

旧 digest 被 `input_producer_contract_changed` 拒绝以及复用同一 Artifact 被
`input_artifact_duplicate` 拒绝，都是正确但不同的负控；它们不能替代“同代际、独立对象、缺一个变长
成员”这一完整性负控。

## 2. 为什么拒绝 A

“任何 Operation 只要消费某个 transform 的一个或多个输出，就自动要求绑定完整输出族”会把生产者
的全部输出强加给所有消费者。许多合法消费者只需要一个确定性报告、一个主输出或一个摘要；强制其
读取全部 sibling 会：

- 违反最小上下文和最小授权；
- 让生产者的输出拓扑隐式决定所有下游输入；
- 使新增可选输出成为所有旧消费者的破坏性变化；
- 把通用核心重新变成重型全族控制器。

因此 A 虽可复用已有 family 恢复代码，却使用了错误的全局触发条件，违反奥卡姆原则、生产者/消费者
责任边界和 `AUTH-003`。

## 3. 为什么拒绝 C

本问题不是昂贵科学计算无法在 preflight 执行，而是控制面已经掌握的不可变元数据完整性。若承认
preflight 只检查端口基数：

- 一个明确声称需要完整图族的 Agent 会被分配不完整上下文；
- Agent 可能先消耗一次完整 Run，直到提交 context validator 或更后面的 bundle Transform 才失败；
- 如果某个科学 validator 没有逐项复核附件，甚至可能封存基于不完整来源的 Intake/Audit；
- catalog 的 applies_when 和精确 preflight 再次出现 `TOP-002` 断裂。

后续 Transform 对 manifest 内容的失败关闭仍应保留，但它不能代替可由控制面预先证明的输入族准入。
所以 C 不是诚实降级，而是保留已被真实负控证明的合同缺口。

## 4. B 的最小正确形态

### 4.1 所有权

合同必须由**消费者 Operation**声明，而不是由生产者声明下游用途：

```text
science.evidence.extract.figure.v2
science.figure.evidence.audit.v1
  └─ 可选完整生产族要求
       ├─ 生产输出端口：figure_manifest、validation_report、
       │                  source_panels、audit_overlays、curve_tables
       └─ 生产输入端口：paper_source、figure_request
```

核心只按不可变元数据机械验证该声明；不得出现 Fig.4、curve、manifest、TCAD、插件 id 或 Schema id
分支。生产者无需知道谁会消费全部或部分输出。

### 4.2 最小数据合同

现有 `InputAdmissionSpec` 同时承担 all-or-none 与可选审批，而且编译器要求其成员端口
`max_items==1`，不适合变长输出族。把 family 语义塞入其中会混合两个责任并迫使修改既有审批语义。

最小合理新增是 OperationSpec 上**一个可选、单族、不可变值合同**，只包含：

- `output_ports`：消费者端口名；要求与 producer 输出端口同名；
- `input_ports`：消费者端口名；要求与 producer 输入端口同名。

当前不设计多族列表、显式 producer operation id、版本选择、资格、审批或 payload selector。生产者身份
由实际绑定 Artifact 的冻结 labels/digest 推导；如未来确有一个消费者同时要求多个 producer family，
再以真实用例扩展，不能本轮预设计。

### 4.3 核心机械验证

preflight/invoke 共用的现有输入准入路径应对声明了该合同的 Operation 执行：

1. 对 `output_ports` 中任一绑定项调用已有 producer-family 恢复逻辑；
2. 要求所有声明输出项属于同一 `family_identity` 和同一 transform invocation；
3. 按 producer member 的 `port_name` 分组，要求绑定 refs 与恢复出的完整 members 精确相等，因而能
   发现少一张或多一张变长表；
4. 通过 producer 已编译输入端口和输出 Artifact 的精确 `parent_refs` 恢复输入分组，要求声明的
   `input_ports` 与各同名 producer 输入 refs 精确相等；
5. 未声明该合同的普通消费者完全不执行该规则，仍可合法只消费一个 sibling；
6. 失败只返回一个稳定、领域无关的既有 OperationInvocationError 外观；不创建状态、收据或第二
   family registry。

集合比较不能只比总 refs：必须按同名 producer port 分组，否则两个媒体/Schema 相同的输出可能被
交换到错误端口。输入父链也不能只做“是 parent”集合包含关系，必须按已编译 producer 端口恢复并
精确比较。

### 4.4 为什么这是契约正确性而非 Fig.4 补丁

核心能力表达的是领域无关命题：

> 某个消费者明确要求一次已编译确定性调用的完整输出族及其精确输入父链。

图插件只是第一个真实使用者。核心不读取 manifest、不数曲线、不认识 PDF，也不假设所有消费者都要
完整族；这与通用的内容寻址、producer digest 和 immutable parentage 同层，属于 OperationSpec 缺失
的一条组合契约，而非 Fig.4 特判。

## 5. 最小实现与测试边界

本轮只需：

1. 给 OperationSpec 增加上述一个可选单族合同并在编译时验证端口存在、输出/输入端口集合不重叠且
   名称合法；
2. 在 Root 已有输入准入中复用 producer-family 与 transform input grouping，不复制 family 恢复；
3. 仅在图 Intake 和图 Audit 两个消费者上声明；
4. 增加四类聚焦测试：完整族通过、少一个变长 sibling 失败、替换独立 source/request 失败、混入
   另一 invocation 失败；
5. 保留一个未声明 family 要求的普通消费者只取单个 transform 输出仍可通过的反例，防止实现滑向
   A；
6. preflight 失败前后 Run/Artifact 数量不变，并证明 invoke 再次执行同一准入。

不得在本轮：解析 manifest、给核心增加图插件引用、修改 producer 声明、重写
`InputAdmissionSpec`、新增 family 数据库/注册表/current/状态机、修改 UI/Hardened，或顺带迁移其他
Operation。最终 bundle 已有独立 parentage guard 和确定性 payload 验证，不在本缺陷的 Intake/Audit
最小修改中扩修。

## 6. 33项约束判断

- `AUTH-003`：family 要求成为消费者 OperationSpec 的编译字段，而非 Root 隐藏名单。
- `TOP-002`：目录声称需要完整族的精确绑定与 preflight 结论重新一致。
- `ROLE-001/002`：核心只验证机械来源完整性，不解释科学 payload；Worker 获得其 Operation 声明的
  完整上下文。
- `DET-001/002`：只使用已登记的 transform identity、成员和父链，不让 deterministic code 作科学
  选择。
- `PLG-001/002`：核心合同领域无关，具体端口组合只在图插件 Operation 中声明。
- `RES-001`：未声明完整族的消费者不被迫读取无关 sibling；声明者只获得自己明确要求的完整族。
- `CQRS-001`：family 恢复和比较必须纯读，preflight 不登记任何对象。

## 7. 是否阻断当前 E5 正例

**阻断。** 当前正确族尚未调用 Intake preflight，而负控已经证明同一 Operation 可以接受不完整
materialization family。此时继续正例只能证明“一组正确输入碰巧可运行”，不能证明 Operation 的准入
合同闭合；还会把后续 Intake、独立 Audit 和人工资格建立在已知存在旁路的入口上。

应先按 B 完成最小实现、聚焦测试和独立复审，再重新部署并用新的真实负控/正例继续 E5。旧 digest
请求继续不可变保留，不得通过改历史 Artifact 或复用旧 Run 绕过。
