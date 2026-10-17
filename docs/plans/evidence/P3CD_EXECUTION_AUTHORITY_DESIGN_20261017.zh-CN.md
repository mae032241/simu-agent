# P3c/d：精确执行授权与唯一资源 owner 接缝设计

状态：**待独立设计审查；只有静态源码读取，没有实施、凭据创建或动态验收。** 基线 P3a `da87484`、P3b `00cb132`、P2c `4f0a455`、P4a `002284e`。本文不启用真实 TCAD。沿用 [拆分方案](../THIN_P2_P3_IMPLEMENTATION_SPLIT_20261017.zh-CN.md) 与 [P4/P5 接线方案](../THIN_P4_P5_IMPLEMENTATION_NOTES_20261017.zh-CN.md)。P2d 正在设计，本文只消费其最终唯一 validator，不另做 retire 协议。

## 1. 当前真实缺口

1. `experiments._adapter` 由已注册 factory 建立执行实现；`RuntimePluginContext` 目前只有配置/路径，没有可信宿主服务槽。P2c 工厂因此固定不给 `TCADManagedExecution` gate，真实 prepare/upload/submit 默认 blocked。公开 JSON 不能选择 gate。
2. P3a/P3b 已有精确封存原件和 `qualification.output_status` / `formal_review.require_review`，但没有执行请求及 policy/human decision owner，也没有把显式 review ref 带到后继执行绑定的接线。package 内 `review`、普通 A 或 pass 文本都不能补这个缺口。
3. thin 没有可直接复用的审批 server/secret owner。旧 `ApprovalUI` / `ApprovalService` 依赖 Root/session/SQL；`approval_ui` 和 `service` package 的 eager import 不能带入新链。P4a 的 `scidiscovery.browser_access` 可直接复用。
4. 现有 `_dispatch_descriptor` 每次创建随机 call，且 `adapter.prepare` 在 `Records.accept` 之前。只在 prepare 加一个 pending-approval 异常，会使重试换 call、旧决定永远不能匹配；必须先冻结待授权 call 原件，再复用该身份。待授权不是 accepted，更不是 unknown submission。
5. 当前累计执行资源只在旧 ExecutionService SQL owner；thin 的唯一 `budget.py` ledger 尚无 reservation/settlement。不能把插件的 project/input 指纹 `budget_key` 当新累计池。

## 2. 两个串行节点与文件责任

| 节点 | 精确文件责任 | 仍阻断的边界 |
| --- | --- | --- |
| P3c | 新 `research_loop/execution_authority.py`：原实例下 request / decision / revoke 原件及验证；新中立 `execution_security.py`：执行 option、canonical binding、nonce/CSRF/HMAC 纯规则，旧调用方 re-export/适配；新 `research_loop/instance_ui.py`：仅明确实例的 loopback 审批 host；`research_loop/{cli,controller,contracts}.py`：prepare 可选宿主配置、同一个 `serve-ui` 入口、精确 qualification ref 冻结。最小定向测试及证据。 | 不改 P2c factory 为可执行，不写第二预算账，不触发后端 prepare/upload。P4b 后续仅扩展这个相同 host 的状态/控制页，不另建 server/secret/session。 |
| P3d | `research_loop/budget.py`：同一 control-ledger 的 resource grant/reserve/settle/release；`operations/runtime_plugins.py`：默认 None 的非序列化 HostServices 槽；`research_loop/{experiments,execution_authority}.py`：唯一可信注入、固定待授权 call、prepare/submit/collect 接线；P2c `managed_execution.py` 的 factory 只消费该槽及可信 provider，串行协调；P2d 公共 validator 消费。最小负控及证据。 | 完整源码/资格/授权/余额/原件验证任一缺失即 blocked；静态实现与 fixture 不等于真实 TCAD 生产验收。 |

不新增 Root、科研任务注册、adapter registry、模型机械表单或独立预算池。普通 H/W/A/E 和不需要资格的科学执行不加正式 review 必经阶段。新配置只对显式 opt-in 的新实例生效；旧 call 的能力/合同/实现身份不改写。

## 3. 输入来源与 exact review：只读直接原件

安全中间态的第一条可支持路径是**已经封存并明确选中的 self-contained ExecutionPackage 原件**，不作为真实 TCAD 全部输入接缝已完成。非空输入与封存后人工等待恢复必须按第 9 节收口才能满足 P2/P3 退出条件。模型仍选择科学材料，控制层沿现有 job/material 绑定取得 producer step、producer seal、精确 source path、read-copy alias、sha/size；不要求模型填写 hash、subject ID、review receipt。工作区同 hash 文件不自动成为该来源；改过的 package 必须先重新封存并取得其自己的 review。

- 使用 P3a 原件接口核验 exact producer/member，当前 bound request 输入的来源也不能把 restricted/unknown 洗为 clear；只存直接 subject/source-proof/review refs，不把祖先列表复制到每个 job。
- 后继 W job 只从直接 `formal_review_return` / 已冻结的精确 subject qualification 绑定相应显式 review ref；不扫描“最近 pass”。`formal_review.require_review(root, subject, receipt)` 再核当前合同、独立实际参与者和 sealed pass。
- 未声明叶、来源 unknown/restricted、作者身份 unsupported、subject 歧义或缺显式 review，科学结果照常保留；执行不获许可，反馈只有缺口与修复方向。
- `resolved_inputs != []` 当前缺少可信 ArtifactRef→thin 原件映射。第一节点继续 blocked，既不造假 Artifact，也不依 hash 推来源，不让模型补机械 ref。未来只能在同一宿主 owner 冻结 exact slot/ref/native alias/original 的明确映射后启用 P2b callbacks；这不是本轮暗含已完成的能力。
- self-contained 也必须通过全部 gate；package 内 solver capability、DeckReviewReport 和任意 restriction 字段均不是来源/正式审查授权。

保证限于框架明确冻结的输入/成果链。保留 native permissions；任意 shell 外读、同 uid 篡改宿主文件不在硬隔离保证内。

## 4. 唯一 authority owner 与审批 host

`execution_authority.py` 只保留原实例下不可变原件及其 exact refs，不重建旧 Approval/Execution 数据库。request 绑定：实例/settings、原 job/scope/native attempt、固定 call、原执行实现、subject/source/review refs、payload exact 原件、target/config-file proofs、当前 policy snapshot、请求 resource dimensions、稳定 resource owner 与**授权修订锚点**、失效期限。不断增长的 clock/消费 seq 不是授权修订号。

policy/human/revoke 均引用 exact request 原件；decision 不复制全历史。读写幂等以精确原件身份和相同语义为准：同 nonce+同完整决定返回旧 ref；同 nonce+不同选项/理由/actor/extension 拒绝。改 source、subject、review 合同、payload、target、policy 或资源授权修订，必须新 request/decision；旧原件保留。

### 同一个 `serve-ui` 宿主

- CLI 显式 `serve-ui --root <exact-instance> --approval-secret-file <operator-file>`；只绑定 loopback，一个实例 UI lock/boot identity。P4b 将在同一入口扩展状态/控制页；不在此创建完整管理 UI、归档或 Root session。
- 复用现有 secret regular/no-symlink/0600/至少 32 bytes 检查（从 `artifact_agent.runtime.read_secret_file` 抽中立原语后旧路径 re-export），不从 W config/result 接收密钥。此设计阶段不生成密钥。宿主启动的管理链接交用户，交换实例 cookie 后重定向去掉 URL 凭据。
- `BrowserAccessService` 管理浏览会话，重启 boot 使旧 cookie 失效；浏览权限本身不授科学执行。写 decision 同时核实例管理凭据、精确 Host/Origin、CSRF、request nonce/expiry 和注册执行选项。没有 chat/普通 CLI 写 human decision 的入口。
- 纯规则从旧 `execution_approval_option_id`、`execution_decision_authorizes`、subject-set binding、`record_ui_decision` 的 canonical/HMAC 和幂等语义提取；旧 SQL/Artifact refs 留原适配层，不能因旧 schema 要 ArtifactRef 就伪造一个。
- HMAC 封存 decision 绑定 exact request 和完整选项/理由/actor/nonce/UI boot/明确 grant amendment；gate 通过宿主配置的验证原语消费，不能从 public JSON 声明 `authorized=true`。同 uid 任意 shell 可越过文件权限的威胁仍是软隔离限制，不宣称密码学 receipt 抵御已取得宿主密钥的攻击者。
- 审批 handler 只写授权原件；**点击批准不自动 submit、不增加科研节点、不恢复 unknown**。无可用审批 host 时返回明确 pending/unavailable 和原件 ref，不伪造 review_url。已封存决定是否仍有效由原 request/期限/撤销/当前 policy 验证，与旧 cookie 是否有效分开。

## 5. 待授权 call 与真实前后路由

现有 Records 继续唯一拥有 accepted/submission/completed/observation。authority request 的 call allocation 原件在同一 record namespace 的 `authority/` 下，不放入 `calls/`，因此 pending approval 不冒充 accepted，也不触发现有 unknown-call 阻塞。对 exact scope/native attempt + subject/payload/target 绑定，在现有 Records writer/lease 下只分配一次 call；相同请求重试复用，改变绑定分配新请求。不能仅按内容 hash 或“最近 pending”复用。

1. H/W/A/E 仍走原 native 路由；需要正式资格时沿 P3b 显式请求、审查返回普通 A、科学选择后 W 继续。控制层将直接 review ref/subject 原件绑定到 W；模型只选择科学材料和行动。
2. W 用现有 `scid-experiment run --payload <selected-copy>`；宿主解析 exact original、固定 call、freeze request。缺来源/review先给可修复 unavailable，不能先调用远端 policy/capability RPC。
3. 本地资格通过后，可信已注册 plugin 的 `adapter.execution_admission(raw, preparation_profile='tcad.execution-package.v2')` provider 才允许读取实际 active capability/policy。provider 是 factory 闭包，JSON 不能选择。policy deny 直接拒绝；显式 policy allow 写 policy decision；require-human 写 pending request 并反馈完整原件位置/用户 review_url 的紧凑视图。
4. pending 时没有 prepare/upload、accepted、reservation；原 W 可在**原授权期限内**重试相同 `run`，只复用原 call/request。W 也可科学选择 wait/finish；原结果不会因等待审批被改成科学失败。UI 不强迫 W 保持活跃，也不保证人能在原预算到期前批准。
5. **不自动跨 sealed/native attempt 重放待授权调用。** 原 W 已结束或原时间授权失效时，仅批准不启动新工作；下一普通节点可读取精确 pending/decision 反馈，选择同 subject 仍须由控制绑定当前 task/期限的新 request，必要时重新授权。第一版不增加“批准即后台执行旧 W”的新 dispatcher。旧决定保留但不继承到新 job。若产品需要长时人工等待后的 same-call 继续，必须另审现有恢复入口的确切扩展；本设计不假称已支持。
6. 有效 decision 后同原 call 经过 P3d reserve，才进入原 adapter.prepare→Records.accept→dispatch lease→submit。submit 再验原 request/target/policy/grant revision/revoke 与 reservation。原 call unknown 只 query/reconcile/P2d retire，不自动再次 submit。

## 6. P3d 只扩原 control-ledger

`budget.py` 继续独占 `_ledger_writer` 与 `_append`；新增受校验的 resource grant/reserve/settle/release event，使用同一原 settings identity、seq/parent 链和 writer 锁。authority 不写第二份余额，P2 wrapper 不写资源账。

最小语义接口（不是新增通用注册框架）：

- `reserve_execution(root, *, owner, call_binding, request_ref, decision_ref, budget, grant_revision)`：锁内重验稳定 owner/当前授权修订及累计余额；精确同 reservation 重复调用返回原 ref，不新增消费；不同请求不能借同 call 重新取额度。
- `settle_execution(root, *, reservation_ref, observation_ref, consumed)`：仅验证过的同 call 终态原件和可信 adapter 资源投影；已证 actual 覆盖对应 reserved 维度，缺失/unknown 维度继续占用原 reservation；重复不退款、冲突不覆盖。
- `release_execution(root, *, reservation_ref, retirement_ref)`：只调用 P2d 最终唯一 `experiments.verify_retirement`，消费永久未提交 fence；没有 external ID 也无需伪造 terminal observation。unknown、lookup None、cancel request、timeout 都不是 release proof。found 原 job 则沿原 query/cancel/终态结算。
- `amend_execution_grant(root, *, owner, before_revision, decision_ref, allowance)`：明确宿主/UI grant amendment，保留历史消费。普通 authorize 不隐含增加累计额度。

稳定 owner 来自原实例 scientific execution owner + executor，不按 package/request/revision/attempt 生成新池。先支持现有 policy 的 `wall_time_seconds` / `max_storage_bytes`，不用新 CPU/license 矩阵。prepare 显式冻结操作者资源 ceiling；实际 admin policy 限额与该 grant 共同约束。没有有限授权字段不发默认额度。

复用旧 ExecutionService 数学：每维使用 `{**reserved, **known_actual}`；unknown 不能按零消费；只明确从未提交永久 fence 才 release。当前 policy 收紧在 prepare/submit 再查；累计余额在 reserve 锁内重算。原科学 max_seconds/max_tokens、已接受执行等待及 CollectionContext 截止继续有效，不用资源 grant 延长原总时间。

reserve 必须在任何 prepare/upload 前持久化；不持 ledger 锁做远端 RPC。request/decision 原件先写，锁内校验其 exact ref 和授权修订、append reservation，再进入 prepare。崩溃保留 reservation，重试按原 request 修复投影；不宣称多个文件有跨文件事务。prepare/accept/submit 之间失败如果不能由 P2d 证明永久未提交，就仍保留 reservation。特别是 reserve 已写、Records.accept 尚无原件的窗口，P2d 若只支持 accepted call 就明确标 `pre_accept_release_unsupported` 并继续占用；不得伪造 accepted 或 retirement 来退款。安全的 pre-accept 释放必须另审，不能顺手增加第二通道。

collect 只取原授权和现有剩余截止，复用 `CollectionContext` / `collection_context`；不通过 `for_seconds` 在每次 query/collect 续发窗口。终态资源只从可信 manifest/owner 验证投影取已知维度，模型报告不结算；完整原件保留，反馈只给紧凑余额/资格/原件 refs。

## 7. 唯一 factory 注入点

`RuntimePluginContext` 加默认 None 的非 JSON typed `execution_host_services`。只在 `experiments._adapter` 核验原 job/native-intent、exact host projection 和原 registered implementation 后由 core 构造；public operator configuration 拒绝同名保留字段。插件没有按 JSON import 任意 gate 的入口。

该服务只提供绑定当前原件的 gate / policy-provider 接线及将来 exact input callbacks；不是工具服务 registry。factory 用自己已注册 underlying adapter 的 provider 闭包接入，gate先核本地资格再调用 provider。与 trim 已确认此接缝；本轮 P2c 工厂仍 blocked。

freeze 与运行 load 必须获得相同**声明**的 HostServices 形状；缺 UI/资格/余额由 gate 动态拒绝，不在 freeze 后改变 capabilities 的 `production` 值，避免 P1 frozen-capability 原件漂移。旧没有声明的配置保持原 None/blocked，不替旧 call 补能力。

**共通实现身份由 core 自动绑定。** 适用的新 freeze 除现有 experiments/breadth/execution_status/replay_check 外，自动加入实际 gate 行为的 `execution_authority.py`、中立 `execution_security.py`、`budget.py`、`qualification.py`、`formal_review.py`、`provenance_rules.py` 和 HostServices 定义文件的 exact implementation proofs；不得要求每个插件手工列框架 helper。request 再绑定此次适用的完整实现 proof 集，consume/load/submit 核对相同原件字节与版本；UI 封存决定同时绑定其 `instance_ui.py`/`browser_access.py` 安全实现 proofs。仅有文件名或对象形状不够。旧无声明配置保持 blocked、不补写旧 capability/request。最小实际依赖集在实施时沿 import/调用链定点核验，若 helper 被抽走，proof 随真实行为迁移，不能留下未绑定的授权行为。

## 8. 最小负控与未验收项

仅编写真实路径的小量负控，不运行：

1. exact 来源/subject/review/target 任一替换、同 hash 不同 source、普通 A/package pass 不授资格；无资格需求普通科研不阻断。
2. JSON forged services/authorized/decision、错实例/Origin/CSRF/nonce、过期决定、同 nonce 异内容；重启浏览 cookie 失效但历史决定不被删除。
3. human pending 前零 prepare/upload/reserve；原 call exact 重试复用、改 payload 不继承、sealed/新 attempt 不自动重放。
4. 同余额竞争及同 reservation 重复、revision 新 package 不重置 owner；unknown/lookup None/cancel request 不退款；P2d permanent fence 可一次 release；terminal 缺一个 actual 维度仍占用该维 reservation。
5. 缺 services、缺 finite grant、非空 resolved_inputs 缺 exact mapping 皆 blocked；policy/grant 收紧后旧 decision 不能 submit；collect 不续发时间。

未动态执行 HTTP/浏览器、真实身份/模型、进程、pytest/collect、import、安装/build、SSH/solver 或真实授权。HMAC/路径封存与静态设计不代表 OS 级不可伪造、平台身份完整、真实 TCAD 或生产恢复已验收。

## 9. P2/P3 最终退出前的必需闭环

P3c 原件/同一 UI host、P3d1 ledger/gate 是可独审的安全中间节点。下面两项属于**同一 P2/P3 计划的必需后续串行集成**，不是永久 unsupported 便可标记生产接缝完成；在具体合同与真实入口另审通过前继续 blocked。

### P3d2-a：非空输入的控制生成映射

控制从明确科学 slot 选择及当前 bound sealed materials，冻结 `semantic_name + target_relative_path → exact producer seal/member + native alias/original proof`；歧义、未选中、同 hash 不同 source 一律不猜。模型只提供科学语义名及材料选择，不填写 storage、hash 或机械 ref。控制生成 package 的机械 binding，并将 package + 映射整体绑定到 exact review subject；输入改变即新 subject/review/request，不在已有 pass 后悄悄补输入。

P2b 两 callbacks 只接受该局部映射中的完整 item identity，metadata/open 都沿同一 host 原件 validator，不扫 CAS/工作区或凭 sha 搜索。原件完整映射保留，模型只见紧凑科学 slot 视图。P3a 同时把这些精确输入列为直接依赖，不因代码 package 自身 clear 就忽略其输入限制。

当前 v2 `ResolvedProjectInput.artifact_ref` 只有 id/sha/kind/schema；须先由独审确认，有明确 host 原件 owner 的 execution-local alias 是否诚实满足该引用合同。如果其语义必须来自旧 Artifact owner，就使用最小有版本的 native-original ref 输入合同并复用同一 P2b materializer 纯拷贝规则，不能构造虚假旧 Artifact/Service/存储。该合同选择是实现前必决事项，本文不批准任选两套运行路径。插件修改由原 P2 owner 协调串行接入，不抢改已冻结 P2 文件。

### P3d2-b：人工等待后的显式原 call 恢复

人工决定到达时原 W 已封存，不能要求模型重填 subject/hash，也不能把新 W 当旧 W、重新授时或修改原 sealed observations。必须沿现有 append-only recovery 前缀/原 call lease 做窄扩展：显式操作者动作引用原 pending request，控制核 exact 原 scope/payload/decision、当前仍有效的原实例授权及剩余资源，再恢复**已确定尚未 prepare/dispatch 的原 call**；原 native 不重跑。UI 后续调用同一控制函数，不能维护另一执行队列。

恢复 owner 必须先证明当前是 pending-not-prepared，而不是以缺文件/lookup None 推定未提交。出现原 prepared/dispatch intent 或不确定结果时，转原 query/reconcile/P2d 协议，绝不走新 submit。已封存科研原件不改；后来执行事实在同一 recovery owner 下追加，后继节点冻结其精确 recovery prefix。具体公共函数/CLI 形状须与 P2d 最终 recovery/disposition 接缝统一独审，不能在 P3 另造 dispatcher。原授权已过期或余额不足保持 blocked；人已批准不等于获得新预算。

两项闭环与真实生产接线验证未完成时，实施记录必须写“P3d 安全中间态，P2/P3 退出条件未满足”，不得写整体完成或生产已验收。
