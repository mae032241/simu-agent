# G3 managed execution 等待与恢复独立复审（2026-10-16）

## 结论与范围

**PASS（限定工程范围）：新 waiting 路径与旧 sealed unknown 的追加恢复路径通过复审；本次精确差异未发现新的 P1/P2 阻断。** 原 G3 反例已有保留不可变历史的恢复入口，不再要求修改旧 seal 或重置预算。本结论不代表真实模型会话续接、远端服务或科学判断已验收。

基线 HEAD：`92c29aba763213812fa374979f04a116adc8f9b2`。范围为[冻结 JSON](MANAGED_EXECUTION_WAIT_G3_FIX_20261016.json)所列 **20 文件**：15 个生产文件、3 个 fixture/tests、用户文档与设计文档各 1。独立计算的当前 SHA256 全部一致；15 个生产文件与 wheel 源快照、fixture 安装模块及两份隔离测试副本亦逐字一致。只写本文档，未改实现、测试或提交。

采用 `scid-cross-boundary-review` 与 `scid-change-scope-checks`，追踪 CLI/controller→native/continuation→managed execution→history/search→正式材料及后继 admission。复用并核对已有原始证据，未另占测试锁或运行模型、solver。

## 关键边界

| 路径 | 复审结论与证据范围 |
| --- | --- |
| 新 accepted/running → waiting | 原 accepted、host interface、external identity 一致且 query 明确 running，才进入等待；accepted/submitted/unknown 不升级。默认同一次 `run` 每秒监控原 call，不调用 LLM、不再 submit。已核对 success/failed、fragment continue、先成功后 pending 的双 call 案例。 |
| 终态 → 原 W 消费 → seal | 复用共同 observation 与 proof 校验；collect=false 不调用 collect。唤醒材料来自 retained proofs/outputs，不读外部 source。W 实读 native 原件与输出后封存，随后 A 接收事实。native terminal 即使已有 checkpoint，也等待 exact runner 退出；已知 missing-output 维持原 repair 诊断。 |
| 唤醒幂等与身份 | 同 session、原 workspace/header、执行链及有限次数受原冻结策略约束。wake intent 先持久化；intent 已落而无进程的模拟崩溃保持 unknown，重启不补发。重复 run/通知不多启动；accepted、submission、retained proof 篡改拒绝。 |
| 暂停、锁与预算 | pause 在申请 controller 锁前发布标记，等待持锁不阻止该标记生效；终态可核对，pause 未清不发新 native turn。等待计入全局 active 消耗 `advance+waiting`，不增加 advance/token/dispatch；elapsed 继续原 elapsed，重启不退款。wake 消费原累计节点预算与有限 continuation 授权；pending managed wait 阻止 budget-amend。 |
| 旧 sealed unknown → recovery | 显式 `execution-recover` 持 controller writer，追加绑定旧 seal/旧 row/原 accepted/新终态的事实。旧 seal、旧 job、旧科学结论保持原字节与验证语义。重复 recover 复用同事实，真实锁占用时 CLI 拒绝且不追加。 |
| 恢复前缀 → search/材料 | 新 job 冻结精确恢复前缀，旧 job 缺字段按空集合读取；已准备 W 的 prefix 与 prior_unknown 不变。按 `(source_step, call_id)` 仅消除对应 unknown，原机会/grant 次数不重计。双 call 只恢复一个时仍阻断；全恢复后计数仍各 1。新 W/A 从正式索引读取追加原件并自行判断，A screened 后下一 admission 通过。 |

预审发现的 fragment 绕过 waiting、无 collect 缺 native 原件导航、missing-output guard 兼容，以及原件相对/绝对路径匹配与 runner 退出竞态，均已在最终文件修正并有对应定向证据；不把早期失败日志抹成全绿。

## 原始证据核对

| 批次 | 实际结果 |
| --- | --- |
| `/tmp/scid-managed-wait-source-final-20261016/batch-001/` | `131 passed, 4 failed`，144.21s；4 项同为恢复原件路径匹配错误。含新等待/恢复、composed、generic inverse、budget、原 fragment/local/nonlocal 兼容。 |
| `/tmp/scid-managed-wait-source-final-r2-20261016/batch-001/` | 路径修正后 `21 passed, 1 failed`，62.61s；唯一失败为 fragment runner 退出竞态。包括 B 三组合、双 call/旧 prepared W 与预算兼容复核。 |
| `/tmp/scid-managed-wait-source-final-r3-20261016/batch-001/` | 最后 runner 边界修正后，精确 fragment 案例 `1 passed`，6.93s。 |
| `/tmp/scid-managed-wait-source-native-guard-20261016/batch-001/` | 非整数 native returncode、unknown native usage 不得转为 waiting：`2 passed`，0.89s。 |
| `/tmp/scid-managed-wait-installed-20261016/check/` | 最终冻结 wheel 独立 venv、真实 entrypoint、`python -I`：新文件全批 `21 passed`，57.60s。 |

所有批次的 resource.json 均 `cleanup_complete=true`。独立核对 installed 驱动、隔离 sys.path、真实 `scid-composed-contract-fixture` 工厂位置及 243 个核心文件无源字节差异。核心 wheel SHA256：`340383319104eb5093d2487fa51fa3504488cac89cdfde0e3c82a8c4b539d259`，独立计算相符。源码批次之间有上述窄修，不能宣称单一最终版本完整重跑了所有源码目标。精确 diff 的空白检查通过。

## 未验证项与保留限制

- 唤醒实测是 scripted launcher 的 same-session 工程流程；本轮 managed wake 不提供 new-context 回退，能力不足保留 checkpoint 并报告 unavailable。未证明真实 Codex/其他平台 thread 注入或会话续接资格。
- 未运行真实模型、solver、网络后端或全量套件；合成 W/A 的结论只用于工程断言，不能当科学有效性、候选最优性或外部提交证明。
- 已准备的旧节点不会自动吸收 recovery；需要新科学节点消费追加前缀。已接受但提交不确定的 wake 仍保持 unknown，不以自动重试掩盖身份缺失。普通科学 `next_action=wait` 仍表示停止，不能混同 managed execution waiting。
