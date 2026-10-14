# 角色 context 选材独立审查

状态：**PASS，限定 full02 的角色选材源码资格**。最终 authority 为 `/tmp/scid-context-full-02.json` 五文件，独审实际 SHA 全部 MATCH，最终 context 七项源码门禁通过。安装/live 与协议15实际广度准入联合资格仍待后续验收，不授真实科研效用、helper token 减少或完整新协议 PASS。独审只读冻结差量和父代理证据，不运行 tests/build/模型、不改生产/测试，也不读取进行中的 breadth 实现，仅维护本文件。

## 审查 authority

基线43f77e3；父协议15差量不属于本 worker 的实现 authority。full01 初审及其运行是历史阶段，以下列出最终 full02，含必要的 W 冻结机制组合纯 view 接线；该 view 不授 accept/grant 资格。

| 文件 | SHA256 |
| --- | --- |
| contracts.py | `457eb0f2cb0f3eb835f22cfb4fb7f09077eb507795bd710a593036a5639d4295` |
| checkpoint.py | `f7f3d89d46d302eee0d3b66a0e33e4104e4725edcee7717f01d97d182d8e8996` |
| selection.py | `e7c2231c161ed7ee8411ea2469942d1037af329c2373dc8edbb847f8314eaec1` |
| test_context_selection.py | `6b40211ec1e0725c09406031e5967d5d7170aac5a29aaa593f5f35369f5ef50b` |
| test_lineage_view.py | `7feeb63355c90a1457f2cd8260e2e40391ef156bdfaa20be1f4edc3296d4ad96` |

## 实际信息边界

- science_view 复用冻结 history view，deepcopy 后按 H/W/A/E 当前问题排序 direct parents；E 优先 requester。只改变展示顺序，不改 job、科学计划或结论。global objective/updates 保留原实际输入路径。
- parent preview 校验 exact direct conclusion SHA，给作者角色与完整 limitation 项目；总 limitation 预算1024按 parent 分配。超长条目可跳过而不挤掉后续短条目，omitted_count 与原 conclusion 入口明确。没有关键词抽取、推测“反例”、编造未知结论或把作者 prose 当 execution fact。
- A 保留全局 proxy；其它角色仅隐藏默认 proxy ranking 并增加省略组计数，原 candidate indexes 仍可补读。未改 current/actual/A recommendation、unknown、failed、coverage 或其它未完成机制事实；proxy 与 target qualification 仍明确分开。
- selection.project 优先推荐/current/actual/confirmed candidate 的 audit，再保 public audit failed；增加最多4条 failed/unknown alerts及全量计数/省略计数。状态只来自已验证结构字段，不由 prose 文本推断。长列表按字段优先级删减，target_best 仍未知，delivery 不凭公开 audit 获授权。
- checkpoint.brief 优先保1536 bytes 的完整 authored limitations，先裁文件列表，再裁 understanding/summary。计 omitted files/limitations 与 truncated；新增 authored/not independently verified 提醒、原 unfinished_plan count/index及 stage_intent，不将未消费机会解释为科学上未测试。

## 可读入口、helper 与大小限制

新 tests 检查 objective、direct parent conclusion、unfinished mechanism index 在实际 task workspace 存在，late caveat 不被冗长正文覆盖；这些是已封存 parents/index 的入口。previous fragment 的完整正文**未挂载**，brief 明确 incomplete，未伪造可读路径。被省略的该 fragment prose 不能声称可从 science-task 恢复；此限制沿原权限保留。

reading_order 建议先核相关约束/limitations，再按需读 supporting originals或原权限允许的 bounded helper。它不强制所有父全文，不扩大 helper 权限或创建新历史库。是否实际避免 helper 重复全文、是否节省真实 token 尚未模型验收，不能从指导语推断。

science_view 简化 implementation_reuse 提示，但 frozen result_schema 仍明确 null 保留/[]清空/科学 IDs替换。作者确认原 native stdin links_instruction 也保留这三语义，本轮未改 native；不为任意 launcher 声称 schema必然展示。

selection.project 与 checkpoint.brief 以实际 indent2/UTF-8 JSON bytes 校验 ≤4096，包括 quote/backslash/newline 膨胀。完整 science-task 并非4KB合同，本轮 test 仅验证典型组合<12000 bytes及不嵌入父长全文；不得扩大为所有角色任务总长4KB或一定比旧 view 小。

## 初轮运行状态与后续 gate

父代理 source01 为80 PASS/20 FAIL；context 新六场参数用例、selection 和 worker_fragments 已通过。失败原件保留，父分类为旧 current14/协议7、旧 invalid-ID/history结构 fixture；这不是最终完整 gate PASS，也不用于掩盖未来实际生产失败。lineage_view 仅 current 常量 fixture更新，原四文件 freeze未变。

## Full02 差量与最终源码证据

contracts 删除逐 parent 重复 interpretation，合并为简短 reading_order，保留 authored/observed 区分和按需补读/原权限 helper。W 的多机制 question 不再暗示只能一个 H mechanism；`_role_lineage` 从 frozen job.search.breadth.mechanisms 形成授权 count、最多4项机制 ref/label/作者 status/原 H page，隐藏默认单focus及 baseline/grant/source H SHA。保留原 unfinished_plan；调用原 bounded_brief 校验组合 view 字节容量，不改 job。测试的 breadth 是明确构造的纯 projection 输入，不能称真实 search.bind/accept/live 接线已验收。

- [source04 最终 context 日志](../../../../../.trial/context-selection-source-04-20261014/batch-001/pytest.log)：7 PASS，2.79s。包括所有角色、whole late limitations、失败/未知、片段4KB及必要 W 组合 view；核每 H page在 workspace 存在、不泄露 private baseline/hash/accepted_count、lineage JSON≤4096、job 不变。
- full01 的 selection/checkpoint/worker_fragments 相关源码用例已在父 source01 通过；后续旧 fixture按当前协议修复。独审核对 [source02](../../../../../.trial/context-selection-source-02-20261014/batch-001/pytest.log) 为41 PASS/3 FAIL，剩余三项 invalid-ID旧预期在 [source03](../../../../../.trial/context-selection-source-03-20261014/batch-001/pytest.log) 补跑3 PASS、0.71s。保留失败证据；这是差量组合覆盖，不伪称单次完整重跑。父修旧协议7/ID-unresolved/history page fixture不恢复旧运行语义。

## 实际对照测量与限制

独审读取 `/tmp/scid-context-view-compare.py` 及父 [source04/view-comparison.json](../../../../../.trial/context-selection-source-04-20261014/view-comparison.json)：对同一 frozen job，比较旧43f77e3 science_view 函数与当前函数，不是两个完整运行或真实模型输入 token 测量。

| 角色 | 旧 view bytes | 新 view bytes | 增加 |
| --- | ---: | ---: | ---: |
| H | 5959 | 6390 | 431 |
| W | 6515 | 7244 | 729 |
| A | 7242 | 7877 | 635 |
| E | 5892 | 6328 | 436 |

每角色默认新增7条完整 parent limitations，保留1 failed/1 unknown/4未完成机会；A保全局proxy组，其余默认隐藏并标省略。初版曾增加约1.2–1.4KB，去重复后仍为正增量；**不宣称 view 更短、真实 token 减少或 helper 避免全文读取已验证**。本节点以必要信息可见、源入口可补读、无科学事实捏造和有界片段/候选投影为源码资格。

无本节点剩余源码阻断。父可独立提交视图和当前协议/fixture差量；全新 protocol15 的实际多机制冻结、common accept 广度准入、逐call身份、安装 namespace/live须由后续联合验收取得。旧实例仍只读，未经本节点在线迁移。
