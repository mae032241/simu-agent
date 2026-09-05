# R1 最小 OperationSpec 与启动期编译器第三轮独立审查

审查结论：**通过**。

R1 第二轮唯一阻断已经关闭，既定回归、发行、存储和复杂度边界均通过。允许主实现者把主计划
第 26 节 R1 状态更新为“通过”，完成报告/计划的 Manifest 摘要更新后进入 R2。该结论只放行
主计划既定的 R2 统一调用阶段，不授权提前迁移 TCAD、删除旧生产路径或修改存储。

审查基线：`baseline/8765-codex@404aeb1`，叠加 R0 已通过内容、R1 实现、前两轮独立审查及
本轮定向修复。审查者未修改生产代码、测试、主计划或前两轮报告，只新增本报告。

## 1. 第二轮唯一阻断复验

### 1.1 非法 Unicode 资源经过真实安装入口稳定失败

测试使用独立发行包 `scidiscovery-invalid-unicode-operation-test-plugin`：

- 插件通过自己的 wheel 安装；
- 只使用唯一 `scidiscovery.plugins` entry point；
- 资源模块暴露值为孤立 Unicode 代理字符 `"\ud800"`；
- core wheel 来自 clean release，测试进程在仓库外目录运行，删除 `PYTHONPATH` 和源码角色目录，
  并确认 `scidiscovery` 来自 venv 前缀。

真实 `compile_installed_catalog()` 结果为：

```text
reason_code = component_resource_digest_invalid
plugin_id   = invalid_unicode
field       = invalid_resource
```

没有裸露 `UnicodeEncodeError`，坏插件也没有被跳过后继续生成部分 catalog。资源 pass-one 边界
现在给出与组件所有者一致的稳定位置；此时资源尚未归属唯一 operation，因此不虚构 operation
位置是正确的。

### 1.2 普通 operation 声明的非法 Unicode 在最终摘要边界稳定失败

独立把 `builtin.test.agent.description.purpose` 替换为同一孤立代理字符，直接编译结果为：

```text
reason_code  = operation_digest_invalid
plugin_id    = builtin
operation_id = builtin.test.agent
field        = digest
```

该异常出现在包含规范、组件、权限模板和 reviewer 摘要的最终 compiled digest 边界；错误没有被
误报成 schema、组件加载或执行错误，插件/operation/field 三段位置完整。

### 1.3 进程控制异常未被错误捕获

独立向组件 import 和资源摘要边界分别注入 `KeyboardInterrupt`、`SystemExit`。四个反例均原样
逃出，没有转换成 `CatalogCompileError`：

```text
component-load-control KeyboardInterrupt ESCAPED
component-load-control SystemExit ESCAPED
resource-digest-control KeyboardInterrupt ESCAPED
resource-digest-control SystemExit ESCAPED
```

实现只捕获普通 `Exception`，没有捕获 `BaseException`；服务停止、终止和操作员中断语义未被
插件诊断层吞掉。

## 2. 回归与范围边界

### 2.1 没有新增第二诊断权威

- 仍只有 `CatalogCompileError` 和局部 `_fail()` 作为 catalog 编译错误合同；
- 新 reason code 是固定字符串，没有诊断 registry、映射表、数据库或生命周期；
- 资源摘要错误在 `_resource_digest()` 的插件边界直接映射，operation 摘要错误在
  `operation_digest()` 的精确 operation 边界直接映射；
- 没有新增错误恢复、插件跳过或部分启动分支，仍然整体失败关闭。

### 2.2 没有超出 R1 或接管生产

- 相对基线，现有 `artifact_agent`、TCAD/curve-score/ingaas 插件生产代码无差异；
- 新 catalog 仍未连接 Task、Artifact、Approval、Execution、Worker 或 Root MCP；
- 没有 `operation_invoke`，没有统一调用切换，没有领域插件迁移；
- 新 compiler 仍只读取 `scidiscovery.plugins`，没有源码扫描或旧 entry point fallback；
- R1 保持三个内置、不可调用真实科学或外部执行的架构测试 operation。

### 2.3 存储和科研权威不变

- 没有新增或修改 migration、SQLite 表、持久化 catalog 或 operation 状态；
- SQLite schema 前后相同的回归继续通过；
- 没有新增 readiness、qualification、current、科学图、候选规划器或调度状态；
- 旧 8765 路径仍是唯一活动生产权威，R1 catalog 只是启动期编译基座。

## 3. 独立执行证据

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. \
  pytest -q -p no:cacheprovider tests/operations
46 passed

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. \
  pytest -q -p no:cacheprovider
76 passed

sha256sum -c --quiet MANIFEST.sha256
通过（写入本报告前）

python scripts/build_git_release.py \
  --source . --output /tmp/scid-r1-round3-release --force
tracked source files: 229；发行目录与 tar.gz 成功生成

sha256sum -c --quiet /tmp/scid-r1-round3-release/MANIFEST.sha256
通过

git diff --check 404aeb1 -- \
  pyproject.toml src/scidiscovery tests/operations tests/fixtures docs/plans MANIFEST.sha256
通过

wc -l src/scidiscovery/operations/spec.py \
      src/scidiscovery/operations/catalog.py
299 / 400
```

此外，独立检查旧生产路径差异为零；新 operation 源码中未发现 `CREATE TABLE`、migration、
Task/Approval/Execution 服务调用、诊断 registry 或领域状态权威。

## 4. R1 总体放行判断

前两轮指出的六组问题现已全部关闭到 R1 应有边界：

1. schema/collection/组件最小 ABI 可从单一插件定义闭合；
2. Agent 传递只读资源进入同一静态权限模板；
3. external Effect 不能降低接受/拒绝、projector 和例外理由的人审下限；
4. 默认拒绝网络、端口总量、collection 和资源投影一致；
5. reviewer 的 schema identity/字节、media、codec、cardinality 兼容均失败关闭；
6. 插件加载、声明结构、资源摘要和最终 operation 摘要均有稳定 reason code，进程控制异常不被
   吞掉。

同时，`OperationSpec` 仍是十字段、无执行/调度/状态的声明；运行时只有一个新 catalog 和一个
新插件入口；没有第二状态机、科学本体或持久化权威。R1 因此符合 Everything is Operation、
启动期编译、单入口注册、默认拒绝最小授权和轻量控制面的阶段目标。

## 5. 允许进入 R2，但不提前声称完成的事项

R1 通过只证明静态声明和启动期编译基座成立。进入 R2 后仍必须独立证明：

- 静态权限模板只能收窄绑定到精确 Artifact Ref 和单任务原生路径；
- `operation_preflight` 与写入调用共享一个判断，调用参数不能覆盖工具、网络、schema、资源或
  executor；
- Task fingerprint、broker 恢复和同一 attempt 重连保持相同权限摘要；
- Effect 仍复用既有 Approval/Execution 唯一权威，不把 spec 变成第二执行状态机；
- 第一批真实组件调用合同能够发现 callable 签名、返回类型和 JSON Schema 适用性错误；
- `spec.py`/`catalog.py` 已贴近行数上限，R2 不得继续压缩可读性或把 invoke 逻辑塞回这两个
  文件。

这些是 R2 及后续阶段的验收项，不构成 R1 残留阻断。
