# U0：未封存 W 的实时观测与反馈

状态：组件 v1 已冻结；最终源码77项、安装89项门禁通过，最终独立审查通过（见同目录 U0 review 记录）。本轮仅开发和零模型验证，U4真实科研未获授权；不恢复旧场。

## 复用与合同

- 新 prepare 默认冻结 `live_feedback_version=1`，新 job复制组件标记，不新增启用开关。未配置合格实时 observer 时明确 unavailable，计数是 unknown/null，不假装零实验。U0不改科学13的队列、路由、准入、额度或周期计数；单current执行退役由后继独立节点负责，observer合同2与反馈组件v1是不同维度。
- generic `feedback.py` 通过已冻结的 observer adapter/config 做只读 progress请求，复用 `history.read_adapter` 的原同步只读传输、5秒/256KB边界；core不import cov。host `scid-research status` 无需instance writer锁，可以在W尚未结束时查看该节点回执。
- cov只解析当前step/job及已接受attempt的确切scope。状态按唯一call_id重建，不存增量余额或第二本台账；仅精确PID/task/boot/start匹配证明 running，没有这种证明或半写JSON只保 unknown。已有完成原件的metadata SHA失配、路径/身份逃逸是完整性错误。
- 轻量进度检查接受/完成、row/stdout/terminal等同调用metadata；不逐次读取大source/model、不加载pickle。最多显示16调用，总状态计数、遗漏数、覆盖及更新时间同时返回；受管调用容量沿用现128上限。完成观测不代表模型/代码原件完整、审计通过或目标科学适用性，最终封存/父选择/资格仍走原完整验证。
- 工具 run和lineage-status回包附固定当前workspace的 `work/budget-status.json` 最近host观测，包含观测时间、剩余观测上界、在途用量未知及软复核建议。提示缺失/畸形不可当0余额，提示不授实验权限、不收费、不决定科学状态。路径不可指向任意宿主文件。

## 通知与执行边界

本版可由host在没有新工具调用时查询进度。W只在工具回包或显式query获得反馈，当前CLI没有已验证的mid-turn消息注入通道；无查询时有通知延迟。软复核请求仅是有界建议，U1再负责新调用准入，U3再负责A介入；U0不通过强杀节点伪造协作。

只读查询不seal、不reconcile、不启动新实验、不消费科学机会、不补额度；重复读取/重启按原call_id和不可变回执重建。普通shell和未纳入回执的工作不冒充完整受管实验覆盖。公共反馈只含调用状态、候选ID、评估版本、公开指标、父候选及资源提示，不传原日志、源代码、模型字节、控制哈希/路径、秘密或隐藏评分。

## 实现与门禁

源码范围：新feedback模块；cov_lineage轻量progress/公共工具回包；history提取原adapter传输；controller/contracts冻结默认组件；cli只读status接线。无新执行器、账本、科学表单或科研模型。

新test_live_feedback覆盖真实受管子进程终态前running可见、半写JSON、PID不匹配、18调用/16可见/遗漏2和无大asset读取、已发布metadata损坏、预算提示未知/更新时间/复核建议、symlink安全、持writer锁读取未seal W和无observer。现wrapper资格保护保留：source/model进度不重hash，但后续新执行或父选择仍拒坏原件。

独立早审发现的畸形advisory枚举/大整数异常、CLI完整性异常裸输出及已封存节点重复扫描已修复，并补5个负例/相关断言。

门禁分批记录（不相加为独立用例总数）：
- 首冻结7文件源码回归83项通过，29.39秒：`.trial/u0-source-20261013/batch-001/pytest.log`。
- 修复后3文件源码回归44项通过，12.78秒：`.trial/u0-final-source-20261013/batch-001/pytest.log`。
- 新构建wheel实际CLI默认反馈与job标记为1；12个实际导入模块来自site-packages且哈希匹配源码；安装回归56项通过，18.38秒：`.trial/macro-role-installed-20261012/artifacts-u0-20261013/u0-installed.log`。
- 同wheel的23个research_loop模块匹配源码，安装CLI的模拟H→A→W→A及重启无重放通过。wheel SHA256：`7a197e4c9fabeb288a8d5544e47d58637c958ea830b5021d593060a2f1c9aae2`。

未跑全量、真实科研模型、真实TCAD、浏览器或原生同线程续接；运行中观测用实际受管测试子进程验证，不授予科学效率或结果质量资格。

## 通用性边界与最后修订

U0提供通用观察合同，实际受管执行仍只验证cov实现；它不构成通用执行监控资格。后继U0r按主计划7.2接入可注册执行接口和普通本地命令实现，同一核心处理两者；本记录不宣称TCAD接入已完成。

最终补修覆盖畸形预算提示、非有限指标、host status在有/无node policy时的非对象intent/outcome及解析异常归一。前两次最终门禁均76通过/1失败：深JSON测试错误地假设解析器必按Python递归上限抛异常。生产实际已typed拒绝；修正为真实深JSON拒绝与精确read异常注入分开验证，未降低生产校验。最终77项源码通过，日志`.trial/u0-close3-source-20261013/batch-001/pytest.log`。

最终fresh wheel门禁：安装89项通过，20.72秒，日志`.trial/macro-role-installed-20261012/artifacts-u0-close-20261013/u0-installed.log`；实际安装CLI默认标记、模块源码哈希、无模型H→A→W→A与重启无重放通过。wheel SHA256 `cacadde02e2fdb8786d6c54a89add0b2212165a2224b766c4cce70e155d82351`。此前安装记录不代表最后补修，以上是最终快照。
