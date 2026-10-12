# N6c：已知异常终态的 Worker 原线程续接

状态：设计、源码独审、回归与零模型安装验收通过；[验收记录](ROOTLESS_N6C_WORKER_RESUME_20261012.zh-CN.md)维护测试快照。基线为 N6b 提交 `a5f4bb7`。实际 Codex 同线程恢复与增量用量未验证；不恢复 N5、不追加预算、不把 N6b 转交 A 收口当成 Worker 续接。

## 需求与首版范围

用户新增要求：Worker 已知异常停止后，保留原任务与断点，继续原线程。已有控制器只能重接活 runner 或补封存成功输出；本节点补的是已停止 Worker 的有限续接，排在 N6b 后、T0 前。

- 新 prepare 显式启用、冻结 resume-capable launcher；最多两个新增已接受 continuation，不自动循环。拟显式 `worker-resume --root ... --step ...`，命令最终语法以实施合同为准。
- 首版故障骨干：native 非零 returncode、`stop_reason=None`、有效 completed meter、原进程组清理可确认、真实 thread/session 可回读。原输出成功但待封存时优先补原 seal，不重复模型工作。
- 原 job、schema、输入、配置、权限、模型、home、workspace 与真实 thread ID 保持绑定；不用 `--last`、名称猜测、新 thread 或复制 home 代替原会话。
- unknown 执行、清理未知、必需计量缺失、身份失配、已发表 closeout、原科学 pause 均不能借续接绕过。保护预留停止、总额或节点 cap 耗尽不默认可恢复。
- 受管理执行按原执行 ID 收集/恢复，不重发不确定提交。普通 native shell 保留 session/workspace/checkpoint，由角色读取已有结果继续；不新增机械副作用台账，不承诺任意脚本幂等，也不因此一概禁止已知本地故障续接。

## 三项冻结决定

1. **计量不退款。** 原 attempt 与每个 continuation 的有效 `turn.completed` input+output 各计一次，cached 不另加。账单迟滞单列限制，不把所有已知本地故障都变成硬 unknown；缺必需 meter、重放历史用量或无法区分累计增量、受管理执行本身 unknown 仍硬拒，不能补零。实际 resume 用量口径尚待资格核验。
2. **继承原额度。** 原 node/W cap、已结算 attempt 消费与节点计时不重置；新 continuation 绑定当次有效共享 grant，只获得原节点余额。新增 accepted continuation 占原执行名额，计入总 token/active 秒/steps，并保留 N6b 交付预留。合法全局 budget-amend 不退款、不隐含扩节点 cap；已接受 attempt 先收终态再判次数，不因重启重新派发。
3. **一个 execution-ref。** 原初始 intent/outcome/usage/log/raw 不覆盖；追加不可变 continuation 原件与前置链。集中解析成功 attempt，覆盖 contracts/controller/history/runtime/budget/native/semantic/correction 及 N6b `delivery.binding/invoke` 的原件读点。seal 明确绑定成功 attempt 与链；不复制成看似初次成功的 raw，不维护第二个可变 current-attempt 权威。旧无续接 schema/job/seal 字节保持。

## 启动器资格与最小门禁

原设计读取的本机 Codex 0.162.1 help 支持 `codex exec resume [OPTIONS] [SESSION_ID] [PROMPT]`；这是语法事实，不证明实际会话、权限、配置或增量计量成立。新 wrapper 须验证原 profile/home/workspace、精确 session、schema 和每次输出目录；旧 fresh-only 冻结 wrapper/settings 不修改，也不绕 wrapper 直调 raw Codex。

最小无模型门禁：

- fake 已知故障 → 同 thread/home/workspace 续接成功，checkpoint 保留，原件逐字不变；全部 attempt 成本与名额累计，集中消费者只从成功 attempt 封存/交付。
- 控制器退出后收同一个 accepted attempt，不重派；重复命令、cap2、unknown、缺 session/thread/meter、boot/hash/清理失配均拒绝。
- 原 node/W/token/active/steps 耗尽、closeout 与科学 pause 不被绕过；budget-amend 后采用当前共享 grant，原节点消费和 N6b slots 仍保留。
- 受管理执行不重复提交；普通本地 shell checkpoint 可继续，但 fake 不证明任意脚本幂等。
- 旧无续接原字节兼容；独立 wheel/venv 的真实 CLI、集中 execution-ref 与新 launcher parser/namespace 零模型入口通过。

实际 Codex 同线程有效性、resume 增量用量与权限尚未取得验证；fake/installed 通过不能替代。首版不建 checkpoint 引擎、第二预算账本、Root 或新的科学字段。实施估量若明显超出原约200–350行控制接缝（wrapper 另计），先复审，不为压行数省略身份与用量验证。

## 来源与独评归档

本文件是 N6c 当前设计入口，合并原只读小设计及独评约束；来源未重写：

| 外层 `.trial/n6b-implementation-20261012/` 来源 | SHA-256 |
| --- | --- |
| worker-resume-design.md | fe5707ffbbd58b32807a1a4333307fa77c5264ea764e41d8b1e840ba25567a93 |
| worker-resume-review.md | 578a6980d149783fd467d845b75320c68308e87460c3d3bbeec79c66d64d02a4 |

原独评人为本节点实施者、与原设计作者不同；其 PASS 只授予设计方向。2026-10-12 实施者确认了上述三决定及首版故障骨干；最终代码由另一独立审查者评审通过，测试范围以验收记录为准，不授予预算自续或真实 native 恢复资格。
