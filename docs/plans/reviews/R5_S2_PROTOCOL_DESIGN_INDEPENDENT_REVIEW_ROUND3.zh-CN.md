# R5-S S2 Worker 协议设计第三轮独立审查

日期：2026-08-31  
审查者：独立 critic `r5s_s0_independent_review`  
审查候选计划摘要：`5b5b3c0dc874c8b7489b776d5d0862b657f2ce0f2a3a5c0755860dcb4cc791e4`  
性质：S2 实现前第三轮只读设计审查  
结论：**通过；只放行 S2 实现**

## 1. 通过结论

S2 起点清单共208项、摘要 `96740af4dcce821dc376adfb41e9f8bd5cf026a566c7bc8e2b4caf3d67347e53`，
逐项校验通过。流式 create/patch 和1 MiB传输边界完整冻结。

跨 Router/daemon 恢复现已限定为同一 exact dispatch 和原持久 session，task、attempt、worker、
proxy、authority、session 全绑定；不创建 session、不延长期限。原 absolute 已过时，只能在既有
finalization hard deadline 内继续 submit；恢复态禁止编辑、heartbeat 和领域工具；completed 只
投影现有完成状态，不新增完成收据权威。错误绑定和过期 hard deadline 均失败关闭。

checkpoint 删除范围已经覆盖工具、组件、服务方法、两份角色、物化 patch contract、两个 Schema
reason、fallback capability 和 activity allowlist；自动保留的 reason 与代码一致。

`AgentLifecycleProtocol` 的唯一投影、插件同名碰撞、ABI/Schema 摘要变化、Task/Codex/Router/部署
四方一致以及 analysis 外部 fixture 成功调用均进入实现验收。设计没有新增表、任务终态、注册表、
通用 action 联合体或领域分支，符合33项约束与奥卡姆原则。

## 2. 实现硬门

S2 实现审查必须包含真实 daemon 重启测试，覆盖 seal 后、Artifact 登记后 CAS 前和 completed 响应
丢失；同进程 Router 单测不能替代。S2 通过前不得进入 S3、S4—S6、H7 或发布冻结。
