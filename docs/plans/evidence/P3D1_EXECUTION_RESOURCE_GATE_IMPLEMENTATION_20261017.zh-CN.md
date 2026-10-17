# P3d1 原资源 ledger 与可信执行 gate：实施冻结

状态：**实现冻结，交独立静态审查；未动态验收。P2/P3 最终退出条件尚未满足。** 基于已提交 P3c `309cf67`、P2d `7effe2f`，遵循 [P3c/d 设计](P3CD_EXECUTION_AUTHORITY_DESIGN_20261017.zh-CN.md)及其[设计独审](P3CD_EXECUTION_AUTHORITY_DESIGN_REVIEW_20261017.zh-CN.md)。本节点不实现 P3d2-a 非空输入映射、P3d2-b 长等待后的原调用恢复或 P4 状态/控制/归档。

## 实际公共入口与单一所有权

- `scid-research prepare --enable-formal-review --enable-execution-authority --execution-resource-policy PATH ...` 显式冻结两维有限 allowance（`wall_time_seconds`、`max_storage_bytes`）；必须具有注册 executor。缺资源配置的普通 local 科研不强制进入审批；仅旧 authority 配置仍不是可用执行 gate。
- `scid-research serve-ui --root ... --approval-secret-file ...` 复用同一实例 host。操作者启动时封存 exact canonical regular key locator、key identity 与 HMAC，不复制 key 字节；后续 gate 复核原 key，可不依赖浏览器在线。凭据/locator 不进入 W 科学视图。pending 的 token-free request URL 仅在 endpoint 签名及同一 UI host lock 可验证时返回；管理 bootstrap token 仍只给操作者。
- 真实 native W 的 `experiments.configure → _adapter/freeze/load → dispatch_descriptor → adapter.prepare/Records.accept/submit` 接入 `ExecutionHostServices`。services 只由 core 核 job、native-intent、exact host projection 后构造，JSON 不可选择 gate。显式启用本策略而 adapter 未声明 exact 冻结 `host_execution_gate` 可选合同即在 configure 拒绝；旧忽略 services 的 factory 不能默许通过。无插件名称白名单。
- TCAD managed factory 仅以可信闭包提供原 `execution_admission`，gate 先核本地来源/精确正式 review 后才允许 active policy/capability 查询。非空输入缺 callbacks 的已知 unsupported 在 gate/provider/request/reserve 前拒绝。普通 package pass、模型自报标签、同 hash 异路径均不替代 exact subject/review/授权。
- call allocation 位于同实例 authority 原件 namespace，固定 scope/native attempt/interface/subject/review/显式 payload alias/原 expiry。pending 没有 accepted、reservation 或 backend prepare；同原 attempt/原期限内重试复用请求，不因当前 clock/剩余数改变 request hash。seal/结束或旧 attempt 的旧配置禁止新派发；不借此打开未来恢复合同。
- 人工决定或可信 policy 原件经当前合同、撤销、expiry、policy 与 resource grant revision 复核，原 `budget.py` ledger 原锁原子 reserve 后才返回 prepare 许可。submit 再核 exact request、当前 dispatch、原 prepared/accepted 与 reservation。prepare-intent 写后没有 accepted 的窗口不能证明无副作用，继续占用并禁止盲重放；本版不提供安全 pre-accept 释放。
- owner 为稳定实例身份 + executor；换 package、call、attempt、grant revision 不重置已用/占用。grant/reserve/bind/settle/release 追加到原 control ledger，沿原 seq/parent/settings/boot/锁验证。没有第二资源池或持久 cache。
- 原 `scid-research budget-amend --execution-wall-seconds N --execution-storage-bytes N --authorization-note ...` 是显式有限 ceiling 修订入口，保留既有占用/消费且不产生 exact-call 批准；不与科学 ceiling 参数混用。旧决定不能自动继承新 grant revision。
- terminal 的 canonical `record_observation/verify_observation` 保持原 owner。可选 native resource projection 只覆盖已知 actual 维度，未知维度继续 reserved。仅 P2d 的唯一 `verify_retirement`，并核本 reservation 的 exact authority/call/prepared/accepted，才可释放永久未提交；unknown、lookup None、取消请求、timeout 不退款。

## 四种期限：不同 owner 与消费者

| 期限 | 冻结/所有者 | 消费者及边界 |
| --- | --- | --- |
| native 新派发期限 | 原 native 授权 + 原科学 ledger；allocation 固定 `dispatch_deadline_boottime`/boot/科学 ceiling revision | 首次 allocation、prepare、submit 统一 `_remaining`：实际 runner/native process 匹配、未 seal/结束、原 node/search/shared 授权。此期限约束何时还能派发，不作为远端 solver wall 上限。 |
| 审批请求 expiry | 首次 allocation 的原 dispatch 窗口，固定 UTC `expires_at` | request/decision/prepare/submit；重试不重新授时。过期不可新 submit；UI 决定不自动 submit。 |
| 远端 job 资源范围 | 原显式 execution resource grant + exact 批准 + 全实例适用 shared 剩余；allocation 固定 `job_deadline_boottime` | provider admission 的 job wall 检查和原 reservation；不裁成 W node/search 推理 slice，W 可提交后 sleep，waiting 沿原计量。准备后再核适用剩余，不获得新 grant。 |
| collect / 维护 | collect 首次冻结 `min(原 job deadline, 当前 + runner collection_total_seconds)`；原许可 | collect 重试复用窗口并受当前 shared 剩余及 BOOTTIME stop 限制。query/cancel/retire 不要求 W live、未过 human expiry 或正科学余额；沿原 adapter 的有界维护 RPC，不授新 solver 权限。跨 boot 不延长旧执行 grant；若原 ledger 跨 boot 拒绝写 release，仍可保留 P2d 原生 fence 原件且保占用。 |

本次未动态证明传输/RPC 可抢占性；原 transport 的 timeout/维护边界仍由既有 adapter 实现负责。没有将一个 expires 值复制成所有时限，也没有新增预算授权。

## 静态审查中已修的资源/权限缺陷

1. 公开 `scid-experiment run` 原可用结束 W 留下的 config 进入新 gate；统一新派发检查现在核实际原 native 活跃状态，维护分支豁免。
2. 缺非空输入 resolver 原会先批准/reserve 后必然 unsupported；本地拒绝前移，不烧已知不可执行请求的额度。
3. 显式 authority 不能只靠 typed services 存在推断插件消费；新增冻结可选 gate 合同，旧 factory 不支持即拒绝。
4. resource ledger fold 原可能每 event 再读账，现单次读取并建立本次 ephemeral ref 索引，随后复用；snapshot 不读执行大原件、不触发 settle/release。
5. 可选 projection 原会对每次相同 terminal 再核 outputs/manifest；现在用原 `resource_settle` 的 exact `settled_observation` ref 幂等返回，空 actual 也记已消费原件，仍保未知维度占用。canonical observation 主验证不省略。
6. optional accounting 的普通 `Exception`（含 AttributeError）不改已成功 terminal/CLI 原科学事实；BaseException 不吞。完整 reason 保存原 call 下 `resource-diagnostics` 原件，公开仅 512 字符预览、真实省略数和 diagnostic ref；诊断写失败同样不毁原科学结果。没有把失败记成 actual=0/settled。

以上是静态可达缺陷及代码修复，不是动态性能/OOM 根因结论。

## 最小负控与证明边界（仅编写）

新增 `test_execution_resources.py` 三条：

1. 同实例原 ledger 两请求并发竞争、exact reserve 幂等、旧 grant revision 拒绝、lookup-none 不释放；穿插原 advance/waiting/paused 与实际 budget-amend CLI，检查同 sample 的科学 time/token ceiling 不变、同 owner 修改 ceiling 保留消费，clock event 不成为授权 revision。opaque request/decision refs 仅是账本数学 fixture，不冒充真实 review/批准。
2. 实际 configure 路径拒绝忽略 HostServices 合同的旧 local factory，未产生 accepted。
3. 现有合成 native/formal-review fixture 经真实 controller/seal 路由，hard 模式下公开 dispatch 拒绝已 seal W 的旧配置；provider/prepare 为失败陷阱，未 reserve/accepted。这不证明真实 Codex 身份或 backend 成功。

修改既有 P2c 一个 case：self-contained 包保留默认 factory blocked 断言；非空无 resolver 在 gate 前拒绝，gate 为失败陷阱且 backend events 为空。未删除旧断言、未新增测试矩阵。

重复 observation 快路径、可选投影异常边界及四时限本轮作静态定点复核；尚未动态验证 actual/partial settlement、永久 fence release、跨 boot、并发文件锁、pending 人工等待、真实 HTTP/policy/native/TCAD。未将未运行用例写成通过。

## 精确冻结文件清单

生产 9 个文件：

1. `src/scidiscovery/operations/runtime_plugins.py`
2. `src/scidiscovery/research_loop/budget.py`
3. `src/scidiscovery/research_loop/cli.py`
4. `src/scidiscovery/research_loop/controller.py`
5. `src/scidiscovery/research_loop/contracts.py`
6. `src/scidiscovery/research_loop/execution_authority.py`
7. `src/scidiscovery/research_loop/experiments.py`
8. `src/scidiscovery/research_loop/instance_ui.py`
9. `plugins/tcad_artifact/tcad_artifact/managed_execution.py`

测试 2 个文件：新增 `tests/research_loop/test_execution_resources.py`；修改 `tests/operations/test_runtime_plugin_configuration.py` 的上述单 case。另新增本实施记录。独审报告由 reviewer 单独持有。

未纳入并行 P3d2-a compiler/schema/packager/test 或 P3d2-b 设计文档；没有改 P2d history/recovery/lineage。没有 git add/commit。

## 检查与退出限制

上述 11 个自有 Python 文件已以标准库 `ast.parse` 检查；`git diff --check` 及新文件 no-index whitespace 检查未报错。没有导入项目或执行 pytest/collect、CLI、HTTP、业务子进程、build/install、真实模型或 solver。

这是安全中间态：非空 scientific slots 的 exact sealed original→P2b callbacks 映射，以及人工等待 seal 后显式恢复原 pending call，仍是本计划必需后续节点，不能以永远 blocked 冒称完成。真实 UI/key/native 操作者仍是软信任边界；不抵御同 uid 任意 shell，不把 HMAC/proof 说成 OS 隔离或科学语义认证。当前没有创建真实 key、开启 UI/后端或授予真实执行权限。
