# Operation 与工具契约一致性修复计划 R3 独立定向复审

日期：2026-09-11。结论：**REVISE，仅 1 项必要补齐：明确编译摘要与合同身份元数据的生成顺序。**

R3 的“一处声明、一次编译、各入口按职责消费”已落到现有类型、编译产物、函数和删除清单，不是抽象口号。C1 没有要求第二注册表、万能校验器或跨阶段动态缓存；R2 已通过的实际协议也未退化。剩余问题很窄：现有输出合同包含自身 operation_digest，新增“合同投影进入 Operation digest”需要明确排除这种自引用，不能让实施者各自选择摘要材料或循环构造身份。

## 1. 精确审查基线与范围

- 计划：`docs/plans/OPERATION_TOOL_CONTRACT_COHERENCE_REPAIR_PLAN.zh-CN.md`，R3，380 行。
- SHA256：`130d3c57018a831e185ed028935631d2849f7d1993bee9bfdafed28aa8f2668b`。
- 对照：`docs/plans/reviews/OPERATION_TOOL_CONTRACT_COHERENCE_PLAN_R2_REVIEWED_SNAPSHOT.zh-CN.md`；R2 对象 SHA256 为 `5e57817f2f4d6567276dc1738643ad60487c8bf0eb13305033f82c20258ce6b3`。已读取 R2→R3 精确差异，R2 PASS 不自动延伸至本版本。
- 仓库：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`；HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`，已有未提交修改。
- 方法：沿用前三轮源码核查，定向读取 CompiledOperation、目录构造/摘要、合同投影、工具解析、Root/lifecycle 声明及相关消费者位置。未访问科研状态、原执行产物或 Worker 工作区，未调用科研工具，未运行测试、编译、安装或求解器。仅新增本报告。

## 2. 唯一必要阻断：合同投影参与自身摘要时尚未定义无环构造

**优先级：P1。计划位置：**§4.2 第 76—79 行，尤其第 4 点；§4.4 单声明变更贯通身份的验收。

**源码证据：**

- `src/scidiscovery/operation_contract.py:268–279` 的 `operation_output_validation_contract` 返回值中，第 272 行明确包含 `operation_digest=compiled.digest`。
- 同文件 `:334–335` 又将这个含身份的合同嵌入最终输出 JSON Schema。复用现有“完整合同投影”时，自身摘要不是外部无关字段。
- `src/scidiscovery/operations/catalog.py:739–767` 当前先对 CompiledDigestEnvelope 和投影版本标记求摘要，`:787–789` 再把摘要放入 CompiledOperation。当前代码没有将带自身 digest 的最终合同反向加入摘要，所以现有流程本身不存在该循环。
- R3 新增要求把实际生成的“工具参数 Schema、合同投影及相关声明能力”纳入现有摘要封套，但没有明确“参与摘要的静态投影”与“注入自身身份后的对外合同”的顺序及边界。

**可达场景与影响（静态设计推导）：**实施者按 C1 直接复用当前公开投影函数，试图先得到完整合同再计算 Operation digest，会先需要一个尚未算出的 compiled.digest。用临时摘要填充后再次计算，则最终公开合同与参与摘要的对象不同；不同入口自行排除字段又违背单一材料来源。这会阻断确定性编译身份与 Worker 配置的接通。问题来自拟新增摘要路径的定义缺口，不是声称现有目录已经无法编译。

**最小修订：**在 §4.2 明确同一条无环构造顺序：

1. 从声明和已解析组件生成**不含自身 operation_digest 的静态模型/合同材料**；既有 reviewer/provider 等有向依赖身份仍按当前目录规则处理。
2. 将这些静态材料纳入现有摘要封套，计算唯一 Operation digest。
3. 再把计算所得身份注入只读对外合同/配置；这是派生元数据，不反向参与同一摘要，也不成为可编辑的第二份规则来源。
4. Run 别名、当前证据、批准状态等动态值继续在各 Run 投影，不进入启动期静态摘要。可直接复用静态材料构造对外视图，无需增加 ContractSpec、第二摘要协议或递归源码哈希。

**最小验收补充：**相同静态声明重复构建得到相同身份；模型/权限变更按 §4.4 影响相应身份；所有公开合同中的 operation_digest 等于所属 CompiledOperation；两个 Run 的别名变化不会反向改变该静态身份。无需为此新增独立测试平台。

## 3. C1 其余主线的可实施性判断

| 审查点 | 判断与源码对应 |
|---|---|
| 复用现有编译结构 | **足够具体。**`operations/spec.py:418–427` 已有冻结 CompiledOperation，包含 spec、implementations、component_specs、permission_template、digest。R3 仅补工具解析与按输出端口索引的只读基础投影，有直接落点。 |
| 消除可编辑副本 | **足够具体。**现有 `tooling.py:103–125` 每次重新解析/投影工具，`WorkerToolDefinition.schema:81–85` 从模型生成 Schema；`operation_contract.py:283–337` 每次组装输出合同。R3 §4.3 给出了具体消费者与应停止的副本，不仅新增 helper 后保留旧分支。 |
| 动态 Run 合同 | **阶段和范围正确。**§4.2.2、§4.4 保留同一静态源上的 Run 别名/证据投影及候选冻结一致性，并要求不同 Run 不污染。`run_assignment.py:157` 与 `run_outputs.py:291` 目前均消费 operation_port_json_schema，可沿同一公开函数迁移。 |
| Root/lifecycle 例外 | **明确且合理。**`interfaces/mcp_root.py:130–140` 的 RootTool 和 `operations/lifecycle.py:12–46` 已各有参数/生命周期声明。§4.2.3 让它们共享解析与诊断适配，保留原来源，不把管理调用注册为科研 Operation。 |
| 输入准入与输出验证 | **没有退化。**§4.2、§4.3 明确 preflight/invoke 执行输入准入；submit 只对照输出声明和已冻结证据，不能重新判定旧输入当前资格。复用的是解析事实，不是跨阶段拒绝条件。 |
| 避免过度重构 | **边界明确。**不新增 ContractSpec、规则 DSL、持久合同库、跨目录可变缓存或万能 validate(stage)；按行为切片迁移、删除副本和验收。§12 已限定 catalog/spec/compiler 与平台改动目的。 |
| JSON Schema/Pydantic 接受行为 | **已有足够的计划验收。**现有 `mcp_local_worker.py:88` 使用 strict=False，而共享 SchemaModel 在 `schema/common.py:57–61` 设置 strict=True，确有类型转换差异需验证。§4.4 明确要求类型/枚举变更经真实 tools/call 与两种 Worker，包含 coercion 负例，不能只比 Schema 文本；无需再发明条件语言。 |

## 4. R2 闭合是否退化

没有发现退化。精确文本差异表明，R3 保留了 R2 的 JSON-RPC error.data 协议、模型验证前可信 attempt、原请求和失败历史行为、两类清单用途及同 Artifact 一次绑定、A→B→C 正负例、三种分析入口能力限制、通用内部证据键规则以及 P6 真实交接条件。

C1 只是要求这些规则的同一声明/解析组件接通全部消费者，并删除重复规则；它未把已审查协议替换为一个统一跨阶段 validator，也未放宽原文件 producer、独立审查或执行批准。

## 5. 非阻断提醒与未验证事项

- §4.4 的“动态批准撤销”宜改为“未取得匹配批准或预算耗尽”等现有门禁表述。§4.2 末尾的解释性段落已经限定保留现有动态授权要求，不能因这一措辞新建批准撤销功能。此为范围措辞澄清，不另列阻断。
- 编译基础 Schema/合同必须真正只读；每个 Run 的实例化不能修改共享嵌套对象。现有投影函数的接口可以保留，具体复制/不可变容器方式属于实施选择，按两 Run 隔离见证验证即可。
- C1 不证明任意 Python 窄 checker 的科学语义。R3 已把这项边界留给同源可见说明、人工审查、行为正负例及组件/插件版本管理，实施时应保持这一限定。
- 本轮未执行任何动态检查，也未验证安装包、生成配置、真实 PLX、科学方法等价性或 P6。计划通过与实现/部署/科研验收须继续分别报告。

补清第 2 节的摘要构造顺序后，可以提交下一版定向复审；无需扩大其余方案或重复开展无关框架审计。
