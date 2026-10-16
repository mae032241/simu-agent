# TCAD managed 薄接缝设计独立审查

## 结论

**设计 PASS。** 两项预审修订已纳入，无剩余设计阻断。可据此开展计划内无真实远端副作用的实现与 fixture 验收；本结论不启用真实 TCAD，不授予模型、SSH、许可证检查或 solver 权限，也不代替 P3 gate 与后续实现独审。

受审文件：`docs/plans/THIN_TCAD_MANAGED_SEAM_20261016.zh-CN.md`，SHA256 `8ddda0d0873300f7e85500185133d2e3c99385346ad3af692dc8e45c21e6b42e`。参考代码基线 `42e3c7e`；并行 P1 实现和独立容量补修不属于本设计通过范围。未改设计/源码、未运行 pytest/模型/远端工具。

## 核对结果

- **状态保真。** 已对照旧 `TCADExecutionFacade`、socket/command adapter：submit 可以返回 accepted，cancel 先返回 cancelling，原件可以最终 cancelled。设计明确保留这些状态；queued 仅在后端明确提供时使用，不虚构 running。取消虽可归入公共工程未成功分类，仍保留 cancelled 原因/原件，不成为科学否定或资格失败。
- **准入覆盖所有调用者。** 预审发现现 `_dispatch_descriptor` 扫描漏 queued/cancelling；设计现要求 dispatch/admission、query、progress、waiting、history 共用 pending 映射，并增加同 turn/独立 CLI 新 call 拒绝负控。仅等待期间不二次 submit 不能替代这个检查。
- **等待符合现有 native 能力。** 只有 native 正常结束、整数 rc=0、无 stop_reason、usage 已知、raw hash 匹配、原 writer 退出后才建立 checkpoint/waiting。已知失败 Worker 沿原 qualified 续接及预算流程，不自动假挂起/唤醒。没有声称能在未返回的 native turn 中注入挂起；终态后仍先写 wake intent，再启动原 qualified session，未知 wake 不补发。
- **授权先于真实副作用。** P3 来源/独立资格、精确 request/payload、政策或 UI 决策、累计资源 reservation 必须在远端 prepare/upload 前成立，并在 submit 前复核。旧底层 policy admission 不是人类决策证明，package 内 pass 文本也不是正式审查资格。新 grant 不能来自 W 参数或每个修订 package 的新预算池。
- **单一权威与恢复。** 新 Records/预算/历史拥有科研调用事实；旧 submissions.sqlite3 只保存底层幂等 job/retire 事实，不引入影子 Run/ExecutionService/Artifact 预算。lookup None 不证明未提交；retire 需确切 digest 与原子墓碑证明。旧 sealed unknown 走追加恢复及新前缀/正式材料，不改旧 seal、prepared job 或原计数。

## 实施验收边界

必须验证 accepted/queued/cancelling 的真实返回与 pending 准入、cancelled 原因保留、丢提交响应不重派、retire/submit 竞争、collect=false、重复通知/wake、原配置/原件篡改和恢复前缀。真实同 session、跨 boot、SSH/许可证/solver、领域候选与交付映射继续各自报告资格；不能用 fixture 或本设计 PASS 代替。旧 transport/manifest 容量补修单独取证，不由本报告声称完成。
