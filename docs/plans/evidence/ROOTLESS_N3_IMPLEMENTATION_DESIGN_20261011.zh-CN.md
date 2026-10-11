# N3 最小实施设计与额度冻结

状态：设计经父代理与独立审查者确认；源码已实施，无模型定向门禁 138 项通过，科学合同与原生资源保护双独审 PASS；独立安装入口验收通过，已提交 c19498a，见 ROOTLESS_N3_ACCEPTANCE_20261011.zh-CN.md。本文件不授真实测试权限，不修改已有实例或安装包。

## 科学声明与机械事实

新协议 5 在 H 增加 nullable `search_plan`：探索范围、至多四个明确承诺（科学 label、最小判别试验、旧机制 ref 或 null），以及首个 focus。host 用原 H 节点及条目生成 ref；后续 H 修订引用原 ref，名称或实现文件改变不产生新的消耗身份。没有新计划的 experiment 请求保留科学结论，停止新 W 派发并说明缺失。

A 增加 nullable `search_review`：承诺处置（screened / deferred / waived / pending、理由、确切已绑定科学来源），以及下个 focus。focus 的请求类别为 screen / improve / repair；repair 另引用确切原 W 结论。W 使用 host 绑定的 focus 与已有 summary / scientific_result / limitations，不手写候选台账、哈希或重复机制清单。A 的判断可引用负结果、不可实施原因与 E 提供的证据；host 只校验声明、来源绑定与记录存在。

未处置的旧承诺不会因新 H 省略而消失；它们保持原 ref，直到 A 明确处置。尚有未处置承诺时不派发 improve；优先执行已承诺的判别工作，或由 A 给出有来源的延期/豁免。screened 的来源须包含同 ref 的 W screen 原件，host 不判断该试验是否科学有效。A 推荐、代理最高和实际提交继续沿 N2 分开记录，未知适用性及代理无提升不自动证伪机制。

## 可执行额度与计数口径

新 prepare 默认冻结三个可配置额度：每 W 片 **900 活动秒**、**2,000,000 观测 tokens**、同原 W 证据修复请求链 **最多 2 次 accepted 派发**。无每机制终身片数限制；累计投入由全局预算及后续 N4 约束。小额度可以在无模型夹具中覆盖。

80% 收口窗口为开始时可见的建议（默认 720 秒 / 1,600,000 tokens），不是实时通知或封存保证。native exec 未提供可靠中途交回接口，不新建后台模型或调度系统。硬保护复用 runner：在接受 intent 时冻结同 boot 身份、累计活动计量锚点与 job 身份，持续检查活动秒与本节点已观测 input + output（input 含 cached 部分，不另加 cached）。token 可能直到 turn.completed 才到达，不能称精确计费硬限；时间保护也受循环检查及进程清理延迟影响。

正常 W 完成、验证及封存后交 A；新 W 为新上下文，并单独记录派发和用量。硬超限或原生失败保留 native outcome、已有候选及未封存材料，停止派发；不伪造 W 科学结论或 A 交接，不自动重试。恢复不退已消费额度。

repair 只计冻结 focus 声明的修复派发：若引用的 W 自身是 repair，沿其冻结 job 继承原 repair-root，故改名、换文件或引用上一修复节点不清零。控制不声称能检测任意 shell debug 或判断科研故障类别。候选数量复用 N2 封存观察，只代表 adapter 可观察的新候选；没有 adapter 或覆盖不足为 unknown，不宣称拦截每个 native 实验，也不把候选数当大循环数。

## 实施范围及兼容

单 `search.py` 从已有 sealed H/A、冻结 W job 与 native intent 重建投影，不另建权威台账。contracts 绑定小科学结构与 host 搜索视图；controller 控制新派发；native 增加本片保护；prepare/CLI 冻结可选覆盖配置。budget.py 的全局计量保持原接口。E 原请求/返回通路保留；历史继续分页、旧实现仅显式按需转交，不继承祖先附件。

协议 1/2/3/4 的 schema、view 与原件保持字节兼容。旧 settings 没有 search-policy 时不强加新门槛或迁移。新 strict schema 的 nullable 字段也列 required；null 表示不作该科学声明。N4 后续读取同一机制 ref/处置/请求类别，不另造第二份机制台账。

任意 native shell 对外部提交文件的写入仍取决于原 launcher 权限；N3 不新增发布引擎。冻结观察保留原模型与科学依据，但不能据此声称所有外部覆盖已被控制层阻止。

必要夹具：小片时间/token硬保护与未 seal 失败保留；正常短片进入 A；旧协议/无 policy 恢复；pending 原 ref 跨 H 修订及改名保留；未处置时拒 improve；负结果与延期/豁免来源；同 root 修复第三次拒派发、重启不重计；N2 unknown/分槽保持、E 通路不变。

有界包大小实测：同一无模型 H/W/A/W 夹具，与协议 4 保持相同历史后比较真实 pretty-print science-task，新增分别 1,038 / 1,402 / 1,598 / 1,670 bytes；search 视图自身分别 969 / 1,328 / 1,491 / 1,576 bytes。新 search 视图对 pretty-print JSON 冻结 4,096 bytes，必要时减少默认显示条目并保留遗漏数与原页入口；原 history 默认摘要仍冻结 4,096 bytes。启动提示词常量增量为 0，不把 schema 再塞入启动文本。此夹具不调用 native；实际假 native 片计量、硬停止与 CLI 路径由门禁另测，不能据包大小声称真实模型行为通过。
