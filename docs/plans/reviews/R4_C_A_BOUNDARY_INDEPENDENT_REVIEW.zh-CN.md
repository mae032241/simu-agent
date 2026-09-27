# R4-C-A 迁移边界独立审查

审查日期：2026-08-29  
审查范围：`R4_DOMAIN_PLUGIN_UI_IMPLEMENTATION.zh-CN.md` 第 6 节冻结边界；当前
`curve_score`、`ingaas_fig4`、`OperationSpec`、`CompiledTransformAdapter`、清洁安装路径及
33 项架构约束族。  
审查方法：跨 Operation、Artifact、谱系、插件发现、安装和调度视图的只读追踪，并按“若非必要，
勿增实体”检查每个拟保留 Operation 的生产消费者。本审查没有修改实现或总体计划。

## 一、结论

**打回**

当前边界的单入口、三视图和 InGaAs 项目插件方向正确，但尚不能进入 R4-C-B。阻断项只有两个：

1. 多 PLX 集合不能按当前设计证明每个原始字节属于哪个计划序列；“按计划顺序绑定”仍然是位置即
   身份，计划要求的错序失败关闭在现有接口上不可实现。
2. “十个 profile 全部变成 support Operation”没有生产消费者证据，并把三个内部算法门面和一个
   已淘汰兼容入口继续暴露成目录能力，违背本轮降低 Operation 数量和删除旧表面的目的。

这两项可以只改 R4-C 计划和 curve-score 插件实现，不需要修改通用核心、不需要新增注册表，也不
需要增加科学对象。

## 二、阻断项

### 2.1 多 PLX 集合的身份闭包不成立

计划第 6.1(2) 和 6.2 要求删除 `solver_output__<series_key>` 动态别名，改用一个集合端口，并从
experiment plan 的声明顺序恢复身份；同时又要求错序、内容身份、摘要和父链不符时拒绝。

现有真实接口无法完成这组要求：

- `preflight_operation` 只给集合成员生成 `port_001`、`port_002` 形式的局部名字；
  `CompiledTransformAdapter` 随后只把同一端口的原始 `bytes` 按调用顺序分组。算法组件看不到
  execution output 的 `logical_name`，也看不到 Artifact 标签。
- `CurveSeriesDeclaration` 只有 `series_key/case_key/role/axis/point bounds`，没有原始输出摘要或
  原始输出逻辑名。计划能声明“有哪些序列”，但不能证明“第 n 个 PLX 就是该序列”。
- 单个 PLX 内容只自描述数据集表头和数值；当前规范化器把 `series_key/case_key/role` 从外部
  `SProcessPLXSourceSpec` 写入结果。两个结构均合法的 PLX 对调后仍能分别通过解析，并被赋予相反
  的科学身份。
- `RuntimeAttestation` 只有通过结论、检查和数量，不保存每个输出的名称与摘要；真正含
  `name/sha256/size` 的对象是 `TCADRuntimeManifest`。当前冻结输入却没有把该 manifest 交给 PLX
  bundle Operation。

因此，现有方案只是把“动态别名即身份”换成了“集合位置即身份”。这会让两个 case 的曲线被静默
对调，产生格式正确但科学归属错误的 CurveBundle，违反不可变谱系、确定性边界和失败关闭约束。
计划中要求的“错序负例”也不可能对一般 PLX 成立。

最小修复不是扩展核心集合类型，而是收紧这个插件 Operation：

1. 给 `scidiscovery.curve-bundle.sprocess-plx.v1` 增加精确 `runtime_manifest` 输入；不新增通用
   Schema 注册表，直接复用 TCAD 插件已存在的 `TCADRuntimeManifest` 资源组件。
2. 冻结一个插件内映射规则：只选择 manifest 中名称与计划所需 `series_key` 精确相等的
   solver-native 记录；集合顺序必须等于这些记录在 manifest 中的声明顺序；逐项核对
   SHA-256、大小和允许媒体类型。缺失、额外、重名、错序或摘要不符全部拒绝。这里使用的是
   execution 合同中的逻辑名，不是文件名猜测。
3. guard 要求 runtime manifest 和每个集合成员来自同一次 execution 父链，并且 exact passing
   runtime attestation 的父链包含该 manifest 和这些输出；experiment plan 仍负责声明科学序列，
   manifest 只负责把不可变原始字节绑定到执行输出身份。
4. 增加至少四个真实 `operation_invoke` 负例：交换两个不同摘要的 PLX、用同 schema/大小的外来
   PLX 替换、绑定另一执行的 manifest、绑定不包含该输出的 attestation；正例必须从
   `execution_outputs` 返回的真实 Artifact 进入 Operation。

论文图集合不存在同一缺口：manifest 和 validation report 已声明 panel/series、data item 与 CSV
摘要，CSV 自身也带 panel/series 列，按 manifest 顺序重建并逐项校验即可。reference CurveBundle
也在内容中携带唯一 series identity；它应按内容摘要形成稳定审计次序，不能让调用顺序改变科学
映射。

### 2.2 十个 profile 不应全部升级成 Operation

生产调用证据只支持六个可调用 support Operation：

| 处置 | profile | 证据 |
| --- | --- | --- |
| 保留 | `scidiscovery.curve-bundle.sprocess-plx.v1` | 当前 scheduler 的 PLX 主链 |
| 保留 | `scidiscovery.curve-score.v1` | 当前 transport-neutral 评分主链 |
| 保留 | `scidiscovery.curve-score.sprocess-log.v1` | scheduler 明确保留的 direct process-log 路径 |
| 保留 | `scidiscovery.curve-bundle.figure-evidence.v2` | 当前定量论文图桥 |
| 保留 | `scidiscovery.curve-reference-coverage.v1` | TCAD 打包前 reference gate |
| 保留 | `scidiscovery.objective-coverage.v1` | 科学计划打包前 objective gate |
| 不建 Operation | `scidiscovery.curve-normalize.sprocess-log.v1` | 只有文档/测试消费者；其解析函数已被 log scorer 内部调用 |
| 不建 Operation | `scidiscovery.curve-normalize.sprocess-plx.v1` | 只有文档/测试消费者；其解析函数已被 PLX bundle 内部调用 |
| 不建 Operation | `scidiscovery.curve-consistency.v1` | 只有文档/测试消费者；评价函数已被两个 scorer 内部调用 |
| 删除可调用入口 | `scidiscovery.curve-bundle.figure-evidence.v1` | scheduler 明确只允许 v2；读取既有旧 Artifact 不需要保留一个可生成新 v1 产物的执行入口 |

前三个“不建 Operation”项应继续作为已保留 Operation 的插件内部确定性函数复用；这不会丢失
TCAD 能力，也不会形成第二注册表。若实施者主张其中某项必须独立调用，应先给出一个当前生产链
无法由上述六项满足的精确消费者和输入父链，而不能以“曾经存在”为保留理由。

论文图 v1 的“只读兼容”理由不成立：历史 Artifact 的只读可见性由 Artifact 存储保证，不依赖
重新发布一个 transform Operation。总体计划还明确采用源码断代，不自动迁移历史 current 或
资格。保留 v1 可执行入口只会允许创建新的旧语义产物。

六项都属于已选科学行动之后的确定性物化或门结果，统一声明为 `support` 合理；它们不得进入
`scientific_readiness` 或默认 public 目录。解析器、绘图器和评价函数只是 Operation executor 的
内部实现，不要为了“注册完整”再建立 internal Operation。

## 三、通过的边界判断

### 3.1 InGaAs 作为可选项目插件是最小保留方案

`ingaas.fig4-baseline-recovery.v2` 读取冻结 scorer project 中的专用合同、固定五输入并输出项目
门结果；其算法确实含 InGaAs/Fig.4 专用列、阈值和解释边界，不能并入通用 curve-score。现有活动
基线溯源仍需要复算，因此现在删除会丢失已证明能力。

把它保留为默认不安装、只有一个 `support` Operation 的 `ingaas_fig4` 项目插件，并通过同一个
`scidiscovery.plugins` 入口编译，是合理的最小方案。核心、TCAD、curve-score 和默认 full 安装
不得含图号/材料判断；项目插件卸载后只影响该一项未来调用，既有 Artifact 仍可读。

### 3.2 不会天然形成第二注册表，也不会污染规划

只要按计划实施，Operation、端口、guard、validator 和 executor 都属于各自唯一
`PluginDefinition`，`public/support/internal/all` 仍是同一 CompiledCatalog 的投影。
curve-score 六项和 InGaAs 一项均为 support，编译器现有规则会拒绝 support Agent、Effect 与人工
审批，readiness 只消费 public。部署中的插件选择脚本只决定安装哪些发行包，不是行为权威。

旧 `transform_adapters` loader 和 Root 表面延迟到 R5 删除可以接受，但 R4-C-C 后所有发布组合的
两个旧 entry-point group 必须为空，且已迁移 profile 经旧 Root 调用必须失败；不得保留一个
“为空时回退”的 profile 列表。

### 3.3 R4-C-B/C 的串行阶段门方向正确，但需补齐两项验收

“B 独立通过后才做 C”“C 全量与清洁安装通过后才进入 D”的顺序足够防止一次性迁移失控。修订后
还需把下列内容写入门槛：

- R4-C-B 的目录断言改为精确六个 support Operation，而不是十个；三个内部算法无目录项，figure
  v1 未安装且精确调用返回 unknown。
- R4-C-B 的多 PLX 测试必须经过 runtime manifest 的名称/摘要/顺序及 exact execution 父链；不能
  用手工构造 `Mapping[str, bytes]` 的单元测试替代 Root `operation_invoke` 负例。

其余既有门槛——clean core-only/full、无源码扫描、旧 entry point 为零、dry-run、全仓回归、
发布清单和独立审查——可以保留。R4-C-C 的显式 InGaAs clean 安装还应断言默认 full 与 core 的
所有既有 operation digest 不因安装项目插件而改变。

## 四、33 项约束族判断

本仓库没有逐项编号的“33/33”自动验证器，本报告不伪称运行了该脚本。按冻结约束族判断：

- 单入口、三视图、support 不参与规划、InGaAs 通专分离和旧入口清空均符合唯一权威与低成本插件
  目标；
- 当前多 PLX 位置映射会破坏精确谱系和失败关闭，是必须先修复的实质退化；
- 无消费者的四个 Operation 会增加目录与测试表面而不增加科研能力，是复杂度反噬；
- 上述最小修复只复用 Artifact、operation guard、现有 runtime manifest 与 compiled catalog，
  不新增数据库表、生命周期、Schema registry、动态端口类型、领域路由器或核心白名单。

## 五、允许复审的最小修复清单

1. 把保留范围从十个 support Operation 收敛为上述六个；三项归入内部函数复用，figure v1 删除
   可调用入口。
2. 为 PLX bundle 冻结 `runtime_manifest + plan + collection` 的精确身份映射和父链矩阵，删除
   “仅按 plan 顺序即可恢复身份”的表述。
3. 将 R4-C-B 目录、clean 安装和负例门按上述两项同步修订；明确 exact Root
   `operation_invoke` 错序/外来执行测试。

完成这三项后可再次进行 R4-C-A 独立复审；在书面结论变为“通过，允许进入 R4-C-B”以前，不得
开始 R4-C-B 实现。
