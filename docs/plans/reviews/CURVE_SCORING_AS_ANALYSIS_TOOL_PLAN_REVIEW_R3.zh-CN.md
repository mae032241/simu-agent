# 曲线评分移入结果分析工具计划：独立工程复审 R3

结论：**PASS（工程计划层面）**。R3 已补齐 R2-1 的绑定元数据交付接口，未发现阻止进入实施的实质缺口。评分保持为分析 Agent 的按需工具；本结论不要求独立评分阶段、实验前评分检查或新增状态机，也不等于实现验收或科学目标完成。

日期：2026-09-09。

## 审查对象与证据基线

- 仓库：`123/scidiscovery-e5.2`。
- 被审文件：`docs/plans/CURVE_SCORING_AS_ANALYSIS_TOOL_PLAN.zh-CN.md`，R3。
- 实测 SHA256：`33d0072b660aa3dd34048f8230cf1be61dd69211981089125267ae657e893ea0`，与委托摘要一致。
- HEAD：`2edac5d317a74056869a567bd0daa7f556ecbc85`。实际工作树有大量既有修改，被审计划为未跟踪文件；以下证据来自该工作树，不宣称是纯 HEAD 的行为。
- 阅读 R2 独立报告及 R3 全部方案，使用 `scid-cross-boundary-review` 技能，独立跟踪相关源码。本次仅新增本报告，不修改计划、生产代码或既有审查结论。

## 实质阻断

**无。** R2-1 在计划层面闭合，理由如下。

### 1. 描述符有完整、可用的控制端来源

`service/run_records.py:42` 的 `RunInputBinding` 已保存 `source_name`、`port_name`、完整 `artifact_ref`、`media_type` 和 exposure；不需要新增输入绑定结构或持久表。`service/artifacts.py:129` 的 `catalog(reference)` 明确解析确切引用，`service/artifacts.py:163` 的 `read(reference)` 通过同一登记记录读取并校验内容；`storage/sqlite.py:271` 的查询进入 `_resolve_in_connection`，不会改成按逻辑名称找当前对象。

执行输出登记处 `service/executions.py:501` 为每项输出建立独立 Artifact，并将 `descriptor.name` 写入 `labels.logical_name`，同时登记媒体类型、长度及摘要。同摘要不同输出名具有不同登记身份，而非只有一份可供猜测的内容摘要。`project_packager.py:790` 的 `RuntimeOutputRecord` 提供对应的 name、media_type、size_bytes、sha256，manifest 又要求输出名与路径唯一。

因此，P2b 选择的字段足以把“确切绑定的输出”连接到“manifest 中的确切记录”。仅投影 `logical_name`，不转交所有 labels 或查询句柄，足以解决当前问题；无需向插件开放核心数据库。缺少 output_name 时仅允许不依赖该关系的受限分析，也没有以摘要匹配偷换确切来源保证。

### 2. 三参数接口兼容，过滤边界已有承接点

`service/run_outputs.py:186` 附近目前按 `input_source_ports[name] in port.context_sources` 构造 bytes 字典，再调用 `context_validator(payload, sources, handoff)`。R3 在这个位置引入兼容字典的容器和只读属性，保留调用参数个数，属于可实施的局部扩展。

已检查的旧校验器使用 `set(sources)`、下标和 `.get()`，例如 `curve_score/science_operations.py:569`、`:608` 及 `general_science_experiment_components.py:156`；这些操作可由 dict 兼容容器保持。没有发现此范围内依赖 `type(sources) is dict` 的障碍。描述符映射与 bytes 按相同端口集合过滤，便可保持别名一一对应；多件输入的序号别名不必编码输出名。

`operations/catalog.py:341` 已校验 context_sources 必须指向声明输入，并在第 344 行开始拒绝将 handoff_only 输入加入 context_sources。P2a 将计划—审查关系放在有 BoundInput 元数据的 guard，P2b 不借描述符泄露隐藏输入，符合该现有约束。描述符作为只读属性交给控制端运行的 validator，也不意味着新增模型可调用的控制查询能力。

### 3. 预检、提交与恢复共用确切绑定路径

`service/runs.py:479` 的 `validate_candidate` 和 `:453` 的 `submit` 都进入 `:725` 的 `_validated_candidate`，后者已经从 `value.inputs` 按确切 ref 读取 bytes，再调用 `validate_run_output`。把描述符构造放在这里，能覆盖 Worker 候选预检与正式封存，不需要复制两套校验。

已接受候选的重试仍在 `_validated_candidate` 使用固定 candidate digest 封存；`_recovery_digest`（`:1054`）还要求恢复来源的 Operation digest 及有序输入 refs 一致。R3 要求每次按当前确切 Run 绑定重建描述符，既不依赖可写草稿，也不会让相同 bytes 的新 Artifact 替代原 ref。已完成 Run 的幂等 submit 可直接返回 completed，无须把这一既有行为改成重新验证。

R3 将登记缺失、ref／media_type 不一致和描述符缺失归为 `RunCheckerError`，与 `submit` 现有“工程 checker 故障进入 failed，科学输出错误允许 rejected 后修正”的分工一致。候选预检应沿既有错误通道呈现工程故障，不能包装成要求 Agent 修改科学答案的语义违规；这属于该方案的实现验收要求。

### 4. 同 bytes、不同名字的反例闭合

同一执行中的 A、B 可以有相同摘要和 parents。P2b 不再先按摘要找任意 manifest record，而是按输入别名取得控制端 output_name，再定位对应记录并校验 bytes 和 case 关联。

由此，只绑定 A 时，描述符只能证明 A；Agent 自报 B 不会改变它。正确绑定 A、B 时，各自描述符分别定位记录，同摘要不构成拒绝理由。R3 的验收同时要求无评分路径拒绝 B 的已读／case 结论、两个合法绑定可提交、顺序改变仍按别名对应，以及缺少对应时允许受限分析，覆盖了 R2 的错误接受与过度拒绝两个方向。

最终 validator 无法机械证明任意自然语言陈述的全部科学含义；实施应将已读输出／case 等机械引用落实到现有报告证据字段及必要的窄字段上，并让提示说明引用规则。计划已要求证据引用与模型可见契约同步，不需要另建通用自然语言裁判。

## 整体路径一致性复核

| 边界 | 源码依据与结论 |
| --- | --- |
| 无合同进入实施 | `tcad_artifact/plugin.py:439` 的 INITIAL_INPUTS 已将两个合同输入设为可选。P0 先复现真实隐藏约束，再决定是否改 author／packager，避免为了形式完整而多改逻辑。 |
| 原始文件到同 Run 评分 | `operations/tooling.py:40` 支持 contextual_handler；`artifact_agent/operation_tool_context.py:40` 提供受控 read_input。TCAD 组合工具可读取绑定 PLX／日志／CSV，调用本插件 normalizer 与 `curve_score/schema.py:1005` 的纯评分函数，再在正式提交从原始 bytes 重放。R3 没有依赖运行时新增输入或 Root 中途解析。 |
| 无评分身份校验 | `operations/invoke.py:29` 的 InvocationArtifact 提供 ref、parents、labels、正式 handoff verdict；`tcad_artifact/operation_transforms.py:183` 展示 manifest—package 及同执行输出父集合检查。P2a 的窄 guard 与 P2b 最终字节／引用校验职责互补，不以工具调用作为身份校验开关。 |
| 失败结果也能正式提交 | manifest 模型允许 failed／cancelled；旧 `curve_operations.py:85` 的 passing-attestation 是旧 support 限制。新方案明确复用底层解析而不沿用该成功门。`layered_diagnosis.py:137` 起的门状态派生支持 invalid_study 与 inconclusive；P4 要求两类合法 fixture，足以界定实施。 |
| 计算记录与提交边界 | P3 把记录放进既有报告而非外包装，computed 重放、unsupported 确定性复核、瞬时 error 不要求复现，也不能支持数值成功结论。记录、采样、响应和最终输出均有上限，且验收要求累计真实解析与提交。没有新增状态机需求。 |
| 下一轮读取 | `general_science_experiment_operations.py:36` 的反馈端口接受通配 schema／媒体 inventory；128 KiB 报告在现有单项限额内。沿用 LayeredDiagnosisReport 并验证封存结果进入设计，能保持计划、限制及后续条件的正式交付。 |
| 插件及安装 | TCAD pyproject 已依赖 curve_score 且有插件 entry point。P2 保持 TCAD → curve_score 方向，P5 明确验证安装版 Operation／工具／端口和禁用 TCAD 后的通用分析。新增领域入口与通用入口为替代选择，不形成串行必经阶段。 |

## 属于实施细节的事项，不新增计划阻断

1. 描述符应使用冻结值和只读映射；现有 ArtifactRef 已采用冻结 SchemaModel。不要仅将可变 dict 放进 frozen dataclass 就宣称深层只读。输入 bytes 不必为兼容性改成全新的抽象接口。
2. 目录解析／读取失败应在共用构造路径统一转换为既定工程错误；字段集合、ref、登记媒体及 bytes 的一致性均需验证。旧纯函数调用可省略描述符，新 TCAD validator 必须 fail closed。缺少 output_name 与缺少描述符是不同情况。
3. `runtime_parentage` 当前使用端口名 `runtime_outputs`，新方案使用 `solver_outputs`；应复用其规则或提取小函数，不能未经适配直接挂旧 guard，导致零项循环而漏检。这是明确可见的端口接线细节，不要求重写计划。
4. 当前输出声明没有普遍可用的直接 case 字段。R3 已授权在真实反例证明缺失时补最小输出—case 关联；实施不能从名字或相同摘要猜测。未知对应允许受限分析，无须为首版实现通用推断器。
5. 近上限验收要包含多条记录的累计重放和角色 envelope 字节，而非仅独立工具响应；恢复、过滤及旧三参数兼容用例应走真实 RunService 入口。这些均属于 R3 已要求的验证，不增加算法或平台范围。

## 验证边界与进入实施的条件

本次完成摘要、HEAD 与工作树核验，读取计划及前审，跟踪输入绑定、登记查询与校验读取、context_sources 编译限制、候选／提交／恢复、执行输出登记、工具上下文、报告门状态、下游反馈端口与插件依赖。未运行测试、安装版服务或真实求解器，未调用研究 Operation／Worker MCP，未读取科学草稿。

PASS 表示当前计划足够完整且存在具体源码承接点，可以按 P0—P5 实施；不表示尚未编写的描述符容器或新分析入口已经正确。实现验收仍须完成原始文件→工具→正式封存→下一轮输入，以及同 bytes 不同名的无评分反例、失败运行提交、恢复与安装版检查。计划第 6 节要求的真实新执行结果进入分析并接续下一轮，也不能由本次文档审查或 fixture 代替。
