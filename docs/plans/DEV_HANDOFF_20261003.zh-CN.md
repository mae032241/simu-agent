# dev 模型切换交接 — 2026-10-03

> 历史快照，2026-10-10 归档核对：本文的 HEAD、停止指令、未提交清单和执行偏好仅描述 2026-10-03，不是当前调度授权。当前实施入口为[HWA 修订计划](RELIABLE_HWA_SEARCH_IMPLEMENTATION_PLAN.zh-CN.md)。保留当时正文供追溯；不得据此恢复旧测试或覆盖新配置。

## 1. 接手先读

这是截至 `308f16f` 的开发状态快照，不是新的实施计划。用户当前只要求写 handoff 以切换模型；本次交接不启动实现、模型测试或部署。

- 工作目录：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`
- 分支：`dev`。目录仍叫 `scidiscovery-e5.2`，不要因此切换旧分支。
- HEAD：`308f16f410b945743c8851763908352660f3aee5`。
- 本轮三个修复节点已本地提交、独立复审通过；**未推送、未部署、未运行真实模型或 TCAD**。
- 现状：P2 源码已收口；P3/P4 初版及本轮指定范围追加修复完成。真实效果、安装态原生轮换及长跑资格没有因此完成。

权威文档只保留两个入口：

1. [主计划与状态](SCIENTIFIC_PROGRESS_AND_CORRECTION_PLAN.zh-CN.md)：节点、待办、验收状态。
2. [长循环控制与记忆设计](LONG_LOOP_CONTROL_AND_MEMORY_DESIGN.zh-CN.md)：loop 预算、记忆、轮换、刹车及 P5/P6 规则。

接手先核对 `git status --short` 和最近提交。交接时已有以下非本轮改动，**没有纳入三个提交，不要还原、清理或顺手提交**：

- 修改中的 `CONTRIBUTING.md`。
- 未跟踪的 `docs/plans/evidence/`。

本交接文件本身新建、尚未提交；不改变上述 HEAD。

## 2. 用户的持续约束

- 开发在 dev；每个实施节点使用独立执行者，再独立审查，通过后提交 git 节点。按用户要求**串行**，不能并行子任务或测试，历史上多次 OOM。
- 开发执行者使用 `gpt-6.1-sol`，思考等级 `xhigh` 足够，不自动升到 ultra。框架内科研 Root 默认 `gpt-5.6-sol/high`，科研 Worker 使用 `gpt-6.1-sol`；真实验收应沿冻结 profile，不擅改条件。
- 禁止无范围递归 `rg`。先用 `git ls-files` 定位，再查确切文件；不要扫描所有历史验收目录、日志或 `/proc`。
- 当前修复使用受限源码验证。不得把本轮通过当作安装、native、模型、TCAD 或科研效果资格。新一组 P5/P6 真实运行须按计划确认预算，不挪用耗尽的 S0 额度。
- 用户允许破坏性升级，不做旧格式兼容。当前 **state v5** 拒绝旧 state root 和旧格式归档；保留旧证据，不能原地改写旧数据来伪造升级成功。
- Agent 只填有价值的科学字段；字段合同必须完整可见。身份、端口、绑定、游标、预算归属由控制层填，不给 Agent 新增机械表单或低价值 gate。
- 保留自动强制刹车；科学暂停只阻止新的研究派发，不能卡住已接受工作、精确审查依赖、取消、收集等必要路径。
- 科学 Worker 负责结论，Root 判断不等于科学验证；历史摘要不算原件消费、审查通过或执行授权。
- 本轮无需绑定科研实例。将来做实例验收时，只有用户管理页能选择/创建实例；不能替用户绑定、接管或授额。

源码测试入口（确切目标、共享串行锁、不得绕锁）：

```bash
cd /home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2
/home/da/miniconda3/bin/python scripts/run_tests.py \
  --lane source --per-file --output /tmp/<本次唯一目录> \
  <确切测试文件或节点>
```

本轮沿 runner 默认 2GB 地址空间、1.5GB RSS、超时和提前止损。过去某次真实验收的 13GB 特批不等于本轮默认；不要直接裸跑全套 pytest、安装或构建。

## 3. 三个已提交修复节点

| 节点 | 提交 | 内容 | 末版定向验证 |
|---|---|---|---|
| R1 | `f259a9ab29d5ab7c7da237af813935134c981392` | 排除启动前背景任务；阻止阈值微调反复获得首解；可选证明缺失/歧义返回 unknown | 51 项通过 |
| R2 | `c6d8c545f319e6e4fe6e099736bfe843581af341` | 新 Root 恢复用户指示/审批导航；有界原生核查；修通知竞争与跨连接旧缓存误信 | 48 项通过，RSS 192364544 B |
| R3 | `308f16f410b945743c8851763908352660f3aee5` | 审查中性记忆；明确目标修订谱系；科学内容摘录；坏内容局部降级 | 35 项通过，RSS 151101440 B |

这些是各节点的定向分组，不是全套或独立科研样本，不要合计后声称覆盖全仓。

### R1：背景与进展证据

- 首次探索按既有终态事件序号冻结背景上界，不依赖简报最多 16 条的展示范围；已观察/已准入任务不能跨目标重新归类为背景。
- 首解家族排除 cutoff 阈值，保留实际指标、执行配置和结构化条件。核验仍用确切冻结阈值；改变真正条件可构成新家族，不声称能判定语义等价。
- 背景家族读取有界；覆盖不足或坏证明保留 unknown，不制造新颖性。`family_omitted` 必须持久保留，后续有限重读不能把不完整恢复成完整。
- 可选计算回执、attempt、plan 缺失或歧义不再通过 `next` 等路径中断读取；不宽泛吞掉数据库异常。

### R2：上下文恢复与原生安全轮换

- 按实际 Root 线程记录上下文确认投递。新线程重新获得当前目标已保存的用户指示；长原文通过 `progression_status` 名称索引和 `artifact_catalog(view=content)` 的真实分页读回。
- 当前目标用户消息沿既有硬上限 16 条，超额明确拒绝；不声称跨目标的用户消息全部自动继承。
- 审批补读 `approval_list` 的 pending 和近期决定，保留分页、`approval_status` 和 review URL；重送文本不产生授权。
- 小简报在能完整保留结果/消息时先降级可选 shadow 摘要，不放宽总预算，不把省略结果算作已消费。
- 原生终态证明绑定真实 session/thread/Run/附着代次、宿主连接代次、事件版本和订阅依据。最终切换前在调度锁内按全部当下确切绑定重新核对。
- 已修两条竞态：检查 B 时 A 收到 `turn/started`；B 的迟到终态响应覆盖期间新回合通知。两者都应延后轮换。
- `thread/read` 不订阅事件；仅为本连接新绑定或仍活跃的确切参与者复用无权限覆盖的 `thread/resume` 订阅，不发新 turn。resume/read RPC 合计受冻结批量限制。
- **冷启动限制**：新连接不信任旧 proof，也不为大量旧终态线程批量 resume；旧历史未订阅时可持续延后轮换。不能把 1501 条“同连接已有可信订阅缓存”的零 RPC 夹具写成冷启动资格。

### R3：记忆语义和边界

- 用 compiled `independent_review_ports` 识别审查合同，不靠 Operation 名称。启动和 `worker_read_history` 均使用中性导航，不自动附加作者摘要/verdict、Root 判断或科学摘录；必要的确切被审原件仍正常可读。这不是声称盲审。
- 只沿明确 `supersedes_ref` 冻结同实例有确切绑定的目标祖先，不按名字、schema 或共同 parents 猜谱系。Root/Worker 共享冻结范围；旧 scope 不追补祖先，新结果不混入旧页。
- 祖先数量受现有 2048 字符加密游标容量限制，超出要显示覆盖不足和入口。历史 Root 判断按该任务实际准入目标读取，不套用当前目标的判断键。
- 从完整的既有科学 decision 字段摘录认识/矛盾；明确 hypothesis `contradicts` 标成 Worker 科学负结果，非受控核验。工程失败和通用 blocked/revise 不能替代科学否定。
- L0 只核查最多两个最早 typed diagnosis 候选，不扫描 300 份报告，不声称找全重要负结果。超预算字段整项省略，不截断科学结论。
- 单条可选正文、Root 判断引用或历史输入索引损坏局部标 unknown，健康条目可读。SQL `CASE` 保护非法 JSON、非数组和非对象元素；没有捕获所有 SQL/锁错误。
- **确切 Run/绑定/范围授权损坏仍是整个范围的完整性保护**，不能声称任意坏记录都可局部容错。当前有效任务可携带明确 unknown 记忆继续，原件读取权限不放宽。
- 30/100/300 夹具中启动材料 10280 B、记忆 4520 B，Worker 页最大 5820 B；薄索引仍零正文读取，公共页为科学摘录最多读取 7 份正文。旧“公共页零正文”的断言已据此更正。

## 4. 证据入口与独立复审

原始记录仍在 `/tmp`，切换模型不会自动归档它们。需要持久化时只处理这些确切路径，不要重新全盘搜索。冻结清单写于提交前，里面的“未提交”状态属于当时事实；现在的提交状态以第 3 节和 git 为准。

| 清单 | SHA256 |
|---|---|
| `/tmp/scid-r1-freeze-v2-20261003.json` | `bbf84ef28e856b836771db9dcc2894a0e15257c8516d55eb586c819e37383363` |
| `/tmp/scid-r2-freeze-v2-20261003.json` | `ccf063a3c5f4fc560f08a5c5932819fd09c49c31bce905d60d53c88e867c46f7` |
| `/tmp/scid-r3-freeze-v2-20261003.json` | `94bba2862ee9408ab4fdcc7c3754e44bd4cc6477107b3e6befe885a2f5aed9d6` |

清单含精确文件 SHA、测试日志、红绿时序与限制。三个清单结构不完全相同：R1/R2 用 `owned_files`，R3 用 `owned`；读取前检查键，不写假定统一格式的脚本。R1/R2 清单文件 SHA 对应各自历史提交，不能要求随后被 R3 修改的文件还等于旧 SHA。

- R2 末版结果：`/tmp/scid-r2-v2-final-owning-neighbors-20261003/result.json`。
- R3 末版结果目录：`/tmp/scid-r3-v2-final-owning-interfaces-20261003`，日志实数 `23+9+1+1+1=35`。
- **R3 v1 计数纠错**：原报 31，实际是 30；v1 未改写，v2 已明记更正。不要再次引用 31，也不要将各次重跑累加。
- 独立评审不是只看提交说明：R1 修过背景覆盖截断后误恢复完整；R2 修过通知竞争和跨连接缓存；R3 修过判断引用与 SQL 输入展开两条漏掉的降级路径。最终增量复审均已通过。

可复用会话内角色（切换后若仍存在）：执行者 `/root/p3_minimal_memory`，独立审查者 `/root/p1b_entry_independent_review`，均已停工完成。列表另有 `/root/p1c2b_bounded_capacity` 为 pending_init；不代表它在工作，不要无故唤醒。此前工具只支持 interrupt，不支持真正释放/关闭槽位，不能声称槽位已全部删除。

## 5. 剩余项和下一步

**本轮只关闭上面指定范围，不能写成整个 P3/P4、长跑或科研能力已全面验收。**

1. **冷启动轮换可用性**：旧终态线程未订阅会保守延后。先查可用原生协议与实际订阅边界，再确定低成本接续方案；不要用“批量 resume 所有历史”解决，存在 OOM 和权限风险。
2. **判据先后依赖封存墙钟**：`verified_progress.py` 仍比较 `created_at`；时钟回拨风险未关闭。需要核对现有可信来源/顺序事实，不能直接删除“先验判据”检查，也不能默认导入顺序等于实验发生顺序。
3. **两套计数仍并存**：逐目标过程观察与实例探索窗口尚未完全收敛。先列真实触发/清零/人工开窗规则，再围绕同一事实来源精简，保留强制刹车及已接受工作放行边界。
4. **偶发测试失败**：前节点有未确认根因的失败，原始轨迹在各冻结清单；后来的通过或夹具修正不能证明生产缺陷已解决。下一模型应先从对应失败证据定位，避免为求全绿扩大重跑。
5. **TCAD 科学进展能力仍有限**：未声明受控科学判据时，默认阈值 3 实际是方向确认检查点。不能宣传为自动识别停滞或百任务无人值守，也不能只提高阈值就声称解决。
6. **效果与长跑验收待做**：按主计划处理发布边界、确认预算后进入 P5 对照和 P6s 小时级多轮任务；通过后才考虑 P6a 的 30 任务/24 小时、P6b 的 100–300 任务/3–7 天。小时级方案在 [P6s 任务文档](HOURLY_LOOP_MEMORY_BENCHMARK.zh-CN.md)。不要直接启动一周测试。

建议接续动作：核对 HEAD/工作树 → 读取上述两份计划的当前状态与未关闭边界 → 给剩余项安排小节点 → 按用户既定方式串行执行、独立复审、提交。已有源码证据足够的路径不要先重跑整套验收。

## 6. 后续定位用确切文件

- 背景与计数：`src/scidiscovery/artifact_agent/service/scientific_progress.py`、`verified_progress.py`。
- 轮换、简报、通知：同目录 `progression.py`、`progression_budget.py`、`scheduling_control.py`；`src/scidiscovery/platforms/codex_progression.py`。
- 历史范围及科学摘录：同 service 目录 `runs.py` 的 `attempt_history_*`、`attempt_memory.py`。
- Worker 与 Root 入口：`src/scidiscovery/artifact_agent/interfaces/` 下的 `mcp_local_worker.py`、`mcp_root_run_routes.py`、`mcp_root.py`；`src/scidiscovery/artifact_agent/service/worker_start.py`、`src/scidiscovery/operations/lifecycle.py`。
- 最直接测试：`tests/operations/test_verified_progress.py`、`test_progression_rotation.py`、`test_progression_delivery.py`、`test_attempt_memory.py`、`test_attempt_history.py`。

本 handoff 仅做路径、git 状态、证据清单 SHA 与文档格式核对；没有重新执行上述测试。
