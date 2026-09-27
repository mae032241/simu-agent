# R5-S S2 Worker 协议设计独立审查

日期：2026-08-31  
审查者：独立 critic `r5s_s0_independent_review`  
审查候选计划摘要：`e1dafdb5d355a70491cc14ce06b39e62334be8f17c547c3397d18f68a7f9b815`  
性质：S2 实现前只读设计与消费者审查  
结论：**打回；不得开始 S2 实现**

## 1. 阻断项

### 1.1 单次文件写无法通过现有传输边界

Unix Socket JSON-RPC 完整请求固定限制为1 MiB；TCAD workspace policy 允许单个源码、
`project.json` 和 `declarations.json` 达8 MiB，部分科学主输出合同达2 MiB。2 MiB UTF-8 请求已约
2,097,314字节，base64约2,796,368字节；8 MiB分别约8,388,770和11,184,976字节，都会在到达
Worker Router 前被拒绝。提高 Socket 上限也不能消除模型输出、重试和超时风险。

因此不能用单次 `worker_file_write` 取代有界流式通道。最小修复是 S2 不动现有文件协议；若未来
重整，也必须保留分块、服务端状态、幂等重试和最终原子发布，并增加真实 Socket 大文件回归。

### 1.2 三段通道还承担大补丁

`begin` 的 `operation` 同时支持 create 和 patch；服务端允许分块补丁高于单次64 KiB patch 上限，
通用角色提示也明确要求大补丁走该通道。TCAD 可编辑文本文件可达8 MiB。删除三段通道会使合法
大修订不可表达，且 required 文件不能通过 delete/create 覆盖。

### 1.3 固有生命周期还没有唯一编译权威

生命周期事实当前会影响 PermissionTemplate、摘要、Task authority、Codex profile、Router、提示和
部署探针。若各处分别硬编码 open/heartbeat/submit，会重新形成分散注册表。计划必须先冻结一个
最小 `AgentLifecycleProtocol` 编译对象，包含版本、工具名、输入 Schema 身份和 capability；所有
下游只读这一投影，插件不能覆盖固有名称，协议变化必须改变 Agent Operation 摘要。

### 1.4 消费者账本和 checkpoint 合同不完整

精确产品消费者为：22个 Agent 使用 materialize、三段写、text patch、validate、finalize；21个使用
heartbeat；3个 TCAD author 使用 JSON patch/delete/move/checkpoint；PDF 为7个；Python analysis 和
web evidence 当前正式 Operation 均为0个，只作为插件扩展能力和测试表面保留。

checkpoint 虽无真实调用，但 TCAD author 提示和 materialized `patch_contract` 仍要求它。删除工具时
必须同步删除或替换这些模型可见语义，并验证 assignment 不再出现退休名称；自动 rejected、工具
结果、finalization candidate 和失败 snapshot 必须保留。

## 2. 可保留的设计结论

Worker 可见的 validate/finalize 可以合成 submit，但内部必须继续执行完整校验、provisional
finalization candidate、seal、finalizing、幂等 Artifact 登记和 Task CAS。复审必须增加校验失败后
修正、seal 前后崩溃、CAS 前后响应丢失、重复 submit、finalizing 超时、下一 attempt 恢复和 proxy
停止续租测试。

text patch 与 TCAD JSON patch/delete/move 不应机械合成通用 action 联合体；删除完整 checkpoint
语义也合理。方向符合快速闭环和33项约束，阻断在传输可实现性、消费者遗漏和单一编译权威。

## 3. 复审条件

先修订计划的 S2 消费者账本和协议边界，闭合以上四项；独立复审通过后才能开始 S2 实现。S1 保持
通过，S3 不放行。
