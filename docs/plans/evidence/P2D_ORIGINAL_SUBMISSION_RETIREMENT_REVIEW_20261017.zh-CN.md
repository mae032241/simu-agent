# P2d 原调用永久未提交证明实现独审

结论：**本节点静态 PASS，无剩余阻断；不批准真实 TCAD 或资源退款。** 审查相对 HEAD `309cf67` 的冻结七生产文件、既有 `test_runtime_plugin_configuration.py` 四条新增负控及实施报告。P3c 已独审提交；并行 P3d1 ledger/HostServices/gate 不在此结论内。仅静态阅读与限定 diff 检查，没有运行测试、项目 import、CLI、进程、构建、安装、模型或远端计算。

## 真实控制链

- `experiments.py` 的可选 capability/完整 contract、`verify_retirement`、Records receipt、显式 retire CLI、准入与 progress 使用同一永久事实。不向必需 managed 方法或 native terminal 状态增加变体，公开 `not_submitted` 不制造 completed/observation/科学失败、候选或 metrics。
- capability bytes/hash 冻结真实 backend_protocol；共同 validator 核 accepted/scope/native attempt/mechanism/interface、authority、request/完整 response、原 dispatch intent、prepared descriptor 及实际原件字节。永久协议按冻结声明比较，core 不硬编码 TCAD 协议名称或目录。
- wrapper submit/retire 取同 call 非阻塞 lease。retire context 跨 yield 持有到 core 核验、发布、重复对照完成，不占 Records.accept 短锁。永久 proof 出现后 submit 在写 intent 前拒绝；退役开始后清除 fresh lease，持久退役请求存在时不会重新授首次提交机会。
- found 绑定同一原 external 并按原权限 cancel；已 cancelling/terminal 不重复取消。明确 found=false/retired=true/同 digest 且永久协议成立才可能封存；已有 external、submission 或已执行事实与 absence 矛盾时拒绝。忙、timeout、丢响应或 lookup None 保 unknown，不清计数、不重 submit。
- 两底层 adapter 新 details 保留完整原响应；旧 retire_submission 继续 tuple/None 适配及原 RPC 数量，validate_submission_protocol 仅返回已核过的原件。实际同 digest 原子 fence 继续由既有后端协议负责，不由本地 lease/等待时长推定。

## 恢复与后续消费者

准入/progress 先取原 call 配置验证独立事实，而非用新 attempt 配置改写旧能力。history 用 `retirement_originals` 归档完整声明 proof，managed_status/validate_managed 复用同 validator。原 sealed unknown 的 recovery 只追加原 call、旧 seal/row hash 绑定的前缀；后继节点冻结前缀，lineage 向 A 展示独立 disposition 及请求/响应/协议，不伪造执行输出。

原 accepted、scientific seal 和机会计数保留；新 call 仍需自己的 admission/gate。P3d 是唯一资源 release owner，必须另核原 reservation 的 accepted/authority/call/prepared，不能从状态字符串直接退款。此节点未改余额。尚无 accepted 的 pre-accept reserve 窗口不在此处伪造证明。

## 独审缺口已收口

1. 早期 validator 仅读取 protocol JSON 而不使用其内容。最终 capability 的完整 contract 绑定精确 backend_protocol，validator 按 canonical JSON 比较，保留类型差异；不在通用 core 引入 TCAD allowlist。
2. 早期重入只比较 prepared descriptor。最终统一 bound 同时复核 accepted.script 留存副本和原 prepared 路径/hash/size；history 显式归档这两份声明，当前准入/progress 与归档消费者均可拒绝换字节。

## 四条负控能证伪什么（均未运行）

- 缺冻结能力必须拒绝；真实 core 发布共同 proof 时重入 submit 会遇同一 call lease，发布后仍不得 submit。若锁提前释放或 proof 未在提交前检查，此保护会失败。后续 prepare 是受控 stand-in，只证明旧 unknown 已解除而新 gate 仍需独立，不证明新执行成功。
- fake backend 丢退役回执后保 unknown、不重 submit；统一 validator 拒绝错协议和 prepared 换字节。fake backend 的 fence 是可信依赖模型，不能证明真实远端持久性。
- 原 found job 只取消同 ID、重复不再 cancel；随后丢后端库仍不能洗成从未提交。若本地身份被忽略或取消被当退款证明，会失败。
- 手工小归档仅注入宿主 scope/config/source 发现，实际 history 与 execution_recovery 消费原 validator。原响应被篡改后 recovery 拒绝，旧观察字节不变；没有把 fixture 自己封存恢复前缀当作 `execution_recovery.create`/整场 CLI/A 展示已通过。

没有新增安装、Root fixture 或笛卡尔积。限定 `git diff --check` 通过；作者报告八文件标准库 AST 通过。本审不以这些静态检查替代动态证据。

## 未完成资格

默认生产 factory 仍 blocked。新的退役调用经原 gate 的 retire/cancel 维护权限与既有有界 adapter RPC，不在本节点自动发科学资源 grant；P3d 必须继续区分维护与新 submit，不能因科学额度耗尽永远阻止管理 query/cancel/退役，也不能借维护重授执行额度。

真实并发、远端掉电/跨 boot 持久 fence、混合版本、权限隔离、安装发现、整实例恢复/A 页面和 solver 均未动态验收。完整 JSON/原件校验没有新增硬实时或内存保证。P3d 资源接线、非空输入映射、长等待原 call 恢复仍独立待完；本 PASS 不是 P2/P3 全体退出。
