# P2d 原调用永久未提交证明：实施候选

状态：**待独审，未实施。** 日期：2026-10-17。基线 P2c `4f0a455`、P5 `3ac974d`。依据[主计划](../THIN_CAPABILITY_MIGRATION_20261016.zh-CN.md)、[已审 seam](../THIN_TCAD_MANAGED_SEAM_20261016.zh-CN.md)及[拆分设计](../THIN_P2_P3_IMPLEMENTATION_SPLIT_20261017.zh-CN.md)。本文补全 P2d 消费语义，不启用真实 TCAD；P3 gate、预算和来源接线仍分别由其 owner 实施。

## 独立事实，不冒充已执行终态

永久未提交是原 call 的独立控制事实，唯一原件为 `calls/<call_id>/submission-retirement.json`。不生成 external ID、submission、native manifest、completed 或 execution-observation，不把未提交称为 native failed/cancelled，不更改旧 accepted/dispatch intent/科学 seal。

共同公开投影使用 **`status='not_submitted'`**，只在该原件通过统一验证后出现；它表示明确没有运行过的原调用，不参加 native `execution_status` 的终态映射，不产生科学否定、候选或 metrics。缺失证明仍 unknown；证明被篡改报 integrity error。明确新增这个受证明保护的 disposition，避免把永久未提交塞进已执行终态合同或使有证据的原 call 永久卡在 unknown。

## 可选能力与实际后端复用

managed wrapper 声明一个 `AdapterCapability`，key 为 `original_submission_retirement`，合同为 `scidiscovery.permanent-submission-retirement.v1`，明确支持同原 prepared digest 的永久 fencing、found 时只回到原 job、缺回执不证明未提交。复用现有 capability bytes/metadata/code 的冻结机制；不向 LifecycleCapabilities 加字段。缺该冻结声明或缺可选方法即 unavailable，不通过试调用后端推断能力，不让旧 call 追认新能力。

可选方法 `retire_original(call_id)` 仅由可信宿主原调用入口触发，其精确调用合同是 **context manager**：core 必须 `with adapter.retire_original(call_id) as evidence:`，在 with 内验证并封存共同 receipt。wrapper 复用原 gate 的 retire/cancel 权限、原 prepared、既有 `tcad_retire_submission`/transport `retire_submission`。两底层 adapter 新增窄 `retire_submission_details(descriptor)`，保留经现有 `_call` 验证的完整响应；旧 `retire_submission` 继续适配 tuple/None。需要保留协议证明时让既有 `validate_submission_protocol` 成功返回其已核验的原响应（旧忽略返回值的消费者不变），不新增 runner、SSH 或提交协议。

| 实际响应 | 控制动作 |
| --- | --- |
| found=true，精确原 prepared 对应同 external ID | 保留原返回事实、核同 ID 并通过 Records.bind_external；仅按原 cancel 权限取消该 job，之后沿既有 native query/manifest/observation 路径。已有终态不伪造新取消。 |
| found=false，retired=true，submission_sha256 等于原 prepared，且永久协议成立 | 封存同 call 永久未提交证明；必须没有曾绑定的 external/submission/已执行终态。若本地已有 job 事实则矛盾拒绝，不能用丢失的后端库洗成 never submitted。 |
| lookup None、busy、timeout、缺字段/协议、响应丢失 | 无永久未提交结论；保留原 accepted/intent/reservation，不重 submit、不清 unknown、不退款。实际 retire 可能成功但回执丢失时，只能重查/同 digest 幂等 retire。 |

原 backend 的 exact digest 原子锁与永久 tombstone 已存在，继续复用；retire 与同 digest submit 竞争的互斥由该后端协议负责。旧无协议调用不能通过配置开关升级，旧已封存结论也不改写。

本地 wrapper 的 submit/retire 共用同 call 的非阻塞 Records lease，保护原 intent/retirement 封存的一致性；backend 调用仍用原有有界请求，不占 node 的 accepted 短锁。retire context 从 raw 退役调用/保存开始，贯穿 core 共同 receipt 验证、Records 发布及重复原件对照，直到 core 完成消费才退出；不能先返回并释放 lease 再封存。永久 proof 已落时，任何迟到的 fresh submit 在写新 intent 前拒绝；原 intent 从无到有的竞态不能让已封存的“无 intent”快照失效。锁忙返回 unknown，保原件，不推 absence。控制崩溃/外部 RPC 仍在进行时，最终顺序以 backend 的同 digest 原子协议为准，不以本地 lease 推未提交。

该 call lease 的 owner 是 wrapper：submit 方法持有它；retire 方法返回的 context manager持有它跨越 yield。core 只消费该 context，不再获取同一个非重入锁；Records.publish 不取 node accepted 短锁。没有新增全局锁或把 backend IO放入 Records.accept 临界区。

## 唯一证明合同与 validator

共同入口候选：

```python
verify_retirement(value, original_loader, *, interface=None) -> dict
```

置于 `research_loop/experiments.py`，与 verify_observation 同样只核原件，不 live query/发授权。它返回已验证的 call/prepared/accepted/authority 绑定；准入、history、recovery、P3d 均调用它，不各写一套解除 unknown 规则。

receipt 必备：版本、kind=`permanent_not_submitted`、call_id、scope、native_attempt、mechanism_binding、冻结 interface、accepted proof、完整原 prepared descriptor、原派发 intent proof（或核实该 call 从无 intent）、原 authority receipt ref、冻结可选 capability 合同及 hash、原退役 request/完整 response/永久协议回执 proof。请求绑定原 prepared digest/冻结目标；响应必须明确 found=false/retired=true/同 digest。所有 proof 验实际字节；不接受 W 传来的任意 JSON、当前最新配置或同 hash 的另一原件替代。

core 在原 adapter 可选方法返回且原件核验后，通过同 Records call namespace 封存该共同 receipt。准入/预算只认可这个宿主 owner 路径及其精确 accepted/authority 链；adapter 原始回执本身、模型的声明或聊天不能直接 release。native raw proof 与共同 receipt 均保留，不用 normalized 布尔值替换原响应。重复操作核原相同原件，不能覆写；调用失败保 accepted/intent 和已保留 raw，不留伪成功共同 receipt。

## 精确消费者及文件责任

| 文件 | 最小变化 |
| --- | --- |
| `plugins/tcad_artifact/tcad_artifact/managed_execution.py` | 可选 capability/retire_original、原 gate/target/prepared核验、保存原始退役回执；found 回原 job/cancel，permanent absent 返回独立事实，不造 completed。 |
| 同插件 `execution_adapter.py`、`command_adapter.py` | details 接缝与已验证协议回执返回；旧接口适配，無新 transport/runner。 |
| `src/scidiscovery/research_loop/experiments.py` | 唯一 verify_retirement、同 Records 原件发布、显式 `retire` 原调用命令；准入扫描在 state 判定前核独立永久证明并跳过该原 call 的 unknown 阻塞。progress 投影 not_submitted；缺 capability 不猜后端。 |
| `research_loop/history.py` | 独立 retirement proof 和全部 native proof 归档；not_submitted 行不得含 completed/terminal/observation/执行输出，统一 validator核身份。原已执行终态格式保持。 |
| `research_loop/execution_recovery.py` | 旧 sealed unknown 可追加同 call 的 retirement recovery，仍绑定旧 accepted/scope/mechanism/seal/old-row hash；新 job 冻结该恢复前缀，不修改旧 seal。沿同 validator，不额外调用 retire/submit。 |
| `research_loop/lineage.py` | 让该独立 disposition/证明在原 A/history 页可见；retirement recovery 不索取不存在的 native observation/outputs，不造科学 candidate。 |
| P3d `budget.py`（**由 P3d owner 修改**） | 只消费上述 validator 认可的原 receipt ref，绑定原 reservation/authority/call/prepared后幂等 release；P2不写余额。 |

`search.py` 当前以 unknown 且未 recovered 判断阻塞，not_submitted 可沿既有验证后恢复前缀自然解除；原 accepted 调用/科研机会计数保持，不能把未执行自动退还为新 call 配额。若静态实现发现需要 search 的小投影修补，应先报告 root；不加入第二条清阻路径。generic candidate 只认 known_success，not_submitted 不授资格。

未绑定 external 的永久退役不会进入既有 managed waiting；found job 继续原 pending/cancelled 路径，因而不改 managed_wait/continuation。不新增科研状态账、Root、授权库或预算池。

## 跨 boot、期限与预算 owner

永久证明依赖同冻结目标下已经持久化的 backend fence，不依赖“等待够久”、当前 boot 时钟或进程退出推测。只认可协议提供的持久 tombstone；丢目标身份、原实现、协议或原权限则 unsupported。跨 boot 只读取原永久事实，不延长原 solver grant，不重新 submit；调用新的 retire 仍需原管理权限。不能声称已动态验证真实后端掉电持久性或混合版本老提交者安全。

P3d 单独决定资源 release/settlement，使用稳定原 reservation；found、cancel 请求、unknown 用量、lookup None 均不退款。验证过的永久未提交可解除该 call 的不确定性，但后继执行仍须当前 P3 gate、剩余预算及科研机会；证明不授新额度。只存在一个 release owner，P2 不从状态字符串直接改预算。

## 最小负控与验收限制

- 真正可选：旧 adapter 缺声明/方法时 unavailable，原 capability hash/实现变更拒绝，不影响已有无可选能力路径。
- 精确身份：错 call/scope/prepared/authority/target/response digest/回执字节、已有 external却声称 never submitted均拒绝；不得靠自报 permanent 放行。
- 原子语义：同 digest submit/retire 的 fake backend竞争只可得到 found 或永久 fenced；retire 回执丢失、busy/timeout/lookup None保 unknown且 submit 次数不增。只写最小可信依赖注入，不建旧 Root fixture。
- 重入：重复读取已封存永久 proof 不再 RPC/submit/release；found 绑定原 job 后按原权限取消，无假 external，已 cancelling/terminal 不重复取消；不同状态的原查询不能覆写初次回执。取消回执不确定只保原 job，不能把它视为未提交或退款。
- 真实消费者：同 node 的 unknown准入→永久证明→不再由该 call 阻塞；旧 sealed unknown→追加恢复前缀→A可见 not_submitted；篡改恢复 proof拒绝，旧 seal/计数/候选不改。P3d用同 validator 的错 ref/重复 release负控归其 owner。

只静态文本/AST/patch检查；本设计没有运行测试、导入项目、CLI/进程、build/install、模型、SSH、许可证或 solver。真实并发、掉电/跨 boot、安装元数据、权限隔离和 live solver仍未验收。独审设计及每个实现小节点通过均不能单独启用真实 TCAD。
