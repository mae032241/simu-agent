# 多机制受管执行：实现与验收

状态：源码定向验收及全新安装包联合验收通过，独立审查另见同目录记录。基线 `b8f402a`。本轮没有模型请求、隐藏评分或旧实例迁移。

## 实现

- 当前写协议为15。固定 W stage owner；每次受管调用独立绑定 H 机制及版本。W 仅选择科学标签，控制层写引用和哈希。
- H commitments 的顺序表达优先级，minimal_test 说明预测、判别问题及科学理由；不要求 H 填实验数量、求解器或网格。
- generic `Records.accept` 在原短锁中检查冻结组合。每机制初始机会由任务配置 `initial_calls` 决定，默认1次；其它未处置机制尚无机会时，限制领先分支继续追加。local 与 cov 共用这个入口，核心不导入 cov 实现。
- 已接受的成功、失败、未知、修复调用都计投入。新脚本、新 W、恢复、同一机制改名或 H 修订不退款。A 明确选择并说明理由可给一次额外机会，精确绑定该 A 原件；同一授权重放不刷新额度。
- A 可明确 deferred/waived。机会被使用不等于科学筛选完成；screened 必须引用相应 H 版本的确切最终 W 及已知终态原件，再由 A 判断科学意义。
- 历史复用既有 observations 和原件快照，只附必要受管回执元数据。修复与组合复议按实际执行机制统计，一个 W/A 科学周期不因多次运行而膨胀。
- 角色上下文节点已单独提交 `b8f402a`，详见其实现及独审记录。它保留完整局限项和失败/未知入口，但默认 view 字节增加，不能宣称已节省真实 token。

## 验收发现并修复的问题

1. 自动附加机制归属后，重复查询误报 external identity 改变：canonical submission 统一包含原 accepted binding。
2. `python -m` 和插件导入产生两份异常类型：完整性错误、unknown collect 的 UnsupportedExecution 分类与普通 CLI 统一；不按错误文本猜类型。
3. W 初始 focus=P、实际执行 Q 时，repair Q 的来源查找和科研轮次仍沿用 P：改为 exact managed originals 的实际机制/H版本集合。
4. live progress 新增的 accepted 读取逃出原损坏记录处理范围：恢复在该范围内读取，破损 JSON/UTF-8 显示 unknown，不伪造成功。
5. 新 Q 修复用例最初遗漏当前 A 必需的科学决策问题：补齐有效问题和改变判据，保留原修复/计数断言。

## 已执行门禁

路径均位于仓库外层 `.trial/`，原失败日志保留。

| 门禁 | 结果 | 说明 |
| --- | --- | --- |
| breadth-source-01-20261014 | 50通过、1跳过 | 跳过为 cov 不适用 local payload 用例 |
| breadth-admission-source-01-20261014 | 59通过、4失败 | 暴露查询身份及完整性分类缺陷 |
| breadth-admission-source-02-20261014 | 16通过 | 两执行器真实 CLI；上述缺陷修复 |
| breadth-source-03-20261014 | 178通过、31失败、1跳过 | 扩展组合回归，见下方分类；不是整体通过 |
| breadth-source-04-20261014 | 74通过 | 新科学集、独立 common CLI、live feedback；含 unknown collect 与 Q repair |
| artifacts-breadth-context-01-20261014/build/check | 通过 | 新 wheel/venv、实际 CLI；零模型 |
| artifacts-breadth-context-01-20261014/breadth-context.log | 290通过、1不适用跳过，106.45秒 | 17个测试文件；所有 research_loop 安装模块逐文件SHA匹配源码 |

安装集包括真实 bwrap/main/registered-cov：H封存P/Q，W执行P、重复P被拒、Q可执行，新上下文查询原P不重放，最终A分别screen两机制，原件及候选绑定仍精确。两个namespace用例都执行，唯一跳过是cov参数下不适用的local payload测试。local和cov的共用CLI、篡改、unknown、repair、源码/安装隔离交付路径、角色视图及科学handoff一并通过。测试驱动位于外层 `.trial/macro-role-installed-20261012/`，构建与运行均持共享串行锁；安装产物的 `test-targets.json`、`breadth-context-result.json` 保存精确范围及模块绑定。

source03 的31项失败明确分为：1项新Q修复夹具、2项live回执真实回归、3项旧无受管原件的科学screen/repair夹具、12项旧portfolio协议/版本预期、13项退役exploration_order协议预期。前3项在source04解决，科学夹具改为真实local执行且保留原诊断断言。后25项未改写或删除：基线代码已经只接收portfolio version2并拒绝旧排序表配置，仍登记为当前测试债务，不能算通过。当前替代行为由 current_protocol、lineage_current_search、breadth_science 验证。

## 明确限制

- 控制层保证受管机会，不保证方法真的不同、覆盖科学上充分或结果更好。任意原生 shell 仍不在受管接口覆盖内。
- 已封存历史 unknown 会保守阻断新提交；本轮不提供解除旧未知记录的新恢复器。原调用 query/collect 不受广度门控，未知提交不可重放。
- 多机制组合上限128；片段/候选简报有界，不承诺整份 science-task 只有4KB。A 的候选推荐、代理最高和实际交付仍分开。
- W→A 频率、辅助者权限及总预算未改。条件 A 路由和科研效果需另行验收。
- 未跑全仓测试、真实模型和远端TCAD。旧 U4 真实场仍为失败，修复不会追认旧场通过。
