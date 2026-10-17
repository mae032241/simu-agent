# P2d 原调用永久未提交证明实施记录

日期：2026-10-17。依据[已审设计](P2D_ORIGINAL_SUBMISSION_RETIREMENT_DESIGN_20261017.zh-CN.md)及[独审](P2D_ORIGINAL_SUBMISSION_RETIREMENT_DESIGN_REVIEW_20261017.zh-CN.md)。基于 P2c/P5，静态冻结时 HEAD 为 `309cf67`（同期 P3c）；本节点差异已冻结并获[独立静态审查 PASS](P2D_ORIGINAL_SUBMISSION_RETIREMENT_REVIEW_20261017.zh-CN.md)，待提交，动态未验收。

## 精确责任

生产七文件：插件 `managed_execution.py`、`execution_adapter.py`、`command_adapter.py`；core `research_loop/experiments.py`、`history.py`、`execution_recovery.py`、`lineage.py`。定向负控仅既有 `tests/operations/test_runtime_plugin_configuration.py`，复用 P2c 小 package/backend/Records，新增四个 case。不改 P3 source/authority/UI/contracts/controller/CLI/budget、RuntimePluginContext 或 factory gate；P3d owner 后续串行接线。

## 变化及唯一原件

原 call 下独立 `submission-retirement.json`，仅永久 protocol + exact prepared digest 的明确退役回执可封存。公开 disposition 为 not_submitted，不生成 external/submission/native manifest/completed/execution-observation，不映射为 failed/cancelled，不给 candidate/metrics。旧 accepted、intent、scientific seal 和科研机会计数不改。

`experiments.verify_retirement(value, original_loader, *, interface=None)` 是准入、history、recovery、P3d 的唯一验证器，返回 call_id/scope/prepared/accepted/authority 绑定。它核所有原 proof bytes、冻结可选 cap 完整 contract/hash、cap 声明的 backend_protocol 与实际 retained protocol 的 canonical JSON（包括类型）、accepted.script 和原 prepared 两份实际字节、authority/request/response/dispatch 身份。core 无 TCAD 操作名或 intent 文件名硬编码；新 accepted 的 execution_authority/execution_target/submission_intent_path 仅投影已有 ref/目标/路径，不建新授权或状态。

两 adapter 的 details 方法保留原完整响应，旧 retire_submission 保留 tuple/None 及原 RPC 数量；validate_submission_protocol 仅在成功时额外返回已经核过的原 dict。wrapper 新可选 cap 走现有冻结机制，不加 LifecycleCapabilities 字段；旧缺声明的方法 unavailable，不追认能力。

wrapper 的同 call Records lease 由 submit 与 retire context 共用；retire 跨 yield 持到 core 原件核验/发布结束，core 不嵌套锁，不占 Records.accept 短锁。退役开始后 fresh lease 失效，原退役请求证据存在时不重新授 fresh submit；已永久 proof 落盘则 submit 写 intent 前拒绝。found 回原 job 并按原权限 cancel；已 cancelling/terminal 不重复取消。busy、丢回执、lookup None 仍 unknown，不伪造 absence、不重新 submit。

当前准入/progress 使用原 call 配置验证永久证明后解除其 unknown；history 归档完整声明原件，recovery 对旧 sealed unknown 只追加同 call 前缀，A 页显示 not_submitted 与公开 native 请求/回执/协议证明，不复制 authority 原件正文为科学材料。不存在额外清阻或余额路径。后继执行仍须自己的 gate、预算及科研机会，退役不退科研调用计数。

P3d 唯一 budget owner 已收到稳定 validator API；它必须对齐原 reservation 自身的 accepted/authority/call/prepared 后幂等 release。本节点没有 release/settle/额度修改。原永久 backend fence 是跨 boot 不确定性证明的来源，不是主机计时/进程消失；新维护调用仍核原权限，跨 boot 不延长 solver grant。

## 四个最小负控（只写未跑）

- 缺冻结 optional cap 拒绝；真实 core retire 在 wrapper call lease 内发布，迟到 submit 不能进入；重复读取无 RPC，准入确实越过已证明的旧 unknown但下一 prepare 仍须独立 gate，没有第二 accepted 或机会退款。
- 丢退役回执保 unknown/accepted，原 submit 不重发；同 digest 重查确认后独立验证器拒错协议内容及原 prepared 被换字节，恢复原 bytes 后可再次验证。
- 已存在远端 job 只绑定同 ID并 cancel；重复不再取消；后端丢库不能将本地已有 external 解释为 never submitted，失败保原件且无共同永久证明。
- 实际 history.managed_status / validate_managed 与 execution_recovery.validate/resolved 共用同 archive loader；可信注入只替宿主 scope/config/source发现，手工小 immutable archive 模拟旧 sealed unknown。native proof 篡改拒绝，旧科学观察字节不改。它不证明整实例/CLI/A 页面实际运行；lineage 路径仅静态复核。

八 Python 文件 AST、定向 diff/尾空白及证据链接静态检查通过；全文/hash 私有快照置于 repo `.trial/reviews`，不提交。没有 pytest/collect、项目 import、CLI/进程、build/install、模型、SSH、许可证或 solver运行。实际并发/掉电/跨 boot、安装元数据、全实例恢复/A展示与真实后端永久性均未动态验收。

真实 gate/source、P3d预算/累计资源及生产隔离限制继续有效，默认真实 factory 仍 blocked。本节点静态 PASS 不能单独启用生产 TCAD。
