# N2b：分页科学历史与候选事实投影

日期：2026-10-11。状态：实施完成，两位独立审查者分工复审PASS；最终组合回归与安装验证通过。无模型 Turn、训练或评分。N2a 已独审并提交 `c64a436`；本节不实施 N3/N4 的科学候选动作树。

## 当前角色读取与后继复用

新 job 冻结 `handoff_protocol=3`，追加历史绑定与 A 可选推荐字段。已有无协议／协议 2 的 job、Schema、科学视图与 seal 保持原字节；协议 2 的显式旧实现转交继续有效。

每个封存 H/W/A/E 节点以原 `summary` 和 `limitations` 形成尝试记录；控制层不另调用模型总结、不从 “failed” 等词推断重要性。H 范围及 H 前驱关系仅从实际科学节点结构派生。默认 science-task 历史简报 **最多 4096 UTF-8 字节**：近期 3 条（摘要最多 160 字节、一个限制最多 96 字节）、最近 3 条已有角色限制引用、8 项 H 范围谱系，以及实际分页入口；显示截断／遗漏并给原结论页。

索引每页最多 8 节点、候选索引最多 16 项，并按实际字节联合打包，单页不超过 64000 字节。每条给原节点与只读结论页；完整原科学输出 JSON 的文字按 8192 字符分页，当前角色可直接读取，不需增加模型轮次。默认提示不展开所有历史原文。历史正文含旧附件引用时，只是原科学文字，不能让 launcher 递归继承附件。

旧实现入口如 `history/nodes/002/artifacts/candidate.py` 是科学 handle，**不是当前已挂载代码**。只有现有 `#reuse-implementation` 标记作出明确科学选择，宿主才按该 job 冻结的历史节点 seal 核对原件，并交给下一节点唯一选中旧文件；保持原拥有节点的四字段路径。普通引用不转交。不新增下载命令、索引制作或角色哈希劳动。

历史页留在 `inputs/history/`，不成为本节点新成果，不进入后继整包继承。job 冻结节点 seal 和页哈希；验证同时复核旧 raw/job/result 与 seal 身份，拒绝原件或当前页变更。单个 job 的历史页总量 32MiB，超界在模型启动前拒绝，不能偷偷扩张。

## 宿主机械事实与科学选择

`prepare` 可选 `history_observer={adapter, config}`，或 CLI `--history-observer-config`；冻结可信、同步、无副作用外部 adapter 的原路径、代码哈希与配置。通用 core 不写 cov 解析或隐藏评分读取。调用 5 秒、输入/输出各 256000 字节，每次 128 个新候选；候选 ID、实现 handle、评估口径、指标与公开原件证据均有大小／数量界限。

外置 `scripts/observe_covshift_candidates.py` 只流式扫描配置的公开 run 台账（最多 4MiB 扫描字节），限新增记录而非旧历史总条数，覆盖不足标 `partial`。只在 harness 确切指向已封存交付原件时关联实现；scratch 不猜为等价代码。读取公开 `exp submit` 事实与模型字节，绝不 unpickle、训练、提交或读取 hidden score。可信宿主 adapter 权限本身不是隐藏数据的隔离证明。

四个位置相互独立：

- 当前候选：只有显式机械事实才有值；cov adapter 没有此原件事实时为 null。
- 代理最高：同冻结 `evaluation_key`／指标方向下的最高**已观察**值。不同口径不比较；附原科学结论页，回查适用条件和盲区，不能声称目标最优。模型是否已保留另述。
- A 推荐：角色在可选 `candidate_recommendation` 中作科学选择，只能指向当时已冻结候选；未知省略／null。不由 host 从 prose 或最高指标猜测。
- 实际提交：公开原件证明的实际 `exp submit`，独立于前两栏；候选关联未知可 null，非空必须已观察。不是外部评测接收或隐藏评分资格。

parent/action 等尚无科学声明的候选关系保持未知。`observation_step / observation_h_scope / observation_summary / observation_conclusion` 仅指首次观测节点的科学上下文；补观测旧 run 时不能归入新 H，`candidate_h_scope` 保持未知。确切实现另给 `implementation_owner_step / implementation_conclusion` 的原代码拥有节点，不能冒充候选生成节点或科学归属。N3 再扩科学关系，不要求角色重抄整张台账。

## 恢复、容量与留存

`host-history/nodes/` 和 `overview.json` 是可重建投影；每次封存包括最后 A 都更新。按节点／原 seal 去重，删失或投影篡改从原 seal 重建，不重新跑角色。`host-history/observations/` 是已被原 seal 哈希绑定的观察原件，不能当成可删除缓存或重新读取“最新”台账替换。

公开台账／提交模型原观察字节封存在 `host-history/objects/<sha256>`，按内容去重；无变化模型不会每角色重复复制。每件最多 32MiB，实例总对象 128MiB；一次观察去重后的原件读取总量也最多 128MiB。归档原件缺失／篡改拒绝。留存容量不足明确 `digest_only`／`unavailable`，只保留观察事实并说明无法回读原件，不能称 best 模型已保存。宿主归档不挂载到科学 workspace。

可选 adapter 超时、格式或容量失败封存有界 `unavailable`，记录宿主 failure_type/error_code（不在科学 brief 展开内部异常／路径），科学结论仍可封存。配置／身份／原 seal／归档原件篡改仍 fail closed。恢复复用同一观察快照，不重采未确认的旧观察。

## 文件与核验范围

源码：`research_loop/history.py`；`contracts.py` 新协议科学绑定、历史 handle 选择、封存／恢复；`controller.prepare` 仅配置冻结；CLI 仅可选配置入口；外置 cov adapter。新增 `test_history.py`，N2a 测试 helper／旧协议兼容随协议升级调整。N1b 的预算、时钟、生命周期语义保持不变。

最小回归覆盖四角色尝试分页、当前节点回查旧原科学字段、H 修订旧实现显式转交、缺失缓存重建／不重复、原科学来源与当前页／seal 篡改、旧协议 1/2 字节兼容、最坏多字节 4096 字节 brief、节点／候选按字节分页、不同评估口径与三栏分离、未知 A 推荐拒绝、可选 observer 失败不丢科学结论、公开旧台账超过 128 但新增少时有效、台账追加／模型覆盖后原观察可读且去重、留存容量明确未知、实际候选不存在不造事实。真实隔离 wrapper 与 installed CLI 无模型核验另记录，不把源测试授为科学／任意内核资格。

## 当前冻结核验

- source 定向：95 passed，12.44s，`/tmp/scid-n2b-frozen-focused/batch-001/pytest.log`；最后新增“known ID 误报更新不能污染 seal”负例及观测字段命名修订后，history 定向 25 passed，4.27s，`/tmp/scid-n2b-candidate-final/batch-001/pytest.log`。
- 另一作者之外的生命周期审查者 history 小门禁：14 passed，3.60s，`/tmp/scid-n2b-history-independent/batch-001/pytest.log`。最终 delta 仅候选观测分支／显示字段及负例，历史原文绑定、分页、恢复函数不改；最终冻结变更及SHA已复核通过。
- 真实外部 wrapper：`/tmp/scid-n2b-wrapper-isolation-20261011/result.json`，bubblewrap 外层 + native 0.162.1 最终工具 sandbox，16/16 canary 通过；当前角色实际读完整旧科学字段页，页只读、brief≤4096，虚拟旧实现只转交唯一原文件；旧原目录、未选文件、host job、private score canary 拒绝，private score literal 不进入 history。0 模型 Turn、0 实验。该 canary 未配置 observer，不授可信宿主 adapter 的隐藏数据隔离资格。
- 冻结 `history.py` SHA256 `78688ece6cf683f2c258ea45dd96b021352507dfa5691fd9eb1980306fe7edf5`；`contracts.py` SHA256 `99ea63f92ec6f3dc3b4f4b9f036d302c1d3f0528dcc0052cb4a5ee796729a4d9`。`git diff --check` 通过。installed CLI 与最终组合门禁由父代理另作独立核验；未重复安装或运行模型。

## 父代理最终验收

- 整个 `tests/research_loop` 组合回归 **130 passed in17.92s**，共享串行资源监督入口；[结果](rootless-n2b-20261011/source-result.json)、[日志](rootless-n2b-20261011/pytest.log)。
- 修复后的最终安装wheel完成六节点HWAHWA；启用真实cov adapter读取假公开台账。代理最高run1、A推荐run2、实际提交run2保持独立；源台账与模型改写后可重建历史，重复run无重放。[安装结果](rootless-n2b-20261011/installed-result.json)。0模型。
- 两位独立审查分别覆盖候选/观察器/生产接线与历史/分页/隔离；最终源码通过，精确SHA见[源码清单](rootless-n2b-20261011/source-manifest.json)。
- 已修复审查发现的原文篡改校验、容量阻塞科学封存、可变原件丢失、按字节分页，以及重复候选ID在封存后阻断恢复的问题。
- 未执行无关全平台回归或真实科研效果验证。只有后续剩余两场cov才消耗模型预算，旧live02仍计已完成第一场。
