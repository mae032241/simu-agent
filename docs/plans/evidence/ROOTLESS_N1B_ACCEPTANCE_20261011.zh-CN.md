# N1b：启用时长与人工预算修订验收

日期：2026-10-11。基线：c64a436。独立审查PASS，精确9个文件SHA见[源码清单](rootless-n1b-20261011/source-manifest.json)。

## 已交付

- 新实例按控制推进与原生执行区间的并集计时；明确暂停且没有活动/未知执行时不消费推进时长。旧实例保持原elapsed口径，不原地迁移。
- 控制器退出时仍在运行的原生执行继续计时；runner在同一实例writer锁内追加停表记录。未知时间保守消费，不回填旧终态退额。
- 控制账本追加记录，预算修订保留原/新上限、原设置身份、消费及外部决定说明。修订时拒绝活动或未知执行，Root/角色无自动续额入口。
- 新active推进额度按boot身份及BOOTTIME锚点计量，UTC仅展示；开放区间100→120→110的UTC回拨不退款。跨boot与BOOTTIME倒退拒绝，未提供重启机器后的时钟修复流程。
- 原验收版本另用20毫秒UTC／BOOTTIME漂移阈值拒绝，真实case02的合法时钟调速触发误停；新active实例已移除该判定。旧elapsed实例已有账本时保留原UTC检查语义，不静默迁移。原85项及安装证据仅证明其当时快照，失败与修复验收另记录，不回写原证据。

## 验证

- 共享串行source gate：85 passed in10.29s，[结果](rootless-n1b-20261011/source-result.json)、[日志](rootless-n1b-20261011/pytest.log)。
- 真正安装wheel的CLI完成6节点HWAHWA假进程，预算修订/active计时、N2a精确历史实现转交与重复run不重放通过，[结果](rootless-n1b-20261011/installed-result.json)。模型请求0。
- 新版Codex0.162.1真实native sandbox及外层bwrap负控制通过：宿主settings/ledger不变、无伪造amend或pause.request，[结果](rootless-n1b-20261011/isolation-result.json)。
- 独立审查核对9文件SHA、边界接线及上述证据；git diff --check通过。未跑无关平台全量测试，也未调用真实模型或求解器。

## 范围限制

修订说明是审计文本，不是身份认证；边界依赖冻结的隔离启动器，raw Codex仍为软隔离。命名空间内可创建不影响宿主的shadow路径，测试不声称所有同名路径写入都被拒绝。用量基于观测事件，仍有token更新滞后；确定未提交节点不自动重启。

N2b仍未完成，本节点通过不启动真实测试。待完整N2独审并提交后冻结候选，新增cov仅两场，各600万token；live02计已完成第一场且版本差异如实记录。
