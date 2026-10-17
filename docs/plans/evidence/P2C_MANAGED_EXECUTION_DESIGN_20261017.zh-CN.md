# P2c TCAD managed wrapper 窄接线设计

状态：**设计独审 PASS，开始实施；真实生产 blocked。** 日期：2026-10-17。依据[主计划](../THIN_CAPABILITY_MIGRATION_20261016.zh-CN.md)、[已审 seam](../THIN_TCAD_MANAGED_SEAM_20261016.zh-CN.md)和[实施拆分](../THIN_P2_P3_IMPLEMENTATION_SPLIT_20261017.zh-CN.md)。前置 P2b 已提交 `f365776`。独审确认默认 blocked、gate 前本地验证、原 call 一次派发与终态缺证据中性分支；root 已批准下述两处 experiments.py 责任扩展。没有动态验收。

## 文件与唯一 owner

新增插件 `managed_execution.py`，修改 `runtime_plugin.py`（提共享底层 adapter 构造）及插件 `pyproject.toml`（注册 `tcad_execution:tcad`），另有小测试/证据。经 root 批准，仅增加 `research_loop/experiments.py` 两处极窄通用接缝（下述），由本实施者独占。保留原 control adapter 和 local_worker 工具分支。P3 的 source/qualification/contracts/controller/CLI 不在本节点修改范围。

新类 `TCADManagedExecution(config, adapter, *, gate=None, input_metadata=None, open_input=None)` 实现现有 managed 方法，复用两底层 adapter、P2b 回调和 `experiments.Records`。`terminal_evidence_kind='adapter_result'`，`result_protocol=None`；不生成本地 command、entry、snapshot_files 或领域 candidate 字段。原件准备目录只存输入、descriptor 和验证回执；call、accepted/submission/completed/observation 仍由现有 Records 持有，不增科研状态账。

## 可信 gate 与精确原件

独立 managed factory 只构造共享 socket/command adapter，固定使用缺 gate 的阻断行为；构造本身不调用远端。公开 JSON 没有 gate 路径、test factory、allow 或 unqualified 开关。可信 Python 构造注入仅供宿主接线/小 fixture，不属于 Worker 输入合同。

单一 gate 调用候选：

```python
gate(phase, *, scope, call_id, payload, target, prepared=None, prior_receipt=None)
```

scope/call 来自现有宿主配置/Records；payload/prepared 使用既有 descriptor；target 绑定冻结 transport 配置身份。phase 的 prepare/submit 检查执行权限，collect/cancel 只检查原调用权限，均不产生新的执行请求。prepare 返回唯一 P3 owner 的回执 ref 和既有 ExecutionAdmission；submit 核同 ref 链，不再次 reserve。collect 返回由原授权当前 remaining 裁剪的 CollectionContext，不扩展授权。P3 owner 从这些宿主 ref 解析来源、正式资格、请求、policy 与预算，不信 Worker 自报的 package/成本/批准文字。receipt hash 验证只证明字节不变，不能自行代替 P3 授权规则。

已与 P3 实施者协调：P3c 的 `execution_authority.py` 及 P3d 的唯一 `budget.py` owner 负责最终 gate 和唯一 factory 接线。P2 不写 grant/reservation/settlement。P2b metadata/open 回调是独立原件读取依赖，不让 gate 再建立一套 resolver；回调必须按完整 ResolvedProjectInput 绑定已冻结来源，不能按近似路径、同 hash 或最新项发现来源，不造 ArtifactService。当前 factory 没有实际冻结 source 接线；含 resolved_inputs 时缺回调即 unsupported。gate 与来源接线全部完成并单独验收前，实际 prepare/upload/submit 一律 blocked。

## 方法消费链

1. prepare 在 gate 前只本地验证 `research_loop.v1`、原 descriptor 和 canonical TCAD package，不调用会 query remote capabilities 的底层 validate_preparation_payload。target 取宿主冻结配置，不信 package 自报。在触达底层 prepare/upload 前 gate；随后复制精确输入到独立准备目录，转换为旧 TCAD profile，并透传 P2b 回调。返回 descriptor 保留原 call_id；acceptance_metadata 保留原 package/prepared/授权回执 ref。拒绝未声明的 candidate/本地命令语义。
2. dispatch_lease 核同 accepted scope/native_attempt/prepared/gate ref，只授本进程一次性的 fresh lease；submit 复核 gate 后，在首次 backend 调用前独占写持久 intent 并消费 fresh lease。已有意图/重启仅 lookup，不重发。底层 descriptor 的 name 不生成第二 call。lookup None 不是未提交证明；响应丢失保留 unknown 与原 reservation。
3. active/unretained status 从原 Records 取得 prepared，每次先 lookup 该 descriptor，再核已知 external ID，最后 query；两底层 adapter 状态原样保留。旧 command status 不含 run_id/prepared digest，不能仅凭其 state 绕过 lookup。取消仅使用原 external ID；retire 留 P2d。
4. status_details/query 不收集。result/collect_original 在终态时按原授权 remaining 有界收集；验证本地 descriptor hash/size、完整 native manifest、状态及输出清单绑定，保留 manifest/日志/outputs 和宿主 lookup/status/收集回执后发布共同 completed。只有状态字符串不构成完成。cancelled 保留 native_state，归工程 known_failed，不产生科学否定。重复访问仅核 retained 原件，不再查后端或重复收集。
5. `config.max_seconds` 的操作 timeout 与 job resource wall_seconds 分开；恢复收集不沿用原 submit 的几秒 deadline，也不重置整场授权。缺可信 remaining/context 即 unsupported；不会以未知用量=0放新调用。

共同消费点仅两处：record_observation 在 result 显式 `status='unknown'` 且尚无 canonical completed 时返回 None，不读取不存在的 completed；completed 已存在却 result unknown/不一致仍按原 IntegrityError，不能吞矛盾。新 call 扫描对全部 native terminal（原先仅 cancelled）要求 verified observation；缺证据返回原 call unknown，不放新 call。

wrapper 保留 native 终态，但 collect gate 缺失、remaining 耗尽或传输失败时不造 completed，而返回 unknown；原身份/本地 proof 篡改仍报 IntegrityError。现有 waiting 路径以 terminal_unverified 保留 raw/checkpoint 与 reservation，不自动重跑；终态首次在 turn 结束时出现且仍缺证据，现有 before_seal 可保留普通科学输出，但执行事实按 unknown 封存，不能声称 W 已消费合格终态。

## 最小负控及未验收

直接用真实 wrapper 与现有 Records，可信依赖注入小假后端/回执 owner；不增加 Root/安装环境或公开旁路。覆盖默认 factory 在底层 prepare/upload/submit 前阻断；accepted→pending→cancelled 的原 call/remote ID/manifest 保留；错 prepared/lookup/gate 回执拒绝；submit 响应丢失后 lookup None 不重发。预期独立列举，不扩状态×环境矩阵。

本节点不运行 pytest/collect、import 项目、CLI/进程、build/install、模型、SSH、许可证或 solver。fixture 不能证明真实后端身份、权限隔离、可信 UI、累计 solver 预算、跨 boot、同 session wake、领域候选或实际生产资格。P3 未完成的 gate/source 接线明确保留，注册成功不启用真实执行。
