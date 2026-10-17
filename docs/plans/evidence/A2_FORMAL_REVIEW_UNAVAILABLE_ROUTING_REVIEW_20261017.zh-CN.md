# A2 正式审查不可用续行独立静态审查

结论：**重冻六文件静态 PASS，可交 root 串行定向验证。** 范围为 formal_review、semantic、controller、contracts、test_formal_review 及[实施账](A2_FORMAL_REVIEW_UNAVAILABLE_ROUTING_20261017.zh-CN.md)。不混 A4 或未实施 A3；不授真实模型、身份独立或外部交付资格。

## 真实控制链

- 原 `request_route` 对同 key 第二次请求返回空路由、controller 直接全场 wait，现改为普通 A 的不可用反馈。没有创建正式 reviewer，也没有改精确 subject/作者资格、原 review receipt 或执行批准。
- `semantic.effective_route` 复用现有 author_correction 的 root/source 与 `MAX_AUTHOR_CORRECTIONS=2`。失败原件只枚举原 native-evidence 下小控制文件，核 requester seal 与 failure_key；新 key 必须由 host 对确切对象/身份重算，不以模型标签或改 route_reason 重置。
- 合法 E/科研改道可解除当前专属补正，但同 key 失败原件仍参与计数；任务验证和公开剩余按各自 step 的原 prefix 计数，不用将来事件改写旧任务。无新重试 ledger、第二任务库或余额。
- controller 在建下一 job 前检查耗尽：有原 delivery_policy 则沿 `_start_closeout`，仍核原 prefix、活动调用、预算和交付绑定；没有则明确 `formal_review_blocked`、缺口和恢复条件。不是 generic wait 或完成，不授缺失资格。当前被引用 root/source 错误或原件校验失败不会被当作新失败机会。
- schema 保留条件性 formal_review，使同一输出能选择真实新对象；反馈仅给普通动作示例并保留其原准入条件，不谎称一份例子列表就是全部可用操作权威。

## 发现并修复的阻断

首版 unavailable 分支会无条件覆盖已有非 formal 的 author_correction，例如一般科学决定缺失的 root/reason，造成旧补正额度被重置。重冻版现仅在没有其他补正时建立 review root；已有其他补正则保其 root/reason，只更新真实 source，并继续保留审查不可用反馈。没有引入第二补正栈。

定点核对新增回归：真实 `continue_w` 缺 decision 声明先产生 `a_decision_request_missing`；该补正 A 随后请求不可用 formal review，下一普通 A 仍绑定原 root 3/reason、source 4 与 accepted=1。它不是用 mock 直接指定想要的 root，且旧 job 通过真实 build/seal/validate 路径保留。

## 负控价值及局限

- 改写理由后仍可 finish：发现同 key 被错误当新请求或 unavailable 误授资格。
- A→E→A 后耗尽及 restart：发现失败额度被改道/重启刷新、再次建 job 或回滚消费；核原 7 节点、105 observed tokens、2000 token/60 秒 ceiling 和原件字节。
- export-only closeout：发现未进入原收口、重复创建收口或出现意外提交；它不证明真实 adapter 交付通过。
- 缺 subject/不支持 launcher 与真实新选中材料：发现不可用请求误变 reviewer，或 host 新 key 不被接受。launcher 分支用作者 stand-in 隔离诊断优先级，不证明真实身份资格。
- 既有正式通过、作者重叠拒绝、普通 A/pass 不授资格继续保留；上述其他补正 root 回归覆盖本次独审发现。

测试共 10 个实例，只写未由独审运行。process 用例沿真实 controller/native 控制链，但 launcher/session 是本地合成事实；不能冒称模型科学独立。现有全场/节点预算、closeout 有限补正、必需交付审计与执行权限未放宽。

## 检查与交接

独立仅阅读冻结 diff、原路由/补正验证/closeout 接缝及相关 fixture 语义；限定 `git diff --check` 无报错。作者 AST 证据见实施账。没有执行测试、收集、项目 import、业务 CLI、安装、模型、服务器或远端作业；唯一写入为本报告。

允许 root 按原资源限制串行验证受影响 formal-review 用例，再记录实际结果；未出现具体风险不扩大回归或安装矩阵。A3 默认输入去锚定另审，不能从 A2 的身份/路由修复推导已实现盲评或访问隔离。

### 首轮验证后的一行 fixture 修补

root 报告 source 5 passed、process 4 passed/1 failed。已读 `.trial/authority_remediation_20261017/a2-process/batch-001/pytest.log`：唯一失败在 `controller.prepare`，交付 fixture 未配置必需的全角色 node budgets，尚未进入收口生产路径。

修补仅在测试启用 delivery_policy 时传入 HWAE 各 100 observed tokens/5 seconds；满足原全角色正有限合同，其余测试配置不变。原场 2000 tokens/60 seconds/10 steps 及 soft 模式不变；export-only adapter=None、submit/confirm=0，原 closeout 30 tokens/1 second 对应预留 30 tokens/1 second/1 step，没有增加原总额度或外部权限。定点静态 PASS、限定 diff 空白检查无报错，允许 root 仅重跑该失败项。生产未改，独审没有执行测试；此处不预记复测通过。
