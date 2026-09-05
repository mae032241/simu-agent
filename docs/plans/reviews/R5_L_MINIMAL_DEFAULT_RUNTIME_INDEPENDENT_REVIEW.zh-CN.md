# R5-L 最小默认运行主干独立审查

日期：2026-08-31  
审查者：`r5s_s0_independent_review`（未参与候选编写）  
候选摘要：`51a1f802c623f2e15b8c5175bd42d7e5e54550526ac61a95e4f24a2bea20d6a6`  
结论：**打回**

## 1. 总体判断

两级后端方向可取。保留最小 `ResearchInstance/CurrentBinding` 也正确；current 应是显式 CAS head，
不表示资格，checkpoint 不能晋级 current。但候选尚未闭合唯一 Run 权威、递归 currentness、恢复
草稿、TCAD 工具上下文和安全边界，当前不能进入实现。

## 2. 阻断项

1. **两后端可能形成两套终态权威。** 共同接口没有规定谁独占完整校验、Artifact 登记、Run 终态、
   current CAS、reviewer 创建和完成收据；现有 Hardened 路径的 `TaskService` 已经自行登记 Artifact
   并完成 Task。必须明确 Run 是 Task 的瘦身后继，唯一 RunService 拥有全部科学终态；后端只能
   返回不可变 `SealedWorkspace`。
2. **current 只做直接 CAS，不足以拒绝 stale 后代。** 必须冻结 requires-current 输入及其生产父链，
   preflight、submit 和 downstream admission 共用递归 currentness。Artifact 可先幂等登记，但
   `Run completed + head CAS 结果` 必须在一个控制事务中落地；CAS 失败以
   `head_advance=stale_rejected` 完成，不能由查询补写。
3. **恢复快照没有写入者隔离和认识论类型。** 原 Run 必须先 CAS failed 并关闭启动槽，后端证明旧
   写入者停止或隔离目录后才冻结；旧 submit 一律拒绝。快照是 backend-private、内容寻址的
   `recovery_draft`，不能成为普通输入、证据、ReviewGate、PromotionPolicy 或 CurrentBinding。
4. **TCAD 调试仍硬依赖 TaskService/session/capability/provisional snapshot。** 必须先冻结后端无关的
   `OperationToolContext`，只暴露任务输入、工作区、候选快照、开发结果和有界 activity；Local 与
   Hardened 分别投影该接口，插件看不到 Run/Task/session/token 身份。
5. **LocalTrustedBackend 不能被条件化为符合 SEC-002。** 它只能是可信本地开发 profile；领域 MCP
   仍需服务端门禁，submit 仍拒绝越界、秘密、机器路径、未声明二进制和超限输出，不能携带生产
   凭证、远程执行或不可逆 Effect。发布不得声称 33 项全部 conformant。
6. **加固路径缺少持续防腐门。** L0 必须冻结其符号、入口、状态和恢复测试；L1—L4 每阶段至少运行
   编译、安装和关键负例。L6 必须以默认 wheel 不启动/导入加固路径、唯一 Run 权威和零默认消费者
   为删除门，不能只以行数判断。

## 3. 非阻断建议

- 盲插件 250 行是观测指标，还应同时记录文件数、重复声明数和必填字段数；
- ReviewGate 只读精确 reviewer Artifact，不维护第二 review 状态；
- current 可以在 reviewer 前推进，因为 current 不等于资格；需要审查的下游必须显式声明门；
- 不要用“必须只有五个状态”代替消费者和不变量论证。

## 4. 复审通过条件

候选逐项落实上述六个阻断项，并保持：一个 Catalog、一个 preflight/invoke、一个 RunService 科学终态
权威；两种后端只是工作区/传输实现；current 与 recovery draft 不互换；TCAD 通过同一工具上下文；
可信本地 profile 如实保持 `SEC-002 known_issue`。修订后必须重新独立审查，不继承本轮结论。
