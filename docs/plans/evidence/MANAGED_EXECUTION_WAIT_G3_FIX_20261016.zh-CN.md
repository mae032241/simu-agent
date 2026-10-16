# Managed execution waiting 与 G3 恢复修复证据（2026-10-16）

基线及最终 wheel 构建 HEAD：`92c29aba763213812fa374979f04a116adc8f9b2` + 本修复工作树。实现/测试已冻结，未提交或 push；独审结论另记。本报告记录工程验收，不宣称模型科学效果。

## 状态与权限

native turn 的结束和 managed execution 的终态分开。原 accepted、冻结 host interface、submission external identity 一致，且有 query 能力的原 adapter 明确报告 running 时，run/reconcile 返回 running；控制在 W 封存或下一 fragment 之前保留原 attempt checkpoint，进入 waiting。accepted/submitted/unknown 不被猜成 running；原 native returncode 非整数或 usage unknown 不进入免费等待。

默认一次 `scid-research run` 在控制进程内每秒监控同一 call；无 LLM 轮询，没有第二 submit。共同终态仍用原 execution-observation.json，collect=false 不调用 collect。终态后先接受并持久化 execution_wake intent，再用原 job/workspace 和合格同 session/thread/header 续接 W；W 实际读取 retained 成果和 native proof，再写自己的科学判断并最终封存。wake 不是失败输出修补，不编造 W 科学文本；次数仍计入原有限 continuation 授权和 max_steps，token/dispatch/节点 active seconds 持续累计。

waiting phase 加在原控制账本中，没有第二份预算账。waiting 不增加模型 token、native dispatch 或 advance_seconds，但 accepted execution 的 waiting_seconds 消耗原全局授权运行时限。依据既有 ROOTLESS_CLI 合同，已接受工作和控制器断连后的原执行继续计时；新 active 用 advance+waiting，旧 elapsed 始终使用原总经过时间。pause 可核对和冻结已接受终态，但不发新 wake turn；后端仍存活时不免费停表。存活 waiting 仍拒绝 budget-amend。明确终态后暂停可停 idle 时间，不回填历史时点返还已用量。

同 boot 控制进程重启恢复同一持久 waiting；重复通知/重复 run 不再 wake。wake intent 已落但 runner 未确认时视为原 native 提交不确定，不重新启动。无合格 launcher/session 诚实保留 checkpoint，返回 unavailable。跨 boot 保留既有预算保守拒绝，不宣称支持跨主机/系统重启。

## 旧 sealed unknown 的 G3

`scid-research execution-recover --root INSTANCE --step N` 在同一 host writer 锁下，验证或 reconcile 原 call，并在 host-history/execution-recoveries 追加绑定原 seal、原 unknown row、同一 accepted/reservation 和共同终态的新事实。它不改旧 seal、科学结论、计数、grant 或原 slice。

每个新 job 冻结所消费恢复事实的精确 prefix；旧缺字段按空 prefix 读取，已准备 job 继续使用自己的原 prefix。search 只解除 prefix 内对应 call 的 unknown，不重计 accepted。恢复一个 call 时其他 unknown 继续阻断。lineage 同时正式挂载 retained outputs/native proofs，后继 W 读取新增原件并作新科学判断，A 再判断 screened；执行成功本身不产生 screened。旧 prepared W 不被隐式改写，新增后继节点才能消费新事实。

## 验收与原始记录

所有批次用仓库 serial_lock/run_one 和默认资源监督，无模型、solver、网络后端或并行 pytest。真实 CLI/registered fixture 完成事件和 scripted 原生 launcher 构成工程闭环；不是实际 Codex session 或真实远端服务资格。

| 证据根（均在 /tmp） | 结果 | 说明 |
| --- | --- | --- |
| scid-managed-wait-source-01 / -02 / -03 | 初始夹具失败，原日志保留 | scripted launcher 的 instance 根层级取错，未进入 waiting；没有伪报执行成功 |
| scid-managed-wait-source-04 | 2 passed，10.63s | 新任务单次 run 成功/失败自动 wake 基线 |
| scid-managed-wait-source-05 | 13 passed / 2 failed，46.21s | A/重启/暂停/未知/篡改通过；B 的 CLI success exit-code 遗漏及 fixture 只收 success 两处失败 |
| scid-managed-wait-source-06 | 2 passed，3.16s | B 上述两项窄修复转正 |
| scid-managed-wait-source-final-20261016 | 131 passed / 4 failed，144.21s | 通用交付、nonlocal、预算与原生 fragment 兼容通过；新增 B native proof 挂载相对/绝对路径匹配错误导致四项同根失败 |
| scid-managed-wait-source-final-r2-20261016 | 21 passed / 1 failed，62.61s | B 四项转正；新增 fragment 正控暴露 checkpoint 已发布而原 runner 尚未退出的收尾窗口 |
| scid-managed-wait-source-final-r3-20261016 | 1 passed，6.93s | W terminal 始终等待 exact runner 退出后再 waiting/seal，fragment 窄转正 |
| scid-managed-wait-source-native-guard-20261016 | 2 passed，0.89s | False 返回码/unknown usage 不 query、不建 waiting/checkpoint、不重 submit |
| scid-managed-wait-installed-20261016 | 21 passed，57.60s | 最终冻结代码、fresh wheel、真实 installed plugin entrypoint，全新等待/G3文件完整通过 |

源码 137 个不同案例有通过记录；各源码批包含上述已记录修正，不冒称每批使用同一 hash，也没有测试后重跑无关矩阵。最终 installed 一批使用最终冻结文件集。所有 resource.json 均 cleanup_complete=true；installed build/check 监督用时 3.889s / 58.186s。

每个源码根的 batch-001/pytest.log、resource.json 以及 result.json 保留；源码新正控另在 fixture-logs 保留 native 输出、会话和控制结果。installed 根保留 source 快照、build.py/check.py/supervise.py、build/check 日志与 resource、wheelhouse 和 installed-identity.json。

核心 wheel SHA256：`340383319104eb5093d2487fa51fa3504488cac89cdfde0e3c82a8c4b539d259`。factory 来自隔离 venv 中的 `scid-composed-contract-fixture` 分发，243 个核心源文件与实际安装逐字一致；未从 repo src 回退。执行器终态无假 process/terminal POSIX 回执。

## 覆盖与限制

新 21 项覆盖成功/失败、collect=false native retained proof 实读、continue fragment 在 waiting 期间无新 turn、一个已完成 call 加一个 pending call、同 boot restart、pause、竞争 writer、有限 deadline、无 session 能力、wake intent 后 crash、重复 run/通知、accepted/interface/external/proof 篡改、真 unknown/accepted/submitted 不误当 running、缺 final output 原诊断、未知 native usage/非整数码拒绝等待；旧 seal 的单/双 call 分步恢复、旧 prepared A/W prefix 不变、新节点挂载原件与科学解读、机会计数不增、恢复重复确认、篡改 prefix 拒绝。

复用原 common observation 和 frozen result_protocol；opaque 结果不因 candidate 字段巧合获得本地候选语义。既有两候选科学选择、目录交付、精确重放及 nonlocal/local/cov 原终态约束在源码定向集合通过。目录确认仅证明目录交付，不代表外部服务提交。

没有全量扩测、真实模型/solver、跨 boot 或任意第三方查询 IO 时延资格。本次自动 wake 在已结束 native turn 的原节点边界工作，依赖冻结的合格 same-session transport；不宣称平台能暂停/注入正在生成中的任意真实模型 turn。旧准备节点输入不会追随最新恢复事实变化，须由后继新节点显式消费冻结 prefix。

## 冻结文件

同名 JSON 列出精确 20 文件 SHA：15 个生产文件（新 managed_wait/execution_recovery，及预算、CLI、节点/续接/封存、history/search/lineage 机械接入）、3 个 fixture/tests、ROOTLESS_CLI 用户文档及设计说明。另有本证据 JSON/Markdown。未改归档/provider，实现冻结后仅补本证据文字，等待独立审查。
