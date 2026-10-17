# P2b 精确原件窄回调实施记录

日期：2026-10-17。基于 P2a `c925873`；静态冻结时 HEAD 为 `da87484`（同期 P3a 提交）。依据[主计划](../THIN_CAPABILITY_MIGRATION_20261016.zh-CN.md)、[已审 TCAD seam](../THIN_TCAD_MANAGED_SEAM_20261016.zh-CN.md)和[已审拆分](../THIN_P2_P3_IMPLEMENTATION_SPLIT_20261017.zh-CN.md)的 P2b 节点。窄接口先经独审认可后实施；最终冻结已获[独立静态审查 PASS](P2B_EXACT_ORIGINAL_RESOLVER_REVIEW_20261017.zh-CN.md)，已提交 `f365776`，动态未验收。

## 精确责任和接口

生产仅三文件：

- `plugins/tcad_artifact/tcad_artifact/project_packager.py`
- `plugins/tcad_artifact/tcad_artifact/execution_adapter.py`
- `plugins/tcad_artifact/tcad_artifact/command_adapter.py`

定向负控仅 `tests/operations/test_runtime_plugin_configuration.py`，复用已有 `_execution_package`，没有新 Root/runtime 环境 fixture。同期 P3a/P3b 文件不在此节点范围。

保留原四位置参数，增加两个成对 keyword-only 参数：

```python
materialize_execution_inputs(
    reviewed: ExecutionPackage, artifacts, exchange_directory: Path, chunk_bytes: int,
    *,
    input_metadata: Callable[[ResolvedProjectInput], tuple[int, str]] | None = None,
    open_input: Callable[[ResolvedProjectInput], ContextManager[BinaryIO]] | None = None,
) -> dict[str, Path]
```

宿主回调取得完整的 frozen resolved item（semantic slot、完整 ArtifactRef、目标路径、media、size），metadata 返回 `(size_bytes, media_type)`；opener 返回该精确原件的二进制流。新调用传 `artifacts=None`，不伪造 ArtifactService，不按近似路径、时间或 schema 猜来源。P2c 负责将真实冻结源绑定至回调，此节点没有新的来源查找系统。

旧 Artifact 参数仅在函数内适配原 `catalog(item.artifact_ref)` / `open_original(item.artifact_ref)`。旧四参数调用、两个 `prepare_with_artifacts` 和 `artifact_agent/execution_bridge.py` 的调用关系保留。两个真实 prepare 消费点只增加同名透传参数；旧 JSON schema、任务注册、Root、预算和授权入口未改。

## 保留与补强的验证

- `ExecutionPackage` 和最终 `package_execution_package_json` 的完整 slot 覆盖、target path、media、hash、size 校验原位保留；原显式 storage quota 仍为 deck UTF-8 字节加全部 resolved 输入声明字节，没有新增机械容量上限。
- 回调缺半对、与 Artifact 参数混用、无来源，以及非正整数 chunk（包括 bool）拒绝。metadata 要求 int size / str media，且与声明精确一致；命中缓存仍先读取 metadata。
- 逐块读取并计算实际 size/hash，超过声明大小立即拒绝；错 hash、短读同样拒绝。仅删除本次新建失败 partial，不删原有缓存。成功文件只读；已有缓存先检查 regular 文件与 stat size，大小不符立即拒绝，否则重新核对实际字节 hash，拒绝 symlink/非 regular 文件。
- exchange 和 `scientific-inputs` 目录拒绝 symlink/非目录，并验证暂存目录 canonical parent 等于 exchange canonical root，防止目录链接把写入导出 exchange。

## 最小负控及证据限制

四个既有模块内新增 case（小原件 `b"{}"`）：

1. 完整 resolved item 传给 callbacks；只读结果、合法缓存无需再开源但仍查 metadata；缓存等长篡改与 symlink 拒绝且旧字节不被清除；大小不符的缓存不进入完整 hash 读取。
2. 错 metadata、等长错 hash、短读、超声明大小拒绝，新的 partial 不残留。
3. 显式 quota、缺/混合 callbacks、缺来源、chunk=0/bool，以及 exchange/暂存目录 symlink 拒绝，外部目录没有写入。
4. 两个实际 adapter.prepare 经真实 package 验证/materializer/packaging 消费回调；错原件必须在 command prepare 前拒绝。能力列表、runner policy 与 command prepare 返回使用小 stand-in；测试不创建 Root、不执行传输程序。它只覆盖本地消费者转发及拒绝，不证明真实服务、SSH、授权、远端 prepare/upload 或 solver。

四个改动 Python 文件 `ast.parse` 和定向 `git diff --check` 通过；仅使用标准库读取/解析文本，没有 import 测试或生产模块。上述负控已编写、未运行；没有 pytest/collect、CLI/进程、build/install、模型、SSH、许可证或 solver 运行，也没有新的耗时/RSS/实际容量结果。私有全文快照与 SHA-256 保存在 repo `.trial/reviews`，不提交。

本节点不授予正式独审资格或执行权限，不注册新 managed TCAD，也不绕过底层 prepare。P2c/P2d/P3 和主计划原有动态未验收限制继续有效；真实 TCAD 生产仍 blocked，必须先完成可信 P3 gate。
