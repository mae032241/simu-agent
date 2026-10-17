# P5 TCAD 导入依赖收缩

日期：2026-10-17。基线：P2c `4f0a455`。独审先认可三文件窄设计后实施；已获[独立静态复核 PASS](P5_TCAD_IMPORT_CONTRACTION_REVIEW_20261017.zh-CN.md)，待提交。此节点不包含 P2d 或 P3 实施。

## 精确变化

- `runtime_plugin.py` 把 `TCADDevelopmentDebugBridge` / `LocalTCADDebugService` 两项导入从模块顶层移至既有 `build_runtime` 的 local_worker mode 检查之后，与原 `OutputInspectionService` 导入并列。managed factory 和旧 control 分支不再因这两个顶层导入拉入 debug service/旧 execution bridge 链；旧 local_worker 仍在同一分支构造相同工具。
- `execution_adapter.py` / `command_adapter.py` 的 `AdapterCapability` 直接从 `operations.execution` 导入；旧 bridge 原为同一中立类型的 reexport，没有新类型或协议身份。

没有改变 factory 配置、注册、权限、方法、状态、预算、旧工具构造或实际 transport 行为。没有生产 gate 接线或真实执行授权。

## 静态证据与限制

三个 Python 文件 AST 解析通过；AST 文本核查确认 runtime_plugin 顶层没有这两个 debug 导入、导入仍处在旧 build_runtime 函数内，两 adapter 使用中立 owner，旧 bridge 同名类型仍为 reexport；定向 `git diff --check` 和尾空白检查通过。没有添加镜像实现的测试。

仅标准库读取/AST及 Git 文本检查，没有 import 项目或测试、pytest/collect、CLI/进程、build/install、模型、SSH、许可证或 solver。静态导入边变化不证明实际冷启动性能、RSS、全部间接导入闭包或已安装包行为；旧 local_worker/control 路径没有动态验收。私有全文与 hash 快照置于 repo `.trial/reviews`，不提交。
