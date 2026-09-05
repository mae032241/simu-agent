# R5-S S2 Worker 协议设计第二轮独立审查

日期：2026-08-31  
审查者：独立 critic `r5s_s0_independent_review`  
审查候选计划摘要：`5d804bffe5e42c54f32d57126ee8e3ac811d3074d8092df70fbbdf488f6e498e`  
性质：S2 实现前第二轮只读设计审查  
结论：**打回；不得开始 S2 实现**

## 1. 已闭合项

- 208项 S2 起点逐项校验通过；
- 流式 create/patch、大文件传输、服务端状态和字节上限已经完全冻结，首轮两个文件协议阻断关闭；
- 22个 Agent、PDF=7、heartbeat=21、TCAD窄工具/checkpoint=3、analysis/web=0的产品消费者计数准确；
- `AgentLifecycleProtocol` 到 PermissionTemplate/摘要、Task authority、Codex、Router、部署的单向投影
  设计合理；插件生命周期名称碰撞必须失败关闭。

## 2. 剩余阻断

### 2.1 缺少跨 Router/daemon 的 finalizing 恢复

计划只保证同一 Router 重入，但 session token 和完成标记保存在 Router 内存。daemon 重启后新 Router
必须先 open；现有 exact claim 拒绝 finalizing/completed，durable session 重建也拒绝超过原绝对期限，
而 sealed finalization 有独立 hard deadline。seal 后、Task CAS 前崩溃因此无法恢复同一 attempt，违反
`RES-002` 和 `MIG-002`。

最小修正是允许同一 exact dispatch 在新 Router 上恢复原 task/attempt/worker/proxy/authority/session；
finalizing 恢复不创建 session、不延长期限，并可在原绝对期限已过但 finalization hard deadline 尚未
到期时继续；completed 返回同一完成收据。错误 proxy、capability、attempt、authority 必须失败关闭。

### 2.2 checkpoint 删除账本未到底

除工具、组件、服务、角色和 patch contract 外，还需删除：

- 两个 Schema reason 联合中的 `checkpoint`；
- 旧 fallback `WORKER_CAPABILITIES` 中的 `output.checkpoint`；
- activity allowlist 中的 `output_checkpointed`。

计划不应声称保留不存在的泛化“failure snapshot”，而应准确写
`validation_rejected`、`operation_tool_candidate/result` 和 `finalization_candidate`。

## 3. 非阻断改进

web 有插件注册正例；`worker_run_analysis` 没有外部插件正向成功调用测试。若将其保留为支持的插件
接口，S2 应增加外部 fixture 注册与成功调用；否则应退出生产表面。生命周期还应测试跨插件固有名称
碰撞、Schema 摘要改变引起 Operation 摘要改变，以及 Task/Codex/Router/部署投影完全相等。

## 4. 复审门

关闭两项阻断后进行第三轮设计复审。S1 保持通过，S3 继续冻结。
