# W任务类型与交付验收

状态：开发与定向安装验收完成，独立审查见[审查记录](WORKER_TASK_ACCEPTANCE_REVIEW_20261014.zh-CN.md)。基线 `0ecd4f9`，当前协议16；本轮无模型请求、旧实例升级或隐藏评分。

## 交付范围

- H/A显式选择screen、improve、repair、validate；控制冻结该选择，不按前驱角色猜。浅筛允许组合范围，局部任务要求明确机制。
- 浅筛W给每个指定方向留下科学发现或明确阻碍。控制核对结构和既有受管原件；调用机会、交付完整、A判为screened是不同事实。
- 普通交付缺项返回同一W/原生会话，复用原实验、共享预算和有限补正额度。明确阻碍、未知执行或真实额度边界只产生partial，不算浅筛通过。
- 每次回复绑定自身的有界原件快照，后续补做不能改写此前验收。深挖、修复、补验证不要求重新扫完组合。
- rootless隔离启动器支持确切已接受的同线程续接；错身份、未知执行和重放仍拒绝。测试使用真实进程与隔离命名空间、模拟native输出，不代表真实模型续接已验证。

## 门禁记录

| 门禁 | 结果 | 说明 |
| --- | --- | --- |
| worker-task-launcher-source-01-20261014 | 22通过 | 启动器解析与身份负例，早期冻结切片 |
| worker-task-source-01-20261014 | 96通过、2失败 | 33秒；暴露组合screen被误作追加授权/改序，已修复 |
| worker-task-source-02-20261014 | 141通过、13失败、3错误 | 两项生产回归已通过；剩余为旧隐式类型/缺发现字段、旧说明字节上限和缺fixture依赖，逐项迁移并保留原断言 |
| worker-delivery-source-03-20261014 | 12通过 | 直接封存、篡改、只读、partial、未知原件、活跃写入者及未配置续接的默认出口 |
| artifacts-worker-task-01-20261014/build/check | 通过 | 全新wheel/venv与实际CLI，零模型 |
| artifacts-worker-task-01-20261014/breadth-context.log | 339通过、8失败、1不适用跳过 | 23文件安装联合验收；未授整体通过，失败原件保留 |
| artifacts-worker-task-02-20261014/breadth-context.log | 313通过、34失败、1不适用跳过 | 父测试驱动以symlink复用venv，原件路径与冻结适配器校验拒绝；属于驱动配置错误，未修改产品校验 |
| artifacts-worker-task-03-20261014/breadth-context.log | 346通过、1失败、1不适用跳过 | 134.98秒；直接使用原安装路径，7个实际namespace用例全部通过；仅预算负例缺host时钟初始化 |
| artifacts-worker-task-budget-04-20261014/breadth-context.log | 1通过 | 2.96秒；补合法host-started及advance前置，保留原预算/禁止循环/只读断言 |

所有日志保存在外层`.trial/`，测试与构建由父执行者持共享串行锁运行。最终23文件覆盖分两批合计347通过、1不适用跳过；不能称全仓测试通过。01构建的CORE04 wheel此后未改，03/04直接使用同一原venv路径，分别重核31个research_loop安装模块SHA与源码一致；日志、目标清单和模块绑定都保留。

7个实际namespace用例覆盖：两种原有new-context链、同线程正常续片、输出修复、终态重放拒绝、unknown dispatch拒绝、浅筛P-only交回后同线程只补Q。最后一项关闭普通output_repair、正常fragment策略仍为new_context，验证工作缺项确实进入独立的same-session返工路径；原P查询复用，不重提。跨W复用与blocked不能冒充screened另有定向用例。

## 审查与验收中的修复

- 组合screen未点名机制时，不再误授额外机会或清空组合投入窗口。
- continue且交付未齐时遇到预算边界，冻结真实退出依据后交partial；不能在seal/wait之间递归。
- 首次采集验收原件前检查原执行者已停止写入，后续validate只读；原P-only回复不会被后来Q追认为完整。
- 未配置node预算/续接的合法默认任务，凭已知原始用量和终态保留partial；真正续接仍要求原预算资格。
- partial原因从已封存控制结果进入A的短问题；跨W复用的旧观察可供A筛选，但不计新调用、投资或修复来源。
- 安装首轮8项失败均定位到测试：5项模拟native缺hashlib导入，1项A用了H的label字段，1项预算先写intent导致未准入用量未知，1项仍读取旧val_score而非通用metric。修正fixture与当前接口契约，不放宽生产拒绝、身份、计数或只读断言；随后实际namespace复验通过。预算夹具还补齐真实host时钟前置后单独通过。

## 资格限制

本轮不改变W→A常规路由，不保证科学覆盖充分，不声明token或得分改善。任意原生shell仍不属于受管实验观察范围。未运行全仓测试、真实模型、浏览器或远端TCAD；此前25项退役协议测试债务不因本次定向通过而消失。
