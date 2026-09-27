# R5 详细实施方案第二轮独立审查

日期：2026-08-29  
审查对象：

- `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md`；
- `docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md`；
- `docs/plans/README.md`。

首轮依据：`docs/plans/reviews/R5_PLAN_INDEPENDENT_REVIEW.zh-CN.md`  
审查性质：对首轮六项冻结修订的逐项复核；未参与方案修订；未运行全仓测试  
最终结论：**有条件通过**

## 1. 结论摘要

首轮冻结的六项主体修订均已进入方案，并且没有借修订扩大为新的科研语义内核、插件生命周期
系统或宏大 benchmark：

1. 设备参数已从“两条 legacy Agent bridge”扩大为一个完整 TCAD 领域纵切面；
2. `load_roles/load_transform_adapters` 的 runtime、Codex、daemon 和安装消费者均有明确替代；
3. Transform producer family 已选择控制生成的统一 invocation fingerprint，并补齐有序父链、
   revision usage、完整兄弟集合和去重；
4. 复杂度改为 R0 固定路径、整个 operations 包和全仓生产代码三重口径；
5. 双 daemon 配置摘要已落实为实际进程写出的短生命周期文件和一次性探针，没有数据库或科学
   Artifact；
6. R5-G 已形成真实 Operation Agent、冻结 TCAD 小任务、重放 solver 层、独立科学评价、单 Agent
   与 8765 参考的有界效果回归。

因此首轮“打回”的架构性阻塞已经解除，方案不需要再做结构重写。但是当前仍有四处很小的文字
闭包问题，其中一处涉及安全交付，一处涉及不可能由现有机制兑现的门禁表述。它们必须修订后
才能给出“通过，允许执行 R5-0”。本轮不允许开始生产实现。

## 2. 首轮六项冻结修订逐项复核

### 2.1 完整设备参数纵切面：已闭合

修订后的 R5-A 明确迁移：

- `device_parameters` Schema、单位/条件/coverage/uncertainty 算法及导出；
- 两个参数 Agent Operation；
- coverage、uncertainty Transform；
- 两个资格 Approval Operation、projector 和 provider 引用；
- TCAD author/reviewer 输入合同；
- 通用 `ExperimentDesignIntent` validator 中的设备参数映射逻辑。

完成门同时要求 core-only 不导入、不导出设备参数 Schema，也不编译参数 Operation，而 TCAD
clean-wheel 仍运行完整参数链。这覆盖了当前真实泄漏点：
`general_science_plugin.py`、`general_transform_operations.py`、
`schema/experiment_intent.py`、`schema/__init__.py` 和 TCAD plugin/package 反向导入。

该处没有要求复制通用 evidence、experiment、ApprovalService 或 ReviewDocument；保持一个 TCAD
`PLUGIN` 组装，符合单入口和奥卡姆边界。

### 2.2 旧 role/transform loader 消费者：已闭合

R5-A 现在逐一处理：

- `artifact_agent/runtime.py` 的 legacy role output/context 装配；
- `platforms/codex.py` 的 Agent 生成和安装 profile 期望集合；
- scheduler prompt 的静态资源归属；
- control/Worker daemon、安装脚本和测试装配。

并要求 clean-wheel 的 `open_runtime`、`scid init codex`、control daemon、Worker daemon 四条真实
入口验证，明确禁止空 loader 或兼容 facade。该闭包能够在删除源码扫描与旧 entry point 后维持
真实启动路径。

### 2.3 Transform producer family 总函数：已闭合

修订已纠正首轮指出的事实错误：现有 request fingerprint 只是 scheduler binding 字段，不是
Artifact 标签。新方案统一由 compiled Transform 调用器生成
`operation_invocation_fingerprint`，并使用：

```text
operation id/version/digest
+ invocation fingerprint
+ ordered parent refs
+ compiled output ports
```

恢复同次调用。修订链则从唯一 `usage=revision_base` 与 `usage=change_request` 输入定位 base/patch，
再通过 patch 输出合同的 `revision_base_port` 验证同一基线。完整 family 按不可变成员集合去重，
冲突失败关闭。

负例覆盖了缺 fingerprint、相同父链不同调用、同一 family 多 subject、缺兄弟、digest 漂移和跨
实例绑定。Root 不再需要端口、Operation、Schema 或角色白名单，也没有新增 provider registry。

### 2.4 复杂度口径：详细计划已闭合，上位文字需做一处同步

详细计划的三重口径能够防止搬文件和压行作弊：

1. R0 固定通用路径集合，职责移出时新文件继续计入，目标相对 8765 净减至少 10%；
2. 整个 `operations/` 包不得高于 R5-0；
3. `src/ + plugins/` 全部生产代码继续计数，core→plugin 不算删除。

`deploy/install.sh` 被明确单列，仍审查增减但不混入通用 Python 核心 10% 指标。单文件
320/450/430 行预算已降为诊断，避免现有多语句压行进一步恶化。该设计比首轮版本更符合
奥卡姆剃刀。

剩余文档差异见 F3：上位计划第 24.2 节仍可被读成把表格中的 `deploy/install.sh` 纳入第一口径。

### 2.5 双 daemon 配置摘要：实现形态合理，门禁承诺需收窄

修订选择的最小机制是：

- 两个实际 daemon 在完成配置读取、Schema 校验和 contribution 构建后各自产生排序摘要；
- 摘要只含 plugin id、configuration schema digest 和原始配置字节摘要；
- 文件位于 systemd `RuntimeDirectory`，不是数据库、Artifact、capability 或 registry；
- 一次性健康探针比较两个实际进程的文件，不重新读取配置冒充 daemon 证据。

该机制本身不过度设计，也比在线握手、租约或共识更小。问题仅在于计划同时声称摘要漂移会在
“创建执行或领取任务前”失败，而一次性外部探针目前没有被定义为每次 admission 的输入。详见
F1。

### 2.6 R5-G 科学效果回归：已闭合且范围适当

R5-G 已清楚区分：

- 真实 Operation Agent 科学产出；
- Artifact/Task/Approval/Execution 与 transform/scorer 的机械链；
- 冻结历史 solver 原始输出的 replay；
- 可选、经 UI 授权的真实 Sentaurus；
- 独立科学审查；
- 单 Agent 对照与 8765 历史参考。

量表覆盖证据追溯、物理合理性、可证伪/可识别性、实验区分度、deck fidelity 和 diagnosis 与原始
曲线/指标一致性；失败按框架、Agent 科学判断、数据/solver、人工等待和外部环境归因。一次运行
不宣称统计优越性，也不要求三领域 benchmark，范围合理。

唯一剩余问题是运行状态保存位置可能把敏感材料混入版本库，见 F2。

## 3. 剩余发现

### F1（中）：一次性摘要探针不能同时充当未定义的逐请求 admission 门

位置：`R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 9.2 节。

计划一方面明确“不建立在线握手”，另一方面写道摘要不一致会在创建外部执行或领取带领域工具
任务前失败。当前 control 与 Worker daemon 没有共享健康权威；两个 `/run` 摘要文件加外部探针
只能证明部署组合一致，不能自动进入每次 `operation_preflight` 或 Worker claim 的准入判断。

若为了兑现这句话再让每次请求读取对端文件或建立共享健康状态，就会把一个部署诊断事实升级成
新的运行时权威，反而违反 R5 的最小设计。

最小修订：二选一并在计划中写死，推荐第一种：

1. 把 R5-E 定位为部署门：systemd/安装验证只有在两个 daemon 摘要探针通过后才把组合标为
   healthy；Root preflight 只验证 control 本地 adapter 绑定，Worker claim 只验证 Worker 本地
   tool service。明确手工绕过部署探针启动两个不一致 daemon 不在 R5 的逐请求防护承诺内；或
2. 若必须逐请求拒绝，必须说明现有哪个只读、非持久事实被两端共同消费并给出失败顺序。不得
   新建数据库状态、租约或配置权威。

不应为此增加在线协调；诚实收窄承诺是最小修复。

### F2（中）：R5-G 不应把完整 state 和原始日志直接保存到版本库交付目录

位置：`R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 11.1 节。

计划要求“运行产生的状态、日志和报告”保存在仓库内 `deliverables/r5-e2e/`。实际 state root、
daemon 日志和 Codex 诊断可能包含任务 token 数据库、绝对路径、socket、配置位置、模型事件或
其他不应进入 Git/发布包的运行信息。用户要求冻结数据不得只放 `/tmp`，不等于授权把完整控制
状态和未脱敏日志提交到仓库。

最小修订：

- 版本库只保存冻结输入 fixture、checksum manifest、封存科学对象的可公开副本/摘要、量表、
  脱敏运行证明和最终比较报告；
- 隔离 state、secret、socket、Codex home 和原始 daemon/模型日志放在权限受限、非 `/tmp`、不进
  release/Git 的持久运行目录；
- 报告记录该目录、清理/保留策略和证据 SHA-256，但不得复制 token、密钥、配置内容或身份；
- 增加 release builder/secret scan 负例，证明运行状态没有进入发布集合。

这不会削弱可重复性；真正需要长期冻结的是输入、输出和审计证据，不是可恢复控制状态。

### F3（低）：上位复杂度口径仍与详细计划存在可避免歧义

位置：`OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md` 第 24.2 节。

该节表格同时列出六个通用 Python 文件和 `deploy/install.sh`，随后写“上述通用文件加新
operations”。详细计划则已正确规定：R0 的六个 Python 路径构成第一口径，部署脚本单列。

最小修订：把上位第 24.2 节同步为详细计划的三重口径，并明确 `deploy/install.sh` 不进入 Python
核心 10% 分母但单独审查。不要修改 R0 历史报告中的原始表格。

### F4（低）：参数能力迁移与破坏性旧入口删除之间缺少显式独立门

位置：`R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 5 节及第 10.3 节。

R5-A 同时包含完整参数纵切面迁移和旧 role/transform/Root 创建入口删除。文本要求“新路径真实
运行通过后再删除”，但阶段独立审查只列 R5-A 完成后一次。考虑旧入口删除会同时影响 runtime、
Codex 和 daemon，这两个动作是不同风险边界。

最小修订：不必新增大阶段，只在 R5-A 内增加两个独立门：

- R5-A1：参数完整纵切面及所有真实消费者迁移通过独立审查；
- R5-A2：随后删除旧发现/Root 创建面，再做 clean-wheel 和独立审查。

R5-A1 未通过时禁止开始删除。该修订落实用户“每个关键环节独立审查”的要求，不增加产品实体。

## 4. 过度设计与遗漏判断

修订后的方案总体没有复杂度反噬：

- producer invocation fingerprint 是既有 Artifact label，不是新表或运行状态；
- runtime summary 是短生命周期部署证据，不是科学对象；
- R5-G 是一次小型回归，不是通用性 benchmark；
- 盲插件只保留一个合成夹具，真实第二领域留到 R6；
- `RecommendedTaskMode/NextTaskMode` 被正确识别为科学 payload，而没有因名称误删；
- 巨型文件仍按“先删后拆”，没有 repository/service/factory 四层模板。

除 F1—F4 外，未发现需要新增注册表、状态机、持久权威、领域 Root 白名单或第二调度器的遗漏。

## 5. 文档权威和状态

三个当前文档状态一致：

- R5 详细计划标为“首轮打回、已修订、等待第二轮审查”；
- 上位计划把 R5 标为“待独立审查”，生产实现未开始；
- README 只做索引和摘要，没有声称修订已经通过。

首轮报告保持历史“打回”，未被改写。R4 继续是已完成基线，R5 条件由活动提案承接。第二轮若按
本报告修订，下一轮只需核对 F1—F4，不必重复发明新的方案范围。

## 6. 本轮验证边界

本轮没有运行 pytest、daemon、Codex Agent、审批 UI 或 solver。使用 7 GiB 地址空间上限和串行
只读命令，复核了计划、上位状态、README、首轮报告以及当前对应的 runtime/Codex、参数 Schema、
producer family 和 runtime plugin 代码依赖。

因此本报告只判断修订方案的可实施性，不预判 R5 实现正确，也不重新继承 R4 测试结论。

## 7. 冻结的最小复修清单

再次送审前只修订以下四点：

1. 将双 daemon 摘要明确定位为部署健康门，诚实限定本地 admission；不得新增在线共享权威；
2. R5-G 只把脱敏、可发布证据写入 `deliverables`，完整 state/secret/raw logs 使用非 `/tmp`、
   非发布、权限受限的持久目录，并增加泄密/发布负例；
3. 把上位计划第 24.2 节复杂度口径同步为详细计划的三重口径，部署脚本单列；
4. 在 R5-A 内增加参数纵切面迁移通过后、旧入口删除前的独立审查门。

不允许借这四项复修增加新领域、真实 solver 强制门、插件热升级、Skill 物化或运行时共识。

## 8. 最终结论

**有条件通过**

仅允许修订第 7 节四项；修订并再次独立审查通过前，不允许执行 R5-0。

