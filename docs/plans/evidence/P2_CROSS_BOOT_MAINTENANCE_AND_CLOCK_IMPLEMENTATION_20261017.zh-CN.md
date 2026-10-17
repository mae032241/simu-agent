# P2 原调用跨boot维护与暂停续钟实施

状态：源码冻结，独立静态审查通过；root唯一串行定向3项通过，见末节。作者仅stdlib AST和空白检查及读取root验收证据，未运行测试、项目import、业务CLI、安装、模型或solver；未Git操作。

## 本节点与并行owner

作者持 `research_loop/budget.py`、`execution_resume.py`、`execution_authority.py`、新 `tests/research_loop/test_cross_boot_maintenance.py`、本报告及[设计](P2_CROSS_BOOT_MAINTENANCE_AND_CLOCK_DESIGN_20261017.zh-CN.md)。CLI/controller/instance_owner/cold archive接线由P4作者持有，另行独审。P3的experiments/history/formal/source贡献修改不作为本作者实施。

维护公共入口为 `execution-resume ... --maintenance query|collect|cancel --max-seconds N --authorization-note ...`。不能与请求续期共用；只读出原accepted的确切attempt/config并核原host scope、permit HMAC、target/prepared。缺accepted返回unknown且不建call目录。当前有限intent/outcome保留在原call的 `maintenance-operations/NNNNNN/`，同一个非JSON CollectionContext交registered factory/底层RPC/新复制；collect进一步裁原runner policy。不会调用fresh call_identity、prepare、submit、科学snapshot/_remaining或重新申请授权。原external回执缺失时仅精确lookup原prepared；None继续unknown。

原终态仍由共同record_observation完整核验、保留输出/manifest/log。可选资源结算复用原预算owner：旧钟跨boot不能追加时保reservation及诊断，不能为收集伪造新余额；钟可用时合法settle原实际消耗不等于维护授新grant。retire原入口保留，本小节点不新增跨boot永久未提交/退款能力。既有sealed科学/history前缀不回写；本命令不承诺替代科学恢复与时钟资格。

authority.writer与budget ledger writer都将外部owner lease持至完整yield结束，未enroll旧实例保持原路径。authority implementation自动绑定真实instance_owner模块，不依赖插件手填。

## 单一原账本的时钟分段

`paused_checkpoint`要求active basis和当前最后clock为paused，冻结原settings关联、ledger head与host-started proof，不保存第二份余额。`reanchor_paused_checkpoint`由cold restore独占owner验证当前transition后，核同一原head/start；同boot不追加，新boot只追加 `kind=clock, phase=paused, reanchor={checkpoint,transfer}`。同transition同boot幂等，换boot不能复用旧transition。

历史_events校验桥时仅读immutable transition关系；后续新generation不能使旧桥失效。普通_duration跨boot仍拒绝。snapshot逐段保留advance/waiting实际累计、原资源grant/reservation和授权revision；只跳过已证实暂停但不可测量的跨boot间隔。`elapsed_seconds=null`、`unmeasured_paused_gap=true`明确不测墙钟总耗时。旧无桥返回形状保持；waiting/advance、旧elapsed、过期head、缺原件不续钟。host-started不重写。首次冷恢复与owner fencing完整接口由P4节点联合验收。

## 最小目标与证据边界

新增3个source目标，作者均未运行：

- `test_paused_clock_bridge_preserves_consumption_grants_and_old_history`：交错clock/grant/reserve，跨两次boot桥，核5秒→9秒原消费、原grant/占用/revision、旧ledger/start bytes、同transition幂等。owner读回为可信DI，只证明预算分段，不证明真实fencing。
- `test_clock_bridge_rejects_unpaused_stale_or_elapsed_checkpoints`：advance/waiting不准入，checkpoint后新grant导致head不符拒绝，elapsed拒绝。
- `test_cross_boot_original_maintenance_collects_without_scientific_dispatch`：复用现精确compiler/review/run夹具与真实registered managed wrapper，仅backend/原生身份是可信DI。换boot并令科学snapshot/_remaining触发即失败，公共controller维护query/cancel/collect，核唯一submit、完整共同observation、原ledger/accepted/seals不变，缺accepted不建目录；维护service派发哨兵和绝对窗口耗尽拒绝。

4 Python stdlib AST与尾随空白静态通过，无收集/测试执行。RPC采用同一绝对窗口；既有只读完整校验、freeze代码hash及单个阻塞系统调用不承诺硬实时中断。完整归档JSON解析/历史原件校验成本未扩大为全仓deadline改造。真实reboot、SSH/socket transport、外部作业/solver/许可证与真实模型身份均未验收。

## root串行动态增量验收

作者只读核对 `.trial/p_finish_20261017/cross_boot/{result.json,batch-001/pytest.log,batch-001/resource.json}`：本文件3目标一次通过，pytest **3 passed / 5.94s**，监督 **6.145s**，树RSS峰值 **83,918,848 bytes**。退出0，cleanup_complete=true，memory_stop_triggers=[]、received_signals=[]，address_space_limit_enabled=false；末次MemAvailable为14,456,496,128 bytes。root使用768MiB采样停止阈值、10GiB可用阈值、120秒每批；作者没有并行启动测试。

关联P4的 `.trial/p_finish_20261017/cold_source` 为4 source通过/1 process deselected，包含实际owner接口的paused桥；`.trial/p_finish_20261017/lease_and_local` 两process目标通过，其中只有一个是外部owner lease负控，另一个是Local来源回归，不重复计作P2新用例。本节点仅声明3个新增唯一目标通过，不声称实际机器重启、完整全套、真实模型或solver资格。现有remote runner UTC弃用warning保留，不影响此批退出结果。
