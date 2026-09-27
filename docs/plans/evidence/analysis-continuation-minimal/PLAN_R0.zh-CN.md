# 分析续接与机械映射最小修订计划 R0

日期：2026-09-12。状态：待独立审查，未授权以本草案开始源码修改。用户授权审查通过后执行。

## 1. 目标与证据

承接 scheduler-attempt-budget/CONTINUATION_PRIORITY_1.zh-CN.md 和 LIVE_FIG4.zh-CN.md。
最新 Fig.4 已封存 60/60 原子单元、三图及有限结论，当前不是重跑研究。源码修复降低下一次续接准备成本。

已发生问题：

- 旧续接首项计算距创建约 377 秒，工具读取返回约 242749 字节且三次截断；这包含包装/重复，不等于净上下文或纯阅读时长。
- 最新续接约 882 秒完成，仅余约 18 秒；既有四份案例对应关系仍被要求补写，两次提交拒绝分别为 source reference lacks matching evidence 和 undeclared case mapping requires explicit source evidence。
- 原 sealed prior_analysis 已含相同四个映射，且 solver_outputs、experiment_plan、reviewed_package 是相同 Artifact；已有 prior_source_bindings 证明旧别名到当前别名，但案例消费者没有复用。
- 恢复目录和文件为 0500/0400。复制后写脚本或创建运行锁失败。现有快照已排除非白名单 lock/stop；不把“复制了锁”当作已定位根因，测试应覆盖只读父目录。

成功标准：新分析 Agent 的简明入口能定位目标、进度、待做事项与错误及原始记录；受控准备出的工作副本可直接编辑/启动；已证明的旧映射无需再次手抄；真正的新科学关联仍由 Agent 决定；拒绝能定位具体输出字段。程序不宣称拟合成功、不替 Agent 选择目标或解决 Fig.4 角点方法问题。

## 2. 约束与最小边界

- 保留 Operation、Run 四态、端口、Artifact 和审批机制。不新增角色、状态机、映射注册表、工具或科学必填字段。
- 准入仅在 preflight/invoke；输出验证只核对新输出的明确主张与冻结来源，不重审输入资格、不重算评分。
- 只修本次 analysis 续接路径：共享分析工作区覆盖通用分析和 TCAD 分析；TCAD 案例语义只在 TCAD 插件。其余角色沿用现有行为。
- 原 Artifact、恢复原件、旧 assignment、旧 Run、外部 failed/97 收据及已封存科学结论不改写。新文件物化使用当前编译合同；不在重开旧 Run 时套新合同。
- 不按相同文件名、相同字节或最新 head 推断身份；身份相同也不自动赋予科学资格。
- 不新增一次性全量测试；全部测试/构建串行，512 MiB 地址空间及进程树内存限制，单次墙钟 150 秒，BLAS/OMP 单线程。

## 3. P1：一个可追溯的简明续接入口

复用 curve_score.analysis_workspace.materialize 与 domain-workspace.json，产生只读 analysis-start.json，版本 1，最大 24 KiB。

内容是确定性的摘取/索引，不是程序生成科学总结：

1. 当前 instruction、deadline；绑定 objective/current_progress/experiment_plan/prior_analysis 的相对文件和 JSON 指针。
2. 从既有 JSON 字段逐字摘取 objective、当前目标、deferred_goals、summary/limitations 等短字段；每项带 source_name、pointer；上限后明确 omitted 和原文位置。未知 schema 仅索引，不猜阶段；并存进度全部保留来源，不选“最新”。
3. 恢复覆盖 saved/omitted 和保存脚本、结果、错误日志的路径索引；草稿标记 scientific_evidence=false。不自动把草稿结论/计算成功当作事实，不解析日志推断科研结论。
4. 指向完整 assignment、输出 schema、工具合同具体 JSON 指针与原文件；完整合同仍保留。

LocalWorker 打开**新分析工作区**时返回此入口路径及合同路径/指针，避免把完整工具合同再次内联返回。非分析和旧工作区仍保留原返回行为。分析 prompt 明确先读简明入口，再按需要读取目标/方法/完整合同与原件，禁止为了缩短阅读跳过科学所需输入。检查入口字节预算、不可见输入不泄漏、完整字段可追溯及旧工作区兼容。此阶段证明减少重复工具返回；不以字符减少冒充真实 Agent 耗时优化。

预计文件：curve_score/analysis_workspace.py；mcp_local_worker.py；通用 science_operations.py 与 TCAD result_analysis.py 的分析 guidance。

## 4. P2：恢复可编辑副本

在上述 materialize 中，仅从控制已验证的 provisional_roots 的 scratch 子树复制白名单文件到新 workspace/scratch；保持相对布局，目录 0700、文件 0600，使用既有 no-follow 有界读写方法，不继承 0500/0400 权限。

- 使用现有 MAX_FILES/MAX_BYTES，不扩容，不复制到 output/result.json，不把草稿变成提交成果。
- 无恢复、不完整恢复、缺文件均允许继续；入口列出恢复覆盖/遗漏。日志仅用已规范化副本。
- 不覆盖已存在不同内容，不跟随链接/逃逸，不恢复运行 lock/stop/cache；现有过滤可复用，不重复建规则系统。
- 准备失败应有明确文件及工程原因；不得悄悄宣称完整副本。可恢复错误保留原件与有界缺口，unsafe 路径不复制。
- 测试直接修改复制脚本、新建子目录与 launcher 状态、复用已有数字仅补图；确认输入和 recovery 原件内容/权限不变。新旧 Agent 均由同一准备逻辑获得副本。

预计仅共享 analysis_workspace.py；沿用原保全/工具预算，不改 runner。

## 5. P3：同一案例投影供可见入口、工具、提交复用

在 TCAD 插件新增一个小型纯函数模块 analysis_bindings.py。函数只消费已绑定 JSON 和只读 InputBindingDescriptor，产生当前别名到 output/experiment/case/basis 的视图；无数据库、原始存储、递归历史或新身份权威。

来源优先级与处理：

1. output_name 来源于当前 descriptor；明确项目 output.case 仍为权威声明。
2. 历史来源只取显式 prior_analysis 及其已准入的同 producer/direct parent manifest，复用 prior_analysis_sources。要求 manifest 中原 experiment_plan 和 reviewed_package 的完整 Artifact 身份映射到当前相同端口；旧原始来源和 basis.evidence_refs 也要精确映射。旧别名与当前同名不同身份不混用。
3. 仅继承旧 source_references 中唯一、无歧义、可完整映射的对应关系及原 rationale；旧记录只证明“此前的科学映射主张”。不重新赋予资格、不覆盖 Agent 明确提交的新 basis；冲突/缺失/旧记录不适用时列明不可自动继承，允许不带案例的有限报告或由 Agent 提出新的有证据关联。
4. 同一 raw 对应多个案例时不任选。global log 不强制归单一 case；只补可唯一确定的数据。新工具证据以当前已注册 descriptor 为准。

接入现有 workspace 钩子，不新建生命周期：WorkspaceMaterializationRequest/WorkspaceFinalizationRequest 增加默认空、不可变 binding_descriptors 元数据；RunService 用既有 source_descriptor 提供，包含 finalizer 时已收集的工具证据，不重读整批原始文件。JSON 读取仍受绑定文件与单文件上限约束，旧调用构造兼容。

TCAD 包装共享 analysis materializer/finalizer，保持共享 snapshot；通过编译 ComponentSpec 声明连接，纯函数同源用于：

- 简明入口的绑定映射和原始出处；不暴露控制内部 ID/hash/path。
- worker_tcad_curve_score/diagnose：请求省略已知 output/case/basis 时自动补；明确冲突仍按实际字段拒绝；记录补全后的有效请求和来源读取，使 receipt/replay 一致。辅助来源读取计入现有工具权限与观察。
- 新结果 finalizer：对 evidence.locator 指定的原始来源，生成/补齐缺省 source_references 机械字段；Agent 自选 source_key 不改写。只补缺省值，不覆盖明确主张；歧义留空不阻断。封存新结果内保存有效映射，下一轮仍可复用。
- 输出 context：使用同一映射规则；删除“source_references 每行必须另有 evidence 同名行”的重复表格门槛。保留重复 source_key 的歧义检测、明确主张的源/输出/案例一致性和计算收据真实性。

原 source_references schema 和 calculation_records 保持兼容。未知来源不能被补成有效来源，缺映射不使未写该主张的有限报告失败。机械补全后 schema 仍由既有输出检查负责，不因自动补全越过数量/字节上限；自动条目过多时只补可容纳项并保持原无映射引用可用，不截断 Agent 的明确输出。

预计文件：新 TCAD analysis_bindings.py；TCAD result_analysis.py；operations/workspace.py；service/runs.py。钩子实现在 TCAD 已有 result_analysis.py 或该新模块，禁止再增加一套通用投影框架。

## 6. P4：准确输出诊断

继续使用 declared_violation(path=...)，不用新错误协议。

- source_references[i].input_alias/output_name/experiment_key/case_key/case_mapping_basis.evidence_refs[j].input_alias；evidence[i].locator；calculation_records 的具体引用索引；身份错误必须明确涉及字段。
- 保留固定且可操作的原因，包含安全的 source_key/input_alias（受 Identifier 约束），具体预期值仅限安全语义标识。不输出未过滤任意内容、原文件绝对路径、密钥或 Artifact 内部 ID。
- 上层封装只加一次 $.payload 或 $.request；真实 timeout、输入损坏/工程故障沿用既有分类，不转化成“请 Agent 改科学答案”。
- 覆盖同 Run 一次拒绝→修正→封存；确认不再次运行输入准入或数值评分。

## 7. 实施顺序、检查与停点

1. 独立审查本计划：目标、可实施性、系统职责、最小范围。修订必要阻断并复审直至 PASS。保留计划版本及评审；冻结通过版本 SHA256。
2. 保存本轮涉及文件当前工作树内容/哈希为增量基线（仓库有大量既有未提交更改）；先跑必要基线测试，记录既有失败。之后按 P1→P2→P3→P4 实施；若新增必要生产文件或行为，先说明计划增量并审查，不自行扩张。
3. 在现有 tests/operations/test_analysis_evidence_recovery.py、test_analysis_input_descriptors.py、test_case_mapping_basis.py、test_tcad_result_analysis.py、test_prior_analysis_sources.py 和通用分析/合同测试上加最小组合用例；允许一个 focused test_analysis_continuation.py 集中新增场景，避免重复运行同 fixture 大矩阵。
4. 关键验收矩阵：无恢复/部分恢复/新 Agent和重开；旧 workspace 返回兼容；只读嵌套目录及新锁；越界链接；相同字节不同 Artifact/别名碰撞；原 cohort 改变；已有/歧义/新 case；旧 basis 依据未绑定；原始证据无案例也能有限封存；新增工具证据；显式错误源/案例准确定位；原 schema/receipt/非 TCAD 通用分析未回归。
5. 编译生产 catalog，确认 TCAD 工作区/工具/校验都连接共享解析函数；测试实际 MCP 返回、可见入口及 finalizer 封存结果，不能仅测纯函数。按现有 isolated wheel/stdio smoke 模板构建安装核心+curve_score+tcad_artifact 三包，在隔离临时目录测试一次 fail→new Run→复用结果仅补图→sealed→下一轮映射复用；不启动 solver。
6. 记录每组命令、退出码、耗时、RSS、失败定位、旧失败及增量 patch。只运行影响面检查，串行，不启动研究子 Agent 与测试并行。完成后给出可复制安装命令；线上安装由用户操作。
7. 用户安装后才开展真实 Agent 续接验收（独立新 Run，遵循已绑定实例/Operation/预算）；记录首项有效动作、读取返回量/截断、权限返工、重复计算、提交拒绝及详细定位。工程 smoke 不替代真实耗时证明，当前已完成 Fig.4 结论不重算。

交付：通过的冻结计划、独立审查、最小源码增量、受限资源测试和安装 smoke 证据、部署说明；真实 Agent 优化效果单独标识待安装验证。
