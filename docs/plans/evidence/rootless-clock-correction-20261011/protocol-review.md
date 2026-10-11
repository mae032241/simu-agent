# 真实验收冻结协议独立审查

日期：2026-10-11。审查者：n_plan_review（未编写执行脚本或生产实现）。结论：**PASS，仅限启动协议**。

已核验：

- 冻结源码为 `19f3e9f8a897a5925126827de95299b08a7b63b7`；最终 wheel SHA256 为 `d72aa7e3485eff75186147a753c49fbc541ac8d9da1eb0b28defbf178c62a231`。安装的 8 个 research_loop 模块与 wheel、冻结源码逐字节一致，CLI 使用该 venv。
- 两实例分别冻结 6,000,000 token、3,600 active 秒、24 节点，模型 `gpt-6.1-sol` / `high` / `default`；settings identity 有效。核对时两实例均无 job、native intent 或预算修订账本。
- 两场使用相同公开题目、observer 与隔离 wrapper；native 0.162.1 及 code-mode-host 哈希与 launcher 配置相符。公开题目 manifest、脚本、两场 settings/identity、wheel、observer、launcher 与 objective 纳入冻结清单；16 项哈希核对通过，最后脚本分支修订的哈希再次核对。
- 脚本持共享 serial lock 串行运行，仅 case-02 / case-03；已有 live02 计第一场，无自动补场或扩额。case-02 观察首个 W 的 native-process，确认 outcome/seal 尚未出现并记录进程身份后请求 pause；已接受工作继续执行，控制器返回 paused 且退出码为 0 后，间隔 5 秒以新控制器 continue。case-03 正常运行。
- 非零退出、error 或无法解析终态停止整组；paused 的恢复分支亦要求退出码为 0。started 标记防止自动重复整场。

限制：这是配置和协议的只读检查，未运行模型、训练或评分，也不判定两场已通过。暂停是否确实发生在首 W 活动期间、W 是否封存、预算是否连续及有无重放，须依据实际事件和封存证据判定。usage 可能延迟，6M 是控制层观测预算，不能宣称精确账单硬上限。隔离结论沿用已测 wrapper 的具体路径边界；可信 host observer 的权限本身不构成隐藏评分隔离证明。隐藏评分仅可在独立环境完成，不回流科学角色。live02 的源码/native/计时口径不同，不作为同版本重复或新恢复机制通过证据。
