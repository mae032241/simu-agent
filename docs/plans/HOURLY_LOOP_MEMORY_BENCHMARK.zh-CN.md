# P6s：小时级多轮记忆验收任务

定位（2026-10-03）：本原合成题降为分批释放／原件／轮换／等待／记忆与预算 cleanup 的机制回归，不再是主要科学效果题；真实效果主测首选原版 LHTB N-body、第二题 covshift，选题、原资源声明与运行缺口由[主计划](SCIENTIFIC_PROGRESS_AND_CORRECTION_PLAN.zh-CN.md#真实效果题与机制回归分工)拥有。此定位调整独立复审通过；不改题库、配置、预算、实现或历史资格。

状态：题目、数据与评分草案已构造，准备边界独立复核通过；`41c3bb4` core 离线安装及仅初始材料的无模型 `init`／`prepare` 实物证据独立复核通过。分批接线源码与有限无模型回归已有证据；增量补验 failed-Run 停止、原子消息 scope 与真实 project 路径拒绝均通过，独立增量复审通过（源码接线资格，纳入本提交节点，未部署）；新源码尚未安装／重冻场次，隔离与完整预算仍 pending，未运行本场。独立增量复审见 `/tmp/scid-p6s-delivery-review-20261003-v2.md`，限定源码与有限无模型回归。本文供验收执行者与评分者使用，不交给被测 Root/Worker。S3-R 的规则见[设计](LONG_LOOP_CONTROL_AND_MEMORY_DESIGN.zh-CN.md)，排期与候选资格矩阵见[主计划](SCIENTIFIC_PROGRESS_AND_CORRECTION_PLAN.zh-CN.md)。

## 规模与目标

单条串行研究链，预计 4–6 个完整研究任务，预计 2 小时、墙钟硬上限草案 3 小时；研究任务最多 8 个，精确审查另最多 2 个（可选，不强制使用），Root 回合最多 20。总输入+输出上限草案 400 万 token，非缓存输入+输出 40 万；所有失败、恢复、helper 和收尾计入。由近期实测校准并在启动前冻结，不自动增加；本文件不构成运行授权，不挪用 S0/P5 的额度。

这场只验证小时级多轮衔接与换线程后的经验利用，不声称跨天可靠性。任务少于预计但完成本合成题目标可通过其局部科学项，不构成主要科学效果证据；实际多轮／轮换／等待／记忆行为未发生即保留未验证，不人为拆完整任务凑次数。只用合成小数据与确定性计算，无 TCAD、安装压力或大文件。Root 使用 gpt-5.6-sol/high；Worker/helper 使用冻结配置，资源监督复用现有入口。

2026-10-04 B1／B2／B5 源码修复与有限无模型检查完成，独立审查通过（仅合成 bench 源码边界，纳入本提交节点，未部署）：opening／鉴别批次公开本 bench 的预测及最终 adoption 交付协议；从 completed 报告的 `adopted_stages` 选取本预测任务自产的唯一确切声明，允许同 Run 预览 A→B、最终仅采用 B，释放时固定声明＋报告，后续合法 final 不替换也不阻断此前声明的比较。未完成、未采用、合法不匹配与无替代语义的多个 final 保留具体 waiting；相关原件读取覆盖不足不授“唯一”资格，原件／receipt／namespace／scope 矛盾仍拒绝。25 个 focused owning 与 4 个合同邻接节点通过，证据 `/tmp/scid-p6s-adoption-20261004-implementation.md`；B3 durable 完成轮换证明仍待独立修复，旧安装／场次不改写。既有源码复审与本轮模拟证据不授自然模型路径活性资格。原版 LHTB 不依赖这些 A/B 钩子，也不强迫本题的 `science.experiment.v1`／可选 declaration／DAG；实际读隔离与候选／反馈／预算冻结仍按主计划覆盖相应真实运行范围。换题或原题高分不关闭本场待测机制。

## 材料与投递

数据在 [materials.json](../../scripts/acceptance/fixtures/hourly_loop_memory/materials.json)，包含完整题目与四批数据。该文件是题库资料，不是现有 accept_b6 配置；不得把它直接当运行命令输入。后续复用已有验收 runner 接入分批投递、轮换和记录，不另造常驻运行器。

执行者把 objective 和当前已释放批次分别通过已有材料入口交付。完整题库、评分答案和未来批次置于被测 Agent 不可访问的位置，不能仅靠提示词隐藏同 UID 下可读文件。若运行环境无法隔离题库，提前知晓检查记受污染，不计独立预测/记忆效果资格。

| 批次 | 释放条件（同时满足，默认草案，运行前冻结） | 可改变的决策 |
|---|---|---|
| A_initial | 开始时 | 三个采样点能否区分机制，继续精修是否增加信息 |
| A_discrimination | 启动至少 25 分钟且首轮结果已封存 | 同工况新增点能否排除机制；封存 x=4 预测及判据 |
| A_validation | 启动至少 55 分钟且预测已封存 | 使用预留观测检验预测、保留适用范围 |
| B_changed_condition | 启动至少 85 分钟，A 验证已封存且一次 Root 安全轮换完成 | 新 Root 回读早期经验；工况变化是否允许重新检验此前排除的机制 |

时间由验收驱动配置并安排投递，模拟观测延迟，不伪装成真实求解器耗时。等待阶段无新事件不启动模型轮次。条件未满足时不偷看答案或补写预测；达到运行上限安全收尾并记录缺项。换线程在旧回合/Worker 已终止且没有未知提交的边界进行；不把旧线程原文或本答案注入新线程。

工况 B 投递后，在同一份用户消息中追加一个中性的决策问题：“请依据此前封存记录说明，是否值得再提高原三个采样点上的参数拟合精度；并判断工况变化后应重新检验哪些结论。”此问题只触发读取/决策，不要求实际做无效精修。这样把“避免重复弯路”和“条件变化后允许合理重试”都变成可观测行为，不仅看摘要是否出现过。

## 运行前准备边界

此前安装准备记录固定 source candidate 为 `41c3bb45cf789ca0e6ae671d72e77e61cbf0fd09`，不是后续文档 HEAD；installed 实物与资格／旧 unknown 限制由主计划维护。该轮只冻结 initial 配置与场次，未改 runner／授权模型预算，实际命令、哈希、资源及读回见 `/tmp/scid-candidate-install-20261003-implementation-v2.md`（静态复审纠正资源冻结元数据，未重跑），实物证据独立复核通过。本轮新增接线不改写该 candidate／source／case，也不赋予其新 schema 支持。

| 现成入口 | 可复用范围与未满足条件 |
|---|---|
| [accept_b6.py](../../scripts/accept_b6.py) `init`／`prepare` | 已从本候选实际 installed 读回 schema 9／配置 API；独立 source 与 `/tmp/scid-candidate-install-20261003-p6s-suite/p6s-inputs` 已冻结。复制后 instance／session／progression／dispatch／Run／execution 均为 0，只含 objective＋A_initial；未创建／选择／绑定实例或启动 host／模型。空 state 不算 P5 同历史资格，不沿用旧 P1b 安装通过 |
| 场次配置 | 原字段／场景不变；源码新增仅限 native／autonomous、`multi_task=true` 的可选 `batch_delivery={version:1,materials_file:绝对host路径,materials_sha256:文件SHA256}`，本 bench 明确采用 `science.experiment.v1`，不扩展通用科学 producer 判定。spec 纳入已有 case／conditions 指纹；题库文件不直接当 runner 配置。prepare 只把 objective＋A_initial 公共投影放入 opening text，材料文件须位于 source／target 的 candidate.json 实际 project 规范路径外（包括 build/core-workdir），prepare intent／clone 前拒绝项目内材料，并沿既有候选内路径与 symlink 约束检查；不是只检查名为 project 的目录 |
| 预算与报告 | initial case 已冻结 `progression.max_tasks=8`、`max_reviews=2`、`max_rounds=20`、总 token 400 万，自然期限／启用时长与 `resources.timeout_seconds` 均为 10800 秒；只是提议，未授权。可选 `budget` 尚未配置：40 万非缓存、suite／人工审查预留未冻结，不声称完整预算／`run` 就绪，不继承 S0/P5 额度。installed 原始 Worker 默认 `gpt-6-astra/high` 保留；派生 source／case 按正式 AgentSettings 实际读回 `gpt-6.1-sol/high`，Root `gpt-5.6-sol/high`，无 operation override，不继承开发 xhigh；helper 沿冻结设置，未执行 |
| 时限作用 | `resources.timeout_seconds=10800` 在 prepare 中生成 host execution timeout；自然期限／启用时长另有同值提议，未实跑。`managed.runtime_seconds=180` 属 managed runner，本 native/autonomous 场次不用；`stage_timeout_seconds=90` 是 cleanup 等待 writer 释放及 authority 等待窗口；`human_wait_seconds=900` 是实例选择／人工等待窗口，prepare 写入 host resources。各自独立，不等于全停止链 3 小时，不机械扩大清理／人工窗口 |
| 分批释放与证据 | [NativeCaseJourney.run_case](../../scripts/acceptance_native_cases.py) 在原 poll／预算／cleanup 链接入三次后续 `progression_message`：同单调开场时间的 25／55／85 分钟下限，以及确切 goal／loop 的 completed 实验报告、封存预测／判据、最终采用的比较和实际轮换边界。`checkpoint.messages` 是唯一 saved ack；runner 使用公开 `expected_scope={objective_name,loop_id}`，控制解析不可改绑的确切目标原件，在既有 maintenance＋scheduling 锁内、旧 ack／intake／bind 前核 exact goal／loop、active/background、未 completed／unknown 和现有总预算事实。可选 review／helper 额度归零不单独判整个 loop 关闭；普通无 guard 消息仍可保存到 paused goal，不恢复或授权。lost reply 只读核对原件，unknown 不重放。接线与模拟事件回归独立增量复审通过（源码接线资格，纳入本提交节点，未部署），真实消息消费与轮换未验证 |
| 评分材料隔离 | [RootPermissions](../../src/scidiscovery/platforms/codex_root_host.py) 及现有有效设置仅有 `never`、`read-only/workspace-write`、network 和写范围校验，未接线题库目录 read-deny／read-scope；[Host.launch](../../scripts/probe_root_host_live.py) 同 UID 直接启动子进程。不能据此声称平台绝对无法隔离，但现准备没有可审计读隔离。运行环境须证明 Root、Worker、helper 及原生工具不能读取完整题库、答案、未来批次或控制日志中的相同内容；只交付当时允许的 objective／当前批次，保留 Worker 声明权限。未证明则记污染／未验证，不给独立预测与记忆资格 |

可选科学字段由[完整实验工具](../../src/scidiscovery/general_science_experiment_task.py)拥有：design 的 `prediction_declaration` 明示 PredictionTest／ValidationCheck／条件别名，validity 的 `comparison` 明示确切声明／观测别名／ValidationCheckResult。每个结构绑定原件最多 65536 bytes；普通 `materials` 不收紧。handler 实读并冻结引用，跨任务声明的唯一原 receipt／原 namespace 在最终 adoption 验证，输入不会因可读而继承当前 stage 或科学资格。本 bench 的 opening／鉴别批次要求在未投递观测前对工况 A 的 x=4 封存预测及判据，并由本预测任务的 completed 报告最终采用唯一声明；合法 `outcome=inconclusive` 可以交付预测子任务，不等待未来 comparison、不声称科学完成或 verified progress。running prediction／comparison、未采用比较和 `not_run` 不触发相应释放。bench 对报告／stage 的有界读取为 65536 bytes；无法读全的相关 adopted 原件可能隐藏其他候选，选择保持 unknown，不以其余候选冒充唯一。无关非 stage 大材料只在唯一原 receipt 的 role／namespace 已独立核验后排除，未读 body 不获科学资格。释放依据的 exact 声明＋report 仅作为同进程观察固定；saved ack 无法重建因果时 post-model restart 仍 unsupported／unknown，不按最新报告猜选。负结果可继续，本题 x=4／工况及科学正确性仍按冻结 rubric 评定，结构通过不计 P6s 科学通过；普通完整任务不新增 gate。

安全轮换须实际观察既有 `prepare_host_rotation` 写入的旧 writer terminal／撤权边界及随后 `complete_host_rotation` 建立的新实际身份，保留 exact goal／loop。错过 prepared 采样、缺原件／receipt、覆盖限额或多个不同预承诺均 unknown，不用 generation／最近 schema 猜。至多三条外部释放 proof 观察保留在现 evidence；它们不是投递权威或恢复账本。early complete／预算 cleanup 记录 saved 与 omitted，report 将 saved complete 与 `science_status=not_observed` 分开。现 runner 仍只支持原 pre-model `resume_wait`，不声称 post-model 宿主重启恢复。源码证据见 `/tmp/scid-p6s-delivery-implementation-20261003.md`，真实模型／native／TCAD 均未运行；需独立复审后另冻新候选／场次，不能直接复用旧 installed 获得此能力。

已有 CLI 的形式如下，尖括号是通用参数占位，**不是可执行交接命令**。本轮已按实际输入执行 `init`／`prepare`；题库隔离与新科学预算仍 pending，二者不是无模型准备前置。未执行 `run`，初始准备不等于运行就绪：

```text
python scripts/accept_b6.py init --suite <新套件目录> --config <冻结场次配置> --source <静止state候选> --installed <本源码实际安装候选>
python scripts/accept_b6.py prepare <已配置case-id> --suite <套件目录>
python scripts/accept_b6.py run <已配置case-id> --suite <套件目录>
python scripts/accept_b6.py report --suite <套件目录>
```

`init` 要求 source 的 schema 9、`scheduler_progression` 无行，且没有非 `completed`／`failed` Run；允许保留合法终态历史。已有 progression 记录不合入口时记录准备缺口并选择／构造合法来源，不删除合法 control／既有消耗记录。`prepare` 冻结 `suite.json` 的 `freeze_identity`、`baseline_digest`／`conditions_digest` 及 `acceptance-case.json` 的有效设置、candidate／settings 摘要。`run` 才启动 native host，并输出精确管理 URL；只有用户页面选择／创建确切实例、暂停 bootstrap、确认本场 loop 预算后才请求模型。预算确认不解除具体行动合同声明的科学资格、暂停条件或 Effect 执行授权；普通任务／阶段不新增统一审批或独立审查 gate，配置执行策略可按具体合同直接授权适用请求。普通继续／恢复不续额；本轮未执行 `run` 或这些 UI／模型动作。后续新 suite 如需结转前场成本，`init --prior-result <确切终态result.json>` 可重复指定，只结转成本，不继承科学结论。

P5 可按已有场次分别封存报告，由用户按冻结 rubric 人工比较 baseline／candidate，不必增加自动汇总；现 `report` 的 `pair` 比较只实现 manual／auto，不能把 baseline／candidate 标签塞入该结构冒充支持。P5 的三场景／原件、两组 installed 条件与资源单独冻结，不把本 P6s 题库当成已准备的六场 P5。

## 科学参考答案（不交给被测 Agent）

1. A_initial：在 x=0,1,2 上扰动项恒为零，c 不可辨识。提高同点计算精度无法消除这一结构缺口；应寻求点外观测。误差不为零，因此不能宣称 a、b 已知到任意精度。
2. A_discrimination：L 无法同时落在全部误差区间。由 x=0 与 x=2 得 y(3)=1.5*y(2)-0.5*y(0)，允许区间为 [6.90,7.10]，与新增观测 [7.95,8.05] 不交。Q 存在可行解 a=2,b=1,c=1/6。
3. A_validation：该可行解预测 y(4)=13，与预留观测相容。考虑初始三条约束及 y(3) 误差，由 y(4)=4*y(3)-4*y(2)+y(0)，Q 的可行预测区间为 [12.55,13.45]；可接受正确的更保守范围和明确的不确定性解释，不要求唯一拟合参数。观测相容支持本次预测，不证明 Q 是唯一真实机制；采用该点重新调参后不能继承独立验证声明。
4. B_changed_condition：L 的 a=2,b=1 可行，Q 的 c=0 同样可行，不能证明唯一机制。工况 A 的 L 排除结论不能无条件迁到 B；但原三个点不辨识 c 的采样结构事实仍适用。允许有依据地重新检验 L，不能把它写成无条件“重复失败”。

任务划分由 Root 根据到达材料决定，建议路径只是“初始判断 → 新证据与预测 → 验证 → 新工况再判断”，不是强制 Operation DAG。独立审查由任务需要决定，不人为消耗审查额度凑覆盖。

## 评分与证据

以下 S1–S4 仅评价原合成题，LHTB 沿自身原版评分，不能互授资格。用户按事先冻结标准评分。科学四项与运行四项分别给通过/失败/未验证，不合成一个掩盖缺口的总分：

| 项目 | 最小证据 |
|---|---|
| 科学 S1–S4 | 四批分别达到上述结论，保留误差、不可辨识和工况边界；错误结论记失败 |
| 运行 R1 多轮衔接 | 实际多轮任务消费、分批投递与预留预测顺序；未释放数据未出现在 Agent 上下文 |
| 运行 R2 等待恢复 | 至少一个真实观测等待区间，无变化时模型回合不增长；投递后恢复，等待不被视作科学失败 |
| 运行 R3 安全轮换 | 旧 writer 已终止，新线程接续同一 loop；原预算、usage、待读结果保留，无双调度或重复提交 |
| 运行 R4 记忆用于决策 | 轮换后找到本场早期封存结论及确切引用，说明同点精修无效、工况变化可重检，不重复派发已知无效工作 |

同时记录完整研究/审查/helper 数量、各角色 token、缓存/非缓存、启动及工具正文大小、轮换开销、峰值内存和人工介入。代码级刹车触发仍用确定性夹具；本题不诱导模型烧预算强行触发。P6s 全项通过才进入 P6a 跨天验收；单场不证明普遍成本收益。失败保留，不自动重跑。
