# T4：公开评估条件与选择概览

状态：已接生产，71项定向及独立安装门禁通过，最终独审通过。T2 已提交 a1881ca，T3 已提交 ac8e3fc。实际科学选择效果待T5。

## 1. 范围与事实边界

- 只读已经验证的公开候选事实、封存 A 的科学推荐、公开提交观测及已验证交付事实；不读隐藏评分、不执行实验、不自动推荐或提交。
- 每个精确 `evaluation_key + direction` 内给出 observed proxy 最高；未知 key 不排名，不跨版本比值、不填目标权重。排名反转的适用性由 A 解释。
- 状态 `ok`、较高代理分、父候选资格、实现已绑定均不能授予本候选审计资格。
- 独立公开审计输入只投影已验证 receipt 的结果，不是新资格权威。真正提交仍走 N6b 的隔离审计、promote、confirm。
- 缺数据及 partial coverage 不得补成 global best、目标最优或完整搜索树；不自动成为 N4 的 no_progress。

## 2. 最小纯函数接缝

`public_inputs(records)` 从 `lineage.project(...)["records"]` 抽取以下白名单；不传 whole records、contexts、proofs、hash 或原始路径给选择函数。

| 字段 | 内容 |
| --- | --- |
| `step/role/recommendation` | 已封存节点顺序、角色及 A 推荐或 null |
| `coverage` | 公开 observer coverage 的 status 或 null |
| `candidates` | `id,label,evaluation_key,metric,direction,status` |
| `current_candidate` | 当次公开 current 的 candidate_id 或 null |
| `actual_submission` | 当次公开 candidate_id、artifact_retention 或 null |

`project(public_records, *, audits=(), delivery=None)` 无 I/O、无时钟和可变状态。输入必须是白名单对象，步号唯一；同 candidate ID 的事实冲突拒绝，不取 latest 覆盖。候选数最多 4096，公开输入序列化最多 4 MiB。

`audits` 每项为 `{candidate_id,status,artifact_bound,leakage_flag}`，status 为 completed/pending/skipped/failed/unknown；只接受独立调用方已核验的公开 receipt。仅 completed + artifact_bound=true + leakage_flag=false 显示 `public_audit_passed`；缺失为 unknown；这不是模型安全或目标适用性结论。

`delivery` 为 `{state,last_confirmed}`；state 为 none/confirmed/failed/unknown，last_confirmed 为已核验的 `{candidate_id}` 或 null。confirmed 必须非 null。未知新提交只能显示 unknown，不能将旧确认当当前成功；旧 last_confirmed 仍可供审计。未知或已不在本公开候选集合的引用拒绝，null 候选公开提交观测允许保留未知。

生产首版没有冻结的交付 receipt 输入，默认 delivery=unknown，不读取当前 ledger；controller closeout 的既有确认结果仍单独作为交付事实来源。显式 audits/delivery 接口仅消费调用方已冻结/验证的事实，合成夹具覆盖，未提供时不假造确认或公开审计。

## 3. 输出与恢复语义

- `coverage=null` 表示该节点没有 observer，不更新 current；`current_candidate` 取最新有 observer 的槽，null 表示本次未知，不携旧 current。
- `a_recommended` 取最新封存 A，包括 null；`historical_a_recommendation` 单列之前非 null 的推荐及作者 step。A null 不等于否定旧方案，也不回填旧推荐。
- `observed_actual_submission` 为最近非 null 的公开观测并附 observed_at，明确仅历史观测；没有新观测不证明当前目标不变。
- `delivery` 单列当前状态与历史 last_confirmed；失败或 unknown 不覆盖旧确认，也不声称新成功。
- `proxy_highest` 按 exact key/direction 分组，只计 status=ok 且有限 metric；并列保留 IDs。未知 key 的候选单列，不从版本字符串、label 或推荐猜 key。
- `target_best=null` 固定保留，附“目标适用性与权重由科学作者判断”；不为获得不同选择而编造 reward。
- 输出包含 coverage、公开审计状态及明确 omitted_count。默认最多 8 组、每组 4 个并列 ID、16 个审计/未知 ID；最终 JSON（indent=2、UTF-8、尾换行）不超过 4096 B，超限按确定顺序缩短可选预览，计入遗漏。原件/完整候选继续由 T2 现有分页读，不加第二分页引擎。
- 纯函数可由封存事实重建，restart 不产生新事实、不重复观察或执行。

## 4. 隐藏数据与集成

- 白名单投影及严格纯函数输入拒绝显式 `hidden*`、`reward`、`test_score` 等非公开评分字段；不声称能识别改名藏入 metric 或自由文本的秘密数据。可信 observer/config 仍承担公开输入隔离责任。
- 夹具全为合成数据，不取 N5/live02 隐藏池数值，不据已窥见评分池制定新科学规则。
- T4 最小集成只替换单 brief 内候选概览，不追加另一份 4096 B 包；分页原件与关系投影仍由 T2 管理。
- `selection_protocol=1` 为独立冻结的 settings/newjob host 开关，由 contracts/controller 作者接线；lineage.bind 显式 kw 默认 0。retained job 缺字段按 0，不从当前 settings 偷换；旧 T2 marker 1 的原 renderer 字节保持。不升科学协议 8，不新增 required 科学字段。
- 本节点不改预算、repair、停滞、执行恢复或交付状态机。
- 集成沿用可选投影的 bounded unavailable 口径：概览输入/容量不适用只停用概览，不阻断已完成科学封存，不猜补值；显式 hidden 输入不发布到概览。源原件、权限或冻结身份失配仍在原消费边界硬拒，不能被该降级吞掉。

## 5. 冻结夹具与门禁

公开夹具：[rootless-selection-v1.json](fixtures/rootless-selection-v1.json)。八类：未知目标权重的排名反转、未知/不同评估版本、缺审计高分、proxy/A/actual 分离、latest A null、partial、unknown submit 保旧确认、显式 hidden 拒绝。

新增 `selection.py/test_selection.py`：纯投影、输入不可变、同 ID 冲突、有限值、并列、UTF-8 4096 B 最坏大小。父代理执行最小 pytest；本作者不跑测试/构建/模型。最终安装验收须证明实际 A 的单 brief 接线及旧输入兼容，纯函数通过不代替集成。

退出：设计独审、上述合成门禁、T2 后最小接线及源码/installed 字节绑定都完成才称 T4 完成；科学选择效果与 T5 真实验收另计。粗规模：纯模块 120–200 行、专属测试约 150 行、renderer 接缝约 10–20 行；不加 catalog 或执行引擎。
