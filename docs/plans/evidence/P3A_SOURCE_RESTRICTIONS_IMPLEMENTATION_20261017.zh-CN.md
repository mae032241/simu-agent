# P3a 来源限制实施记录

状态：代码已冻结，[代码独审 PASS](P3A_SOURCE_PROVENANCE_REVIEW_20261017.zh-CN.md)；仅完成静态 AST/文本检查，未运行测试。P3a 不启用生产执行，也不代替 P3b 正式独审、P3c 授权和 P3d 资源 gate。

设计依据：[P2/P3 拆分](../THIN_P2_P3_IMPLEMENTATION_SPLIT_20261017.zh-CN.md)及其[设计审查](THIN_P2_P3_SPLIT_DESIGN_REVIEW_20261017.zh-CN.md)。独审随后确认本轮最小可信入口为现有 `prepare` 的操作者配置，并接受同一 CLI 入口；不新增 setter、UI、模型资格字段或任意 `basis_ref` 授权机制。

## 根因与最小接线

原薄层封存成果字节和父节点引用，没有独立来源限制原件。没有标签不代表来源不受限；相同 hash 也不证明相同来源。原 `scientific_usage` 和 `reference_proofs` 已处理精确引用、显式依赖及不确定性，但其 SQL/CAS owner 不能搬入薄层。

- 共享纯规则 `dependency_sources` 区分未声明 derivation 与可信显式空集合。无精确 derivation 的自动成果继承全部冻结任务输入；不从科学模型的 selection、标签、文字或 pass 推断缩小依赖。
- `inherited_restriction` 保留 `clear/restricted/unknown`。已知 restricted 支配 unknown；无完整原件的边不能洗成 clear。
- 操作者通过 `prepare --source-restrictions FILE` 提供 JSON 数组，每条只有 `source`（绝对精确原路径）、`sha256`（预期原件 hash）和 `restriction`（clear/restricted）。该入口继承现有宿主配置的信任边界，JSON 字节 proof 不是语义认证。
- 仅允许 objective、user updates 原件及 public root 内的 canonical regular 文件。拒绝 symlink 绕过、错误 hash、同一路径重复声明和无关私有路径。声明原件及其字节保留到实例；声明 ref 冻结进原有 settings。
- objective/updates 通过明确的原路径到 global 副本映射继承来源事实，不按 hash 查找“同源”。未声明的真实 global 输入仍 unknown；新增 public 声明作为直接绑定输入，不能被模型删去。
- 新 job 的 host record 保存 `input-provenance.json`，只含直接输入边和直接 producer seal ref。新成果保存 `provenance.json`，绑定原 job/raw/result 身份、当前材料列表摘要及 input ref。材料明细仍由原 seal 持有，不再存一份清单，也不复制全祖先。
- 控制按需沿原 seal/ref 核验，单次计算局部复用已核实来源状态。模型只见紧凑输入状态、数量和保证范围，不见祖先引用列表、hash 清单或机械来源表。
- `output_status` 只读确切封存成果及材料 membership，不是执行准入接口。历史 job/成果缺来源 receipt 时保持 unknown；不补写旧原件、不继承资格。无来源资格需求的普通科学 build/seal 继续。

示例（source 必须替换为操作者实际原件路径和预期摘要）：

```json
[
  {"source": "/absolute/public/material.csv", "sha256": "<expected sha256>", "restriction": "restricted"}
]
```

`clear` 只表示框架已声明/冻结的输入成果链无来源限制，不表示科学结论正确、正式 review 合格、执行获准或 native 任意外部读取被 OS 封闭。拥有任意 native shell/宿主写权限者仍处于既有软隔离边界；本轮不扫描或复制整个 public root。

## 缺边与集成限制

| 情况 | 处理 |
| --- | --- |
| 真实叶无操作者声明、旧 producer 无来源 proof | unknown；普通科研不阻断。 |
| 材料不属于任何精确绑定 producer，或多个 producer 身份歧义 | 保留 unknown 边；不按同字节换原件。 |
| 循环闭包 | 状态消费保留 unknown；新任务仍要求严格前序 producer。 |
| 同一原路径的材料身份与 producer 不同，或声明/receipt/raw/result/材料身份改变 | 明确 IntegrityError；这是身份破坏，不是科学否定。 |
| 非空 managed calls，或自定义外部 observer 无可信来源映射 | 成果额外 unknown，原因 `observation_input_provenance_unsupported`；与 restricted 合并仍为 restricted。 |
| 空 registered capture，且没有外部 observer | 没有额外来源输入，不平白增加 unknown。 |

后续可信 adapter 必须经唯一输入 owner 暴露精确来源资格，才能移除 managed/observer 的 unknown。本轮不平行解析 accepted，不猜 work 源码来自何处，不将工程完成状态视为来源资格。P3b/P3c/P3d 及真实 TCAD gate 仍未完成。

## 文件责任与旧规则复用

本轮精确文件：

- `src/scidiscovery/operations/provenance_rules.py`（新）：纯依赖选择与三态传播。
- `src/scidiscovery/research_loop/qualification.py`（新）：宿主来源声明原件、直接输入/成果 proof、精确只读状态。
- `src/scidiscovery/research_loop/controller.py`：prepare 操作者配置验证与声明 ref 冻结。
- `src/scidiscovery/research_loop/cli.py`：同一 prepare 的声明 JSON 入口，无新增 Worker 输入。
- `src/scidiscovery/research_loop/contracts.py`：job 输入 ref/紧凑状态、成果 ref 及身份核验。
- `src/scidiscovery/artifact_agent/service/reference_proofs.py`：复用纯依赖选择；保留旧 namespace、source_ref、公共网页和历史 all-task-inputs 语义。
- `tests/research_loop/test_source_qualification.py`（新）：小量定向负控。
- 本记录。

没有删除旧测试或生产接口，没有移植旧 Artifact/Run/Approval 数据库，也没有新增 Root、预算或状态机。P2a 的 execution/experiments/managed_wait/history/lineage 与测试修改由其他 owner 完成，本轮未编辑；当前对照基线包括已独立提交的 P2a `c925873`。

旧能力对应：精确引用/错 ref 对应新 `output_status` membership 与直接 producer 绑定；衍生锚点及复制不洗白对应自动全输入继承；历史缺精确来源对应 unknown。旧 SQL 适配遍历仍在原 `scientific_usage`，本轮不声称已完整替换其全部合同。

## 独审反馈中修正

1. 成果 proof 初稿只有 job/raw/result，未绑定材料身份。已加入原 seal 当前材料列表的确定性摘要；新增只改材料身份、保持科学 JSON 不变的负控。
2. 初稿对任意 observation ref 一律额外 unknown。已区分空 registered capture 与确有额外输入/外部 observer，不制造零实验节点的无谓 unknown。
3. 判断观察有无额外输入时，初稿调用完整 `history.validate_observation`，会在祖先来源消费时重复核验全部执行原件和日志。现只核对 seal 绑定的确切观察 JSON 路径/摘要并读空非空事实；完整 history 验证继续由既有 contracts owner 单点负责。来源核验局部 memo 不成为新状态。这里是静态可达额外 IO 的修复，没有动态性能或 OOM 结论。

## 定向用例与验证层级

用例复用现有 `test_history_handoff.finish` 的真实 build_job/seal_result/validate 路径，不构造旧 Root，也不启动模型或 solver：

- 未声明 derivation 继承全部；可信显式空集合与 unknown 分开。
- 相同字节的未声明 update 不继承另一个 objective 的 clear。
- restricted 经 H/W/A 及复制成果传播，模型文本 clear/pass 不授事实。
- 缺材料边 unknown；精确 source 成员错路径拒绝；成果当前材料摘要防换原件。
- 声明原件篡改拒绝；无声明普通科研仍能封存，旧缺来源 job 状态 unknown。
- 零 call 的 registered capture 不额外制造 unknown。
- 同一 CLI prepare 可冻结 public 原件；symlink、错 hash 和重复声明负控。

实际执行：最终冻结的上述 7 个 Python 文件通过 `ast.parse`（标准库静态解析，无项目 import），8 个本轮文件通过文本尾空白检查，本轮路径限定的 `git diff --check` 通过；另作差异/引用文本阅读。没有借静态结果声称测试通过。

**未运行** pytest、collect、项目 import、CLI、任何业务子进程、build/install、真实模型、远端、solver 或性能检查。用例已写，不是运行 PASS；静态独审也不替代运行验收。动态验证仍受当前硬资源域限制，不能以新来源 proof 声称真实生产资格。
