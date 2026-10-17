# P3d2-b 迟批恢复实施账

状态：**实现已接公共入口，待独立代码审查；未提交、未动态验收。** 依据设计提交 `e75623c` 及其[独审](P3D2B_LATE_DECISION_RECOVERY_DESIGN_REVIEW_20261017.zh-CN.md)。继承[主计划](../THIN_CAPABILITY_MIGRATION_20261016.zh-CN.md)、[TCAD seam](../THIN_TCAD_MANAGED_SEAM_20261016.zh-CN.md)的生产资格限制，不声称真实 native、UI、跨 boot、掉电或远端执行已验收。

## 单条实际顺序与失败后果

公共 `execution-resume` → controller 原 `host-run.lock` → authority 同 owner `execution_resume.py`；没有新调度循环、任务/身份库或预算 owner。

| 顺序 | 当前实际动作 | 失败后留下什么、能否重试 |
| --- | --- | --- |
| 1 | 精确原 seal/pending-set/allocation/config/实现核验；当前有限 host operation receipt、原 boot/ceiling 与绝对截止；拒其他活/unknown owner | 未开始准备；不造 accepted/终态。缺原正向证明永不 fresh；当前证据错误待修复。 |
| 2 | 现有 factory 的可信 provider 核当前 profile/policy；原 exact review/来源/target、当前科学机会与共享剩余；有效 exact 决定复用 | 缺决定只留 operation/request。过期须显式有限 validity 的 successor，旧 request/decision 不改；重读同 successor 不刷新 TTL。无 resume_intent、不 unknown 计费。 |
| 3 | `reserve_execution` 原子检查累计余额，或经原件验证追加同 ID authority-rebind；不退旧额、不新建 reservation | 不足额或重绑拒绝时没有派发 intent。reserve→intent 窗口若中断，同正向无 prepare 证明下复用原 reservation；原余额仍扣住。 |
| 4 | `remaining()` 再核本次窗口；同 authority writer 内 `recovery.begin` 发布不可重放 intent，再写 prepare-intent | **只有 reserve/重绑成功、剩余通过才发布 intent。** intent 后任意中断均 unknown，不重获 fresh lease；不以缺 accepted 推未派发。 |
| 5 | 原 wrapper.prepare → 原 Records.accept（当前可信恢复准入，原 mechanism）→ 同调用 lease → 原 submit；接受后立即追加 accepted | prepare/accept/submit 失败保原件/reservation；accepted 只算一次。submit 响应未知只保原身份，后续 lookup/query，绝不 submit 重放。 |
| 6 | 同 recovery ref 链追加真正状态/统一 observation/P2d retirement；history/search/lineage 只派生副本 | 无 verified observation 不终态。raw queued/cancelling/cancelled 保留；lookup None 不清阻、不退款。终态不减机会，余额 settle/release 只走旧 ledger owner。 |

同 `CollectionContext` 由 operation receipt 的**绝对截止减当前 boot 时钟剩余**映射；authority/ledger/accept 锁等待、prepare materialize/hash/tar/copy、命令/socket RPC、observation 保留及首次 host-history 归档共用该窗口，未重新加完整 seconds。首次 history 归档超时保留本次独有 partial；下一次明确操作重验原件后使用新 partial，不把旧 partial 猜成完整证明，也不永久污染共同 snapshot。真实 solver wall 与控制窗口分开。维护 collect 使用当前窗口/共享剩余/原 runner policy 的一次固定子窗口并留 receipt；不刷新旧窗口或 solver allowance。结束后的原 clock reconciliation 不是新运行 grant。

## 原件与投影边界

- `seal.pending_executions` 在原 terminal/cleanup 后、原 authority writer 内捕获完整本地 allocation/request/call 集合；一次局部索引，不每 call 重扫请求。没有相关 allocation/call 时不读取 attempt/request 历史。可选捕获遇半写/坏目录或锁冲突只保存 incomplete，普通科研结论仍可封存；不能拿 incomplete/当前 absence 授 fresh。
- 第三行闭合：原 `possibly_prepared`/无 accepted 从原 seal 控制元数据派生 unknown。`origin=sealed_preparation_unknown` 仅消费后来真实同 allocation/native_attempt/interface/target/authority/prepared 原件，不 fresh；没有 accepted 仍 unknown。它使用同 event validator/ref 链，不伪造 terminal 或退额。
- 旧单文件 recovery API/原件保留；新 version2 同目录按 seq/previous 追加，发布前共同校验。append 对既有 prefix 仅验不可变控制 metadata/ref 链，当前 prospective 事件仍完整核精确 source/job/raw/result/seal、pending/allocation、managed 原件、accepted/script/prepared/authority/query，并带本 operation context；科学 history 的默认只读完整验证未降级。相同事实轮询不追加状态或反复写 query 原件；request/操作 receipt 与可能派发 intent 分开。
- job 的 recovery prefix 不变。search 在每个科学 source 前用该 job 当时的 prefix 还原机械计数，最后叠调用者 prefix；原 W/A 的科学结论、旧 seal、node/slice/portfolio 投入不回写。零旧 accepted 的真实新增 row 仅在派生 copy 加一次。
- 自动冻结 `capture_pending/verify_pending_set/resume/call_view/validate_managed` 的真实 owner 文件及原注册实现；不依赖插件手列共通 helper，不递归扫依赖树。

## 精确文件组

1. 原件/资格/预算：新增 `research_loop/execution_resume.py`；`execution_authority.py`、`budget.py`、`contracts.py`。
2. 同 owner 消费：`execution_recovery.py`、`search.py`、`lineage.py`、`managed_wait.py`、`history.py`（仅首次归档/验证的默认 None context 透传）；复用原 history validator/capture，未改旧历史科学结果格式。
3. 公共/可信接线：`cli.py`、`controller.py`、`instance_ui.py`（只 successor 链接）、`experiments.py`、`operations/runtime_plugins.py`。
4. 原同 deadline 传递：TCAD `managed_execution.py`、`command_adapter.py`、`execution_adapter.py`、`project_packager.py`。默认 None 保持旧消费者；operator JSON 无恢复/放行开关。
5. 仅编写负控：`tests/research_loop/test_native_execution_inputs.py`，抽原 review 链 helper，共用已有小 fixture；五个新用例覆盖有效迟批/public CLI/pending→cancelled/旧 prefix、过期 successor、缺/坏/活 owner/矛盾、intent 中断不重发、reserve-gap renewal 不重复扣额。

## 静态证据与真实成本

执行的只有 **19 个 Python 源码/测试的 AST 解析 PASS、文本/调用链审查、git diff --check PASS**；未 pytest/collect、项目 import、模型/进程业务、安装、build 或 solver。负控尚未运行；fixture 的 native identity/cleanup 和 backend 是可信合成边界，不能替代真实平台/远端并发验收。

capture 一次扫描 allocation 元数据，相关 pending 才建一次 request 索引并核显式 attempt/ref；clock/新 call 分类读取当前 seal/pending-set 与 recovery/request/decision/admission 的控制 JSON/ref 链，不重验历史科学输出/大日志。ledger fold 只读原 ledger 元数据，不在每个 snapshot 递归解析 attempt/allocation 原件。search 每次 fold 建一次局部 recovery 校验结果，按 source prefix 派生，不每 source 重扫全部原观测。

实际资格、发布及科学 history 仍需核显式原件，当前原 W 的 capture 可重复读取它已有的 call 原件；没有机械容量 cap，也不声称零 IO。既有 `retirement→verify_retirement` 的 prepared/receipt **只读**复核仍可默认 None；这不触复制、RPC 或新 grant，按 root/独审裁定披露其成本，不扩全只读依赖树。单次阻塞文件 IO、JSON 解析/序列化与系统调用不能被 Python context 硬抢占；持久文件与 seal 完整保存、可信 host 路径是软边界。历史无正向 seal、缺原件或不完整 cleanup 保持 unavailable；不修复/猜造丢失原件。
