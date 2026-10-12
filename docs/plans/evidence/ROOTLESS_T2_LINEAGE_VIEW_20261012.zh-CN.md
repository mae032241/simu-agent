# T2：单谱系默认视图与兼容边界

状态：实施已冻结，分批定向风险门禁及独立安装门禁通过；独立源码审查待完成，尚不是节点 PASS。基线 T1 `5a4713e`；范围依据 [T0 冻结设计](../ROOTLESS_T0_LINEAGE_DESIGN.zh-CN.md)。本节点无科研模型请求、不修改原科研实例，不引入辅助者或新的预算/执行器。

## 1. 新入口与冻结布局

新 `prepare` 默认冻结 host `lineage_projection_version=1`，科学输出仍为协议8。程序接口可显式 `None` 准备旧布局兼容夹具；已存在 settings 不迁移。创建 job 时，新设置只影响新 job；retained job 始终按自身 marker 重建，缺 marker 保持原生成器。旧协议1–7不启用新布局。

新 science-task 只有一个 `lineage` 默认 brief，不再同时投递 `history` 与 `search` 摘要。所有谱系域及 inline 实现选择摘录使用 UTF-8 JSON、indent2、末 newline 合计检查，≤4096B。必要的直接前驱科学输入与已绑定原文件仍走原直接输入机制，不复制祖先附件。

host 的 `history` binding 继续绑定 nodes、只读 files 和 candidate IDs；新布局只是它的唯一默认 view，不新增可变候选表、余额、current-attempt 或关系账本。`search` 继续冻结 focus、repair root、limits 等原准入字段；新路径不组装 legacy search 摘要。实际调度、硬预算、收口和 continuation 计数保持原控制入口。

## 2. 复用与移除的装配

| 函数/接缝 | 本节点实际处理 |
| --- | --- |
| `history.source_sequence/_source` | 原源完整性检查及 closeout cutoff/extra-node 边界共用；不从缓存猜原件 |
| `history.records_from_sources` | 原节点科学页构造从源遍历中拆出；legacy rebuild 仍保同布局 |
| `search.fold/apply_source` | 原机制解释、control receipt 重算、W slice/repair 统计共用；未引入第二科学解释 |
| `lineage.project` | 一份验证后的 source 集合供节点、机制、候选与三关系投影；不再次调用 history.rebuild/search.project 装配 |
| `lineage.candidate_view` | 原 candidate overview 原样迁移；history.candidate_overview 只作兼容 facade。T4 的 null/可比性新规则不在本节点混入 |
| `lineage.bind/brief` | 共用 page writer、单默认 brief、公开关系页；只为新 marker 生成 |
| `history.bind/search.bind` | 旧布局保原 renderer；新路径不投递第二候选/机制摘要，保原绑定与准入责任 |
| `history.refresh` | 新 marker 通过统一 project 更新可删投影；legacy job 保原 refresh。缓存不是权威 |
| `contracts.build_job/science_view/_validate_inputs` | 按 retained marker 选择布局；schema、science raw、selected input 意义不变 |

## 3. 容量、导航与公开范围

- nodes 每页≤8；候选、机制、实现和关系每页≤16，并使用实际 UTF-8 字节≤64,000B及原历史总量32MiB边界。
- `indexes`、`next_page`、omitted count 给完整分页入口，第17项和第9节点不会因默认摘录隐藏而失去选择入口。
- 摘录按 UTF-8 安全截断；summary≤160B、limitation≤96B、label≤80B、minimal_test≤160B，并保截断/遗漏标记及原结论页。
- 合法原科学输出保完整文本分页，当前 H/W/A/E 可按需读取；历史实现仅给稳定对象 ID 导航，仍需 explicit selection 才交给后继。
- 默认 brief 超容量时仅减少导航摘录并增加遗漏计数，不删除 current/A推荐/actual 独立槽，不放宽资格或猜完整 coverage。
- 公开复用关系页只含科学对象 ID、来源节点、有界 label、原结论入口与 declared 限制；不投递 host source 路径、hash 或材料 receipt。
- candidate 页的 `execution_status` 来自 T1 精确调用事实，表示 known_success/known_failed/unknown；原 observer `status` 及作者科学结论独立保留。工程失败不等于科学无效，status=ok也不等于审计合格。
- 支持关系无明确原科学声明仍 unknown；派生/复用不授予因果证明或继承资格。T3 wrapper 部署及 T4 公开选择规则另节点实施。

## 4. 验证记录与待退出项

首组父级共享串行门禁：120 passed、3 failed，日志外层 `.trial/t2-source-20261012-01/batch-001/pytest.log`。三个失败为旧视图夹具假设：假 native A 将缺 `search` 当 legacy，自行提前 finish；第一 H 无历史原件页；长 UTF-8 机制夹具读取旧 search view。已改为新 lineage 入口，并保持五节点真实 transport、两 W meter/restart、真实 accepted A 历史页损坏、20机制/16行/64k/只读/原结论断言。

新增 `test_lineage_view.py` 覆盖全角色单 brief/原科学页、9节点与17候选/实现分页选择、复用页无私有绑定、缺页/改页硬拒、旧1–8任务/原件逐字重建、1000节点多字节纯 renderer、known_failed 实验与原科学结论分栏。测试由父级统一执行；作者不跑测试、构建或模型。

分批复验（不能称一次全套运行）：

- 外层 `.trial/t2-source-20261012-02/batch-001/pytest.log`：30 passed、1 failed，6.25s；剩余 history 页夹具在已 seal W2 的 instruction 与前驱 route_reason 不一致，提前触发 retained-route 拒绝，尚未触达页攻击。
- 修正 W2 真实前驱 instruction 后，外层 `.trial/t2-source-20261012-03/batch-001/pytest.log`：16 passed，9.77s，含完整性负例及13项 closeout gate。受损 accepted A3 必须 `seal_pending`、已完成2节点、reason 明确为 bound history page changed；不允许以 sealed_node_invalid 掩盖夹具错误。
- 本轮原123项集合风险经分批覆盖，另含新增 known_failed 分栏及13项 closeout；没有声称同一 snapshot 一次全套通过。

独立安装门禁：外层 `.trial/t2-installed-20261012/artifacts/result/result.json` 的9项 installed CLI 检查及新 settings/job marker 断言通过；17个 research_loop 模块 source、wheel、installed 逐字节一致，0模型请求。

独立源码审查通过，报告见 [T2 review](ROOTLESS_T2_REVIEW_20261012.md)。原科研费用、读取次数及效率提升没有本节点真实实验验证，不能从 brief 字节下降推断 token 或科学收益。
