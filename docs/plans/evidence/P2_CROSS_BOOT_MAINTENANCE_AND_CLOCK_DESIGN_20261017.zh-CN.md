# P2 跨boot原调用维护与暂停checkpoint续钟：最小设计

状态：root方向批准、独立设计审查通过；已实施，动态未执行。基线 `29a7f69`；非真实solver验收，禁止作者测试/项目import/安装/模型/Git。P3与P4由其他作者并行；不改其源码。

## 已确认的功能缺口

同boot控制器重启已有等待/原call/唤醒路径及 `test_managed_execution_wait.py:156` 的真实CLI重启检查，应复用。当前跨boot收集却被 `execution_authority._gate` 的旧allocation.boot比较明确拒绝；`execution_resume._RecoveryAdmission` 在维护分支前调用budget.snapshot，也会被 `budget._duration` 的boot不符拒绝。它是代码缺失，不能以“尚未验真实solver”代替。

原许可query/cancel/retire并不等于新submit；无需一律重新审批。来源/资格、权限或原件不明仍拒绝，lookup None不制造未提交事实。

## A. 原accepted有限维护

公共入口复用 `execution-resume`，新增 `--maintenance query|collect|cancel`；保原root/step/call-id、有限max-seconds、操作者authorization-note。与request-valid-seconds互斥；不续请求/审批、不走任何unprepared/fresh prepare/submit分支。缺原accepted即unknown/unsupported。

trim持CLI/controller：maintenance分支仅原writer/owner lease调用 `execution_resume.maintain(...)`，不进入普通resume的budget.inactive/_inactive_on_error科学时钟写入。无该选项原语义保持。

本作者持execution_resume/execution_authority：

- 在原scope/attempt/frozen config/interface、accepted/prepared/script/target/原permit HMAC与external ID下建立当前boot的单个有限CollectionContext；操作intent/outcome落原call目录。绑定准确action，不以当前余额、原W是否结束或审批TTL决定维护可用性。
- 经现非JSON HostServices给原registered factory注入同一operation_context；复用 `_gate(..., recovery=maintenance)` 的原permit收集分支，collection再裁原runner policy限额。query/cancel仍只操作原job。实际RPC/新复制使用同一绝对deadline，不在retry重发时间。
- 维护service禁止call_identity/prepare/submit；不提供compiler/新输入解析器，不创建accepted。复用共同record_observation/verify_observation保完整原件；不改旧科学seal/history snapshot。
- 维护不append新grant/额外release或重签决定；既有预算owner仍可对精确终态按实际消耗合法settle，不能以维护窗口重置额度。永久未提交retire保原入口，本节点不新增跨boot退役或退款能力；跨boot尚未续钟时可选资源结算若无法append，保原reservation与诊断，不能丢已核terminal原件。后续仍由原budget owner消费，不能以维护窗口变科学秒数。

## B. 仅paused冷checkpoint科学续钟

trim持instance_owner/instance_archive等唯一owner：实例外同宿主anchor、原绝对root、新generation、原写者已静止、无unknown外部call；旧只读包不追认。预算不解析第二套anchor。

约定现owner API：`read_transition(root, checkpoint_ref, transfer_ref)`只核immutable receipt关系；`verify_transition(...)`再核首次恢复当前anchor/transaction/generation/root inode。预算首次reanchor必须用后者；已发表历史ledger只用前者，不能因第二次恢复使第一次历史失效。

预算只增加两函数：

1. `paused_checkpoint(root)`：在owner已独占下纯读原_events，要求active basis且最后clock phase为paused（无clock默认paused）；返回 `{version:1,basis:'active',phase:'paused',head:<seq及精确event ref或null>,started:<原host-started ref或null>}`。不存新余额；不改host-started。grant/reservation仍唯一来自原ledger。
2. `reanchor_paused_checkpoint(root, checkpoint_ref, transfer_ref)`：在原owner/ledger锁内，先核verify_transition及checkpoint.budget与当前原head/start/phase完全相同。若同boot不追加；新boot仅追加一个原ledger `kind=clock,phase=paused,reanchor={version,checkpoint,transfer}` 原件。新事件前head与原checkpoint一致，根内receipt不提供独立余额。重复同transition幂等，不覆盖原事件。

_events和snapshot只对这类已核paused桥分段；不放宽_duration通用跨boot拒绝。历史advance/waiting累计照原事件保留，新段从reanchor当前boottime计，不减消费；budget_amend/resource_grant/reserve/bind/actual/release全部原样fold、revision不由新clock事件重置。waiting/advance、旧elapsed basis、无可信checkpoint/过期head/缺owner不能续钟。无host-started且无ledger时无需桥，首次真实run仍自行记录原起点。

跨boot暂停间隔无法按boottime测量，snapshot明确unmeasured_paused_gap，elapsed_seconds可为null；paused_seconds仅含可测片段。不能显示为已测0秒。max_tokens/max_seconds、consumed_seconds、seconds_remaining仍原类型与原规则；不通过重写host-started或增加grant弥补未知区间。只有active实例且跨bootpaused桥才改变该展示；无桥旧返回形状/语义保持。

## 文件与最小负控

本作者：`research_loop/{budget,execution_resume,execution_authority}.py`及最小新测试/证据。authority.writer加同instance_owner.lease贯穿yield，implementation自动纳owner模块；实际RPC之外层effect lease由对应experiments owner/trim接入，不在本作者重改其共享文件。trim一次接CLI/controller参数；P3的history/formal/source改动不混入。

- 原accepted跨boot/科学余额耗尽仍可在当前有限窗口query/collect，原call/external/permit不变，submit/prepare哨兵不得触发；缺accepted/错身份/lookup None不fresh，窗口耗尽不自动延长。
- 原ledger交错clock/resource事件→paused checkpoint→新boot桥→新advance，累计消费不降、原grant/reservation/revision不变，host-started原bytes不变；waiting/advance、错head/transition、旧elapsed拒绝。
- 第二次合法冷恢复仍读第一条历史桥，重复同transition不追加；真实owner验证的完整闭环由trim节点联验，不以budget测试注入伪称owner fencing通过。

只写必要source负控，root唯一串行执行；不新增安装或模型/solver矩阵。真实SSH/许可证/远端持久服务与实际机器reboot仍是独立资格。P3 opaque/observer可信来源闭合由migrate持有；不以本节点抹除其未知来源。
