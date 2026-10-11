# N5：H 增量组合与有限作者补正

协议 8 已完成无模型门禁、独立安装验证及独立源码审查（PASS）；真实原场未恢复，不推定科学验收通过。

## 已采纳的修订

- H 每轮最多四个新增或修订声明；控制从 sealed 原件延续已有组合、机制身份与状态。省略不删除，重命名不重置。当前 focus 可以选择已声明的新 label 或唯一既有 label/ref。控制不从自由文字生成新机制或 minimal_test。
- A 的 screened 更新仅在精确冻结来源中有唯一同机制 screen W 时生效。缺失或歧义记录该项未生效，其他合法 delta 与作者原科学文本保留；不授予失败项 screened 资格。
- 无效实现 ID 保留科学输出，选集明确为空且 unresolved；不回退旧实现。null 继续承接当前未解状态，显式清空或有效替换可以解决选择问题。依赖该选择的新 W 不派发。
- 合法 schema 内的明确机制/焦点/任务准入缺口，依冻结链回 H/A 原作者作有限补正。上限为同一根尝试两个已接受的作者 H/A；更换 prose、原因码、E 中转、重启均不续额。E 可完成已请求抽取，但返回作者仍受原上限约束。
- 控制 seal 中的 `control_outcome` 只描述动作 applied/unresolved，每次从原件重算；不是科学资格或证据支持的证明。诊断有界、由控制生成并在新任务上解释未生效的科学选择。角色不读写内部 job/raw/seal 哈希链。

## 保留的硬边界

不采纳“无效实现 ID 静默沿用旧实现”。不把任意 ValueError、非法 JSON/schema/enum、空科学理由、来源/任务/终态/材料哈希失配、权限问题或未知外部提交改成可补正问题。已接受工作先收集与封存；未知提交不重放。预制但未启动的任务若与确定重放路由不符，以 `retained_job_conflict` 停止，不覆盖。

补正的 step/token/active time 使用原预算与 N3 切片规则。N4 作者补正 A 不增加科学停滞轮次、不消费人工 ack；补正 H 的文字不获得 progress 信用。真正合法并携同一精确 N4 请求的补正 H 可以履行原 H 重审；后续真实被评 W/E 仍按原科学轮次规则计数。

## 已发布协议与真实 H010

协议 1..7 的 schema/view/job 字节保持；有效已封存 7 节点保持原解释。仅未封存、原生终态可信的协议 7 尝试，其显式科学控制字段缺口可增加新的宿主完整性 receipt，保留原输出并明确计划未生效。这个 receipt 不使未声明 focus 成为合法方案。

真实 H010 四旧机制加未声明 MultiTaskLasso focus，控制不能补造第五机制。验证范围仅原实例只读检查，以及复制实例在同一冻结绝对路径下封存未生效尝试、准备新的协议 8 H 补正 job（没有 native intent）；不启动模型、不修改原实例。原场剩余约 7.2 秒 active time、341221 token，本修复不增加预算。

## 验证证据

基准 HEAD `fc36d29`，实现范围为 contracts/controller/correction/history/search、新 semantic 模块、三个定向测试文件与本文；主计划由父代理单独维护。

- 原代码缺陷夹具：known-ref 重命名后省略再选焦点，两参数均失败，`red/batch-001/pytest.log`（2 failed / 2.04s）。
- 新语义精准门禁：26 passed / 11.98s，`semantic-final/batch-001/pytest.log`。
- 一次完整 rootless 门禁：272 passed / 2 failed / 106.59s，失败仅旧 7 夹具仍要求首次 screening 语义缺口必须拒绝整个 seal。
- 按已批准旧 7 H/A attempt 范围更新那两条断言，保留原严格 search 拒绝、坏更新仍 pending、原科学 raw 不变及新 receipt 重算要求；两个相关文件最终 56 passed / 18.10s，`legacy-attempt-final/batch-001/pytest.log`。完整门禁之后生产代码未改，其他通过项未受该测试断言修订影响。
- 独立 wheel / venv：实际 CLI + fake 原生进程走 H/W/A/H/E/H/W/A 八节点、80 token，单一实现跨角色承接、暂停/恢复与重启不重放；另 H/H/E/H/W/A 六节点、60 token 检验两个作者补正、同根经 E 保留及模型只见小诊断、不见哈希链。
- 同一安装包完整只读核验真实 H010 原 schema、view、任务、输入及可信 native terminal。bwrap 同路径副本封存未生效 attempt，仍仅四旧机制、focus 为 null，准备 H11 新 8 补正任务但无 native intent。原实例 4612 个文件哈希前后完全一致。

外层证据目录 `.trial/n5-semantic-recovery-20261011/`，安装结果 `installed-result.json`。wheel SHA256 `33d0437971209b664c2d2b64c625c15247aea5717c7476c710b4e605bbee1184`，结果中 installed/source 七模块 SHA 相同（含未修改 native）。`git diff --check` 通过。所有模型调用为零；未跑旧平台全套、未改变冻结真实实例、未自动恢复原场或扩额。

最终独审报告：本地 `.trial/n5-semantic-recovery-20261011/independent-review.md`，SHA256 `1ef91b8f87f98da1c1d7e6146e72e3f4edc5d4b4396a544448d30c96696c4718`；状态文字在通过后同步，生产与测试保持冻结。
