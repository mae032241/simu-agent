# P2b 精确原件 resolver 独立静态审查

## 结论与范围

**静态代码审查 PASS**，基线 `da87484`。受审为 `plugins/tcad_artifact/tcad_artifact/{project_packager,execution_adapter,command_adapter}.py` 的窄差异及 `tests/operations/test_runtime_plugin_configuration.py` 新增四个测试，已对照[最终实施记录](P2B_EXACT_ORIGINAL_RESOLVER_IMPLEMENTATION_20261017.zh-CN.md)。不包含 P2c 注册、真实 TCAD prepare/upload 或 P3b–d 门禁。

审查独立于实施者；仅文本/Git 阅读，没有运行测试、收集、项目导入、CLI、构建、安装、模型、SSH 或求解器。本报告中的负控目标不表示实际执行通过。

## 生产边界

- `project_packager.py:1965` 保留原四个位置参数，只增加成对 `input_metadata` / `open_input` keyword 参数。回调接收完整 `ResolvedProjectInput`，宿主负责精确冻结原件绑定；函数没有按路径近似、时间、schema 或相同 hash 发现来源的逻辑，不构造 Artifact 服务或授予来源资格。
- 旧 Artifact 分支仅把原 `catalog(ref)` / `open_original(ref)` 转成两个回调；与新回调混用或只给半对明确拒绝。`execution_adapter.py:77`、`command_adapter.py:149` 的 `prepare_with_artifacts` 与旧 bridge 调用关系保留。两 `prepare` 只加透传参数，没有新增配置/授权协议。
- 显式 storage policy 仍检查 deck UTF-8 字节加全部声明输入。chunk 要求正整数且拒绝 bool；元信息要求精确 int size / str media 并匹配声明。没有新增任意大小上限。
- 暂存目录要求实际目录，拒绝 exchange/子目录链接，并核对子目录 canonical parent 与 exchange root。目标缓存拒绝链接/非 regular 文件；先 stat size 再逐块 hash，不会明知超声明大小仍整份读取。合法缓存仍调用 metadata，验证后恢复只读，不重开原件。
- 新文件按 chunk 同时验证实际大小与 sha；超过声明大小立即拒绝，短读或等长错 hash 也拒绝。仅删除本次新建失败 partial；已有损坏缓存不会被异常路径删除。成功文件只读。
- `package_deck_project:1129` 的最终完整 slot/path/media/size/hash 校验未移除；新 resolver 不直接进入 submit，也不绕过后续封装器。旧 `artifact_agent/execution_bridge.py:135` 仍经原授权逻辑后调用 `prepare_with_artifacts`。

最后补读的收口为 cache stat-size 提前拒绝与对应负控、合法 cache 重新只读；未再扩大范围。前者避免新增路径对明显超量坏缓存做冗余全量 IO，不构成动态性能或 OOM 根因结论。

## 四个负控的实际证明目标

| 用例 | 哪种生产缺陷会使其失败 |
| --- | --- |
| `test_exact_input_callbacks_recheck_metadata_and_cached_bytes:182` | 只传猜测路径而丢完整 slot/ref、缓存命中不查 metadata、等长篡改被信任、链接可冒充 cache、失败删除旧 cache、明显错误大小仍全量 hash。最后一项只 mock 哈希器以禁止不必要读取，关键 materializer 仍为生产函数。 |
| `test_exact_input_callbacks_reject_wrong_original_and_metadata:228` | 元信息不一致仍开源、等长错 hash/短读/超声明大小被接受，或新 partial 在失败后残留。使用小真实字节流验证复制与散列，而非伪造成功响应。 |
| `test_exact_input_callbacks_preserve_quota_and_source_boundaries:245` | 混合/缺失来源被接受、chunk=0/bool 进入读取、显式 quota 被绕过、exchange 或暂存目录链接将文件写到外部。预期明确写出，没有导入生产校验常量生成答案。 |
| `test_tcad_prepare_adapters_use_exact_input_callbacks:278` | 任一真实 prepare 未透传回调、绕过实际 materializer/packager，或坏原件仍进入 command prepare。capability、runner policy 和 command 返回是 stand-in；它不验证服务端准备、SSH/上传、执行授权或 solver，只证明本地消费者转发和提前拒绝。 |

测试放在既有模块，复用小 execution package；该模块原有 Root/runtime 导入未被本次新用例调用，也未新增相应 fixture 或安装链。没有状态/环境笛卡尔积，没有将功能组换解释器后重跑。

## 尚未覆盖

旧 Artifact 分支的调用形状已静态核对，未运行其完整 CAS/bridge 兼容测试。并发同 cache 写入、文件系统竞争/错误、跨恢复、真实大文件资源曲线均未动态验证；不声称强隔离或硬实时保证。payload JSON 的原读取方式仍在，不能把原件流式暂存称为所有 JSON 已流式处理。

P2c 仍须把真实冻结输入 owner 接至回调；P3 正式独审、授权和预算 gate 仍须分别实现。此 PASS 不允许据此启用真实 TCAD prepare/upload/submit。
