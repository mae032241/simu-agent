# R4-D-B 核心审批实现独立审查

## 结论

**打回，不允许进入科学审批插件环节。**

本轮实现已经证明了正确的主干方向：`approval` 仍是同一启动编译目录中的一种 Operation executor，调用复用既有 `ApprovalService`、`ApprovalRequest`、`HumanDecision` 和 SchedulerBinding，没有新增审批表、状态机或第二注册表；编译身份和 provider edge 也确实进入消费者摘要。但是当前边界仍有四个可构造的失败关闭缺口，其中 provider-less 旧查询回退使新旧资格权威在可调用代码中同时存在，不只是文档债务。现有 9 项专项与 216 项全仓测试均通过，但没有覆盖这些反例。

审查对象是当前工作树中题目指定文件及计划第 7.1—7.6 节。相关 Operation 文件和计划文件在当前工作树中尚未被 Git 跟踪，因此本报告不把结果表述为相对某个已提交基线的完整差异审查。

## 已确认成立的边界

1. `approval` Operation 只能是 `public`、无输出、非 external，executor component 必须与唯一 projector 同源；非 Agent executor 不能携带 workspace、tool、resource、prompt、model 或原生工具权限。它没有 Worker authority，也不会创建 Task、ExecutionRequest 或占位科学 Artifact。
2. 调用路径只在既有审批生命周期中创建 ReviewManifest 和 ApprovalRequest，并绑定既有 approval namespace。已声明 subject 的顺序是合同 `subject_ports` 顺序，集合内保持调用绑定顺序；Operation/contract/document/subjects/options 均进入创建指纹，重复同一调用保持幂等。
3. `ReviewDocument` 的五种 item、64 节、512 项、256 subjects 和 512 KiB 总量已经落实；插件只能返回数据模型，不能注入 HTML、URL、脚本、模板或 renderer callable。指向非 JSON subject 或不存在值的 pointer 会在创建和历史读取时失败。
4. provider identity 包含 operation id、version、operation digest 和 approval contract digest；provider group 进入 consumer digest。编译器能拒绝缺失 provider、非 public/approval provider、未声明跨插件依赖和 provider 自身再消费审批 cohort。provider-aware 查询要求身份相等，并要求同一请求/决定具有相同完整 subject tuple 和 subject hash。
5. 总体实现没有偏离轻控制面、最小授权、单一目录投影和“everything is operation”。本轮问题属于缺失的失败关闭约束，不需要再增加新服务或新注册表。

## 阻塞项

### 1. 审批 Operation 可以带未进入人工决定的隐藏输入

`ApprovalContract.issue()` 只要求 `subject_ports` 是全部端口的子集；编译器对 approval executor 也没有要求其全部输入端口都成为 subject。运行时 projector context、ApprovalRequest subjects 和幂等指纹只使用 `subject_ports` 对应输入。

只读反例已经确认：在测试 approval Operation 上增加第二个 `hidden` 输入、仍只声明 `subject_ports=("subject",)`，目录可以成功编译。这样 guard 或未来 projector 语义可以依赖一个没有展示给人、没有进入决定、也没有进入请求 subject 身份的输入；同名调用替换该输入时还可能复用旧审批。这破坏了“一个精确审批闭包”和最小授权。

最小修复：对 `executor.kind == "approval"` 强制 `subject_ports` 与全部 input port 名称精确相等，顺序由 `subject_ports` 唯一定义。若某个对象会影响审批，必须成为可见、冻结的 subject；不要增加“辅助隐藏输入”类别。增加编译负例和变更非首个 subject 后不得复用旧请求的调用测试。

### 2. provider-less 回退是全局可声明的第二资格权威

`InputPortSpec` 允许声明 `approval_kind`/accepted options 而不声明 `accepted_approval_operations`；compiler 遇到空 provider 集合直接跳过；Root 随后回退到旧 `are_subjects_approved()`。只读反例确认，一个新的消费者插件可以用空 provider 集合成功编译，compiled provider map 为空，运行时便按任意同 kind/option 的历史决定准入。

这并未被限定为“仅现有 cohort 的临时兼容”：任何新插件都能选择这条路径。与此同时通用 `approval_request_create` 仍可创建无 compiled identity 的 `scientific_foundation` 请求，因此当前可调用系统中确实并存“精确 provider 决定”和“任意 kind/option 决定”两种资格权威。它违反计划第 7.2 节的单一 provider-aware 查询，也会使 provider readiness 无法闭合；当前 `ready_operations()` 仍只按 Schema 数量投影，未按候选冻结 provider 身份核验精确 cohort。

最小修复：不要新增 legacy provider allowlist、兼容标记或第二查询表。把“核心第一环”和“三个最小科学 provider + 所有现有消费者迁移”合并成一次原子阶段：所有带 `approval_kind` 的 Operation 必须声明非空 provider 集合，Root 删除 cohort 的旧查询分支，候选级 readiness 与 preflight 调用同一 provider-aware 判定，并关闭通用 scientific-foundation 创建旁路。完成这组原子迁移后再整体复审。历史无身份请求仍可只读，但不得准入。

### 3. `ReviewDocument` 没有真正执行 RFC 6901 校验

Schema 目前只检查空串或以 `/` 开头；解析器用连续字符串替换解码 token，没有拒绝非法 `~` 转义，并把任意纯数字 token 转成数组下标。只读反例确认 `/a~2b` 可指向字面键 `a~2b`，`/01` 可读取数组下标 1；前者含非法 RFC 6901 转义，后者不是合法数组索引表示。文档冻结后不同实现可能产生不同解释，也与第 7.4 节明确冻结的 RFC 6901 合同不符。

最小修复：建立一处严格的无副作用 pointer 解析函数，创建和历史重放共用；逐 token 拒绝裸 `~`、`~2` 等非法转义，数组只接受 `0` 或非零开头十进制下标，并拒绝 `-`、前导零和越界。增加空根、转义键、非法转义、数组前导零、非 JSON subject 和不存在路径测试。无需新增 Schema registry。

### 4. 编译合同没有覆盖下游 ApprovalRequest 的静态界限

approval contract 在编译期只检查标签唯一、decision 枚举和最少两个选项，没有检查 decision 唯一、最多 32 个选项，以及 question、label、description 的下游长度界限。运行时把 decision 确定性映射为 ApprovalRequest option id；两个不同标签但同为 `accept` 的选项能成功编译，却会在创建请求时因 option id 重复失败。超长字段和过多选项同样会形成“可编译、不可调用”的目录项，而且异常不一定被规范化成 Operation 拒绝原因。

最小修复：compiler 对静态 approval contract 复用 ApprovalRequest 的精确界限：2—32 个选项、映射后 option id 唯一、question 1—16384 字符、label 1—256 字符、description（含默认 label 后）1—4096 字符；增加每类编译负例。不要在 invoke 层再建立第二套宽松规则。

## 测试与证据

- `pytest -q tests/operations/test_r4_approval_operation.py`：`9 passed in 0.93s`。
- `pytest -q`：`216 passed in 58.89s`。
- `git diff --check`：通过。
- 额外只读最小反例：非法 pointer `/a~2b` 与数组 `/01` 被接受；含非 subject 输入的 approval Operation 成功编译；两个 `accept` 决定的 approval contract 成功编译；provider 集合为空的审批消费者成功编译并留下空 provider map。

测试绿说明既有生命周期没有明显回归，但当前专项缺少上述四类负例，也缺少跨插件未声明依赖/版本漂移、provider A 与 provider B 隔离、同 provider 不同完整 subject 决定、collection 顺序、256/512/512 KiB 边界的直接覆盖。返工后至少补齐四个阻塞项的最小负例；跨插件与容量边界可合并为本阶段完成门测试。

## 阶段门判断

R4-D-B 第一环尚不能作为独立可发布边界。尤其不能用“下一环会删除回退”来批准当前双权威，因为当前编译器允许任意新插件主动选择旧路径。建议保持实现方向不变，只做上述外科式收紧，并将真实科学 provider 注册、消费者迁移、readiness/preflight 统一和旧旁路删除视为同一个原子阶段；复审通过后再进入 projector 领域校验、TCAD execution 身份和固定 UI renderer 的后续环节。
