# F2 诊断归档修复独立复审（2026-10-16）

结论：**PASS，限定为本次明确所有权的诊断 inventory、同步原件归档/恢复及受控 writer 拒绝路径。** 未发现该差异中需要阻断提交的剩余缺陷。没有将同步 fixture 结果外推为真实 native Worker、TCAD solver 或任意原生写者的静止证明。

## 精确范围

基线为 `727f5372549148fa2c0f40c51c5bd74692478954`。复审 F2 独占的 7 个生产文件：`operations/runtime_plugins.py`、`artifact_agent/runtime_plugin_bindings.py`、`service/instance_archive.py`、`service/instance_archive_files.py`、TCAD 插件的 `plugin.py`、`runtime_plugin.py`、新增 `debug_archive.py`；以及 `test_instance_archive.py`、新增 `test_instance_archive_debug_storage.py`。其余并发 F1 execution/history/contracts 修改不在本结论内。

独立复审者未编写被审实现；先读原始 F2 审计，再按 `scid-cross-boundary-review` 和 `scid-change-scope-checks` 追踪接口、所有权与 writer 边界。冻结后独立提取 [实现报告](GENERIC_PLATFORM_ARCHIVE_F2_FIX_20261016.zh-CN.md) 的 9 个文件 SHA256，与工作树逐项核对，全部一致。未修改生产代码、未重复运行未冻结测试、未调用模型/solver、未提交。

## 关键边界与负控

原全局否决没有被直接删除。已有 runtime factory 增加可选、只读的 archive_storage builder；独立 loader 只读配置，不构造 adapter/tool service、不连接 solver、不创建 debug 目录。核心负责 provider root/路径边界与既有文件迁移；领域 reader 负责解释 TCAD ledger/receipt，避免核心理解领域预算内容。

TCAD reader 使用原预算锁进行有界只读扫描，验证现行 schema、record key、实际 Run→instance 归属、instance budget key、submission 和 collected receipt。目标实例必须已 collected、原件摘要及 receipt 身份一致；其他实例状态保留原位。未知/混合归属、未知残留、坏 receipt、缺锁、锁忙、活动或未收集状态均保持拒绝。无法取得实际 Run 归属时不会仅凭目录名或 mtime 指派所有权。

公共 inventory 拒绝相对/别名 root、与既有管理树重叠的 root、越界路径和符号链接；restore 对 archive 中已有 plugin root 要求同一配置的 provider/root。插件移除但存在历史 TCAD 残留时仍报告 explicit unsupported，不能用移除插件制造 ready。新 provider 对旧 archive 没有 plugin root 的兼容检查也保留既有基础 root/backend 身份。

审查期间发现的锁孤儿问题已修正：只迁移 ledger、把新增 `.lock` 按后缀猜为 shared 会留下孤立锁，重新阻断其他实例。最终实现取消该猜测，目标预算锁与 ledger 作为明确的独占原件迁移；已有全局 transport/shared CAS/recovery 锁策略没有改变。新增测试实测 A 归档后 A 的锁不残留、B 仍 ready。

并发保护依赖现有 MCP tool 的 global/instance maintenance guard、archive freeze/switch 的同一互斥与 durable marker。reader 还拒绝持有中的预算锁和未完成后台状态。最终测试覆盖：预算锁占用时 preview/archive 拒绝；preview 后预算字节变化使确认失效；after_archive_scan 新取得真实 instance maintenance guard 后 freeze 拒绝。现有 backend_writer_guards 对 native writer 的保守拒绝未放宽；plugin 文件清理没有被解释成对任意绕过维护协议写者的安全授权。

## 实际证据

独立读取最终两批原始 pytest.log、资源记录和冻结测试文件：

| 检查 | 结果 |
| --- | --- |
| 新 21 项及现有 archive/runtime plugin/debug identity 批次 | 96 passed、5 failed、3 deselected，49.09s |
| 新 21 项及修正夹具后的原失败 5 项 | 26 passed，12.44s；监督 12.869s、exit 0 |

合计是 **101 个唯一用例最终通过**，两批中重复运行的新 21 项只计算一次。最终复核 production 字节与前一批一致，只有现有测试两处输入前提修正。资源监督均 cleanup_complete=true、无内存保护触发；最后复核观察到 tree RSS 峰值 131858432 bytes。

初批 5 个失败没有被笼统标为环境问题。独立查看精确 HEAD 的 SchedulerRunStatusInput，确认它没有旧 `output_paths` 参数，相关四个参数化失败发生于 Schema 入参校验；删除参数保留同一 MCP facade、queued/running 与归档拒绝断言。另一失败来自 prepare 已创建 scratch 后测试再次 mkdir；精确 HEAD 的 prepare 确实创建 capture root，改 exist_ok=True 保留后续 recovery/shared bytes/预算检查。两处未修改生产 Schema 或降低 writer 检查。

新增测试覆盖 B 已完成和已知运行中诊断不属于 A；A 自身 ledger、receipt、prepare exchange 归档/恢复逐字节不变，预算 17 不重置；A 归档后 B 可继续归档；所有权/receipt/未知残留/链接/缺锁拒绝；无 provider 与 restore 缺 provider 拒绝；公共 root/path 边界；真实 LocalTCADDebugService 在无 solver adapter fixture 下生成的原始 ledger/receipt 能被只读 reader 消费。reader 不改这些原字节。

原始证据保留于 `/tmp/scid-debug-archive-f2-final-source` 与 `/tmp/scid-debug-archive-f2-final-recheck`；具体命令与完整冻结摘要见实现报告。审查没有把临时路径当成持久发布产物，也没有把合成 adapter 当成 solver 验收。

## 限制与可冻结状态

没有运行 F2 独立 installed wheel、完整平台矩阵、真实 daemon/browser、跨主机重启、TCAD solver 或 native Worker。插件 factory identity 已显式更新，装配与运行路径在源码测试中覆盖；打包/部署资格仍需相应安装检查。同步迁移正控采用仓库既有 SynchronousFixtureArchive，真实生产 backend 的未知 writer 仍会拒绝归档。

PASS 仅覆盖以上精确差异和证据。F1 的非本地终态修复仍由另一个独立结论判断。F2 文件集可冻结提交，审查者不再写入这些实现文件。
