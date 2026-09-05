# R1 最小 OperationSpec 与启动期编译器第二轮独立审查

审查结论：**有条件通过**。

放行范围：只允许继续修复本报告所列的 R1 稳定错误边界并补负例，不得进入 R2，不得新增
`operation_invoke`、迁移领域插件、切换生产调用路径或修改存储。修复后仍需独立复审；不能把
“有条件通过”记为 R1 已通过。

审查基线：`baseline/8765-codex@404aeb1`，叠加 R0 已通过内容、R1 首轮实现、首轮审查报告
`R1_OPERATION_SPEC_COMPILER_INDEPENDENT_REVIEW.zh-CN.md` 及本轮修复。审查者未参与修复，
只新增本报告。

## 一、仍未关闭的阻断项

### 摘要阶段仍可能裸抛异常，稳定 reason code 合同未完全闭合

位置：

- `src/scidiscovery/operations/catalog.py:85-90`
- `src/scidiscovery/operations/catalog.py:343-367`
- `src/scidiscovery/operations/spec.py:281-299`

独立反例：把已经登记为 schema resource 的字符串内容替换为一个孤立 UTF-16 代理字符
`"\ud800"`。组件在 pass one 计算资源摘要时调用 UTF-8 编码，实际结果是裸
`UnicodeEncodeError`，不是 `CatalogCompileError`。把同一字符放进 operation description，
也会在最终 compiled digest 的 UTF-8 编码阶段裸抛相同异常。

```text
invalid-utf8-resource RAW UnicodeEncodeError
invalid-utf8-description RAW UnicodeEncodeError
```

影响：服务确实会停止，但安装器、启动器和回滚逻辑得不到稳定 reason code 以及插件、
operation、字段位置；这仍不满足主计划第 19 节“任一步失败均给出稳定 reason code”的合同，
也是首轮第六项阻断没有完全关闭。

最小修复要求：

1. 在资源摘要和最终 operation 摘要边界把普通规范化/编码异常转换为带精确位置的
   `CatalogCompileError`；
2. 不得捕获 `KeyboardInterrupt`、`SystemExit` 等进程控制异常；
3. 增加 resource 内容和普通声明字段非法 UTF-8 的负例，至少一个负例必须经过干净 wheel 的
   `scidiscovery.plugins` 安装入口；
4. 修复仍须保持 `spec.py <= 300`、`catalog.py <= 400`，不得为错误映射建立第二诊断注册表。

## 二、首轮六项逐项复验

### 1. Schema、Collection 和组件 ABI：原阻断主体已关闭

- 每个输入、输出端口现在必须引用已登记 `schema_resource`；编译器读取 JSON 并核对 `$id`
  与端口 schema identity，缺失、不可解析和 identity 不匹配均失败关闭；真实资源字节摘要进入
  compiled operation digest；
- `OutputPortSpec` 已有最小 `CollectionSpec(max_total_bytes)`，内置 Transform 用独立 bundle
  codec 编译了一个有界 collection；
- 普通可执行组件必须包装为 kind 匹配的 `CallableComponent`，workspace 必须是只包含三个
  相对、互异目录的 `WorkspaceContract`；`builtins:print` 伪装 workspace 已被拒绝；
- 没有为 schema、collection、workspace 或组件 ABI 新增平行 entry point/registry。

独立重放结果：缺失 schema、schema identity 不匹配和任意 workspace callable 分别以
`component_reference_missing`、`schema_resource_mismatch`、`component_protocol_invalid` 拒绝。

剩余非阻断风险：当前 schema 检查证明资源是 JSON object 且 `$id` 相同，但没有执行完整 JSON
Schema meta-schema 校验；`CallableComponent` 证明类别和 callable 边界，不静态验证 Python
函数签名与返回类型。这两点在安装插件信任边界内暂可接受，但 R2/R3 首次真实调用前必须通过
每类组件的调用合同测试，不能靠运行失败文本让 Worker 反推协议。

### 2. Agent 传递资源授权：通过

`worker_resources()` 从 Agent executor、workspace、Worker tool、显式资源和 prompt 根做闭合，
确定性收集所有传递只读 resource；权限模板和 operation 可达摘要使用同一已解析组件集合。
独立构造 prompt → skill 传递资源后，结果为：

```text
transitive-authority ('builtin:independent_skill', 'builtin:test_prompt')
```

未声明资源仍不会进入模板，网络和工具也没有从角色默认值补入。R1 只形成静态模板，没有提前
绑定 Artifact Ref 或真实任务路径，边界正确。

### 3. Effect 审批与 UI 下限：通过

- external Effect 同时强制接受语义和拒绝语义；缺任一侧均以
  `external_approval_options_invalid` 失败；
- projector 必填，必须解析为 kind=`projector` 的 `CallableComponent`；缺失和错误 kind 均失败；
- `accept_with_exception` 必须 `requires_reason=True`，否则以 `approval_reason_required` 失败；
- subject 必须精确来自 operation 输出端口，projector、问题和选项都进入 spec/digest；
- 内置假 Effect 已同时声明 Allow/Reject 和只读架构测试 projector。

独立反例中，“仅接受且无 projector”与“带例外接受但无理由要求”分别被
`approval_contract_invalid`、`approval_reason_required` 拒绝。没有发现插件可把 external 降级为
scientific/explore 或绕过人工审查的静态路径。

### 4. 网络和总资源上限：通过

- network 只接受 `none` 或有非空、非全局通配、去重域名和正请求上限的 `restricted`；
- `*` 和空域名均以 `network_scope_invalid` 拒绝；
- operation 总输入、总输出、collection 总字节和输出文件数与端口上限统一校验；单端口超过
  总输出上限以 `output_limits_inconsistent` 拒绝；
- 调度器安全投影已补齐输入/输出字节、文件数、内存、网络模式和最大请求数，没有泄露允许
  域名、组件路径或配置身份。

核心运行时硬上限仍属于 R2 精确 preflight；R1 没有错误地新建资源状态或预算表。

### 5. reviewer 端口兼容：通过

producer/reviewer 现在同时校验：

- schema identity 相同；
- schema resource 真实字节摘要相同；
- producer media types 是 reviewer 可读集合的子集；
- 指向同一已解析 codec；
- producer 所有 subject 输出的最小/最大基数整体落入 reviewer 输入端口范围。

独立构造的 codec、media、schema bytes 和 cardinality 四类不兼容均得到
`reviewer_port_incompatible`；reviewer digest 继续递归进入 producer digest，强制审查环仍失败
关闭。

### 6. 稳定错误边界：主体修复有效，但尚有上述残留

- 插件 iterable、声明结构、entry-point load、组件 import/module attribute 和普通组件解析错误
  已统一转换为稳定 `CatalogCompileError`；
- 新增的安装态坏插件从真实 wheel 的 `scidiscovery.plugins` 入口加载，组件模块 import 时抛
  `RuntimeError`，测试验证其得到 `component_implementation_error` 以及精确 plugin/field；
- Pydantic 严格冻结声明和编译前重新验证已关闭 `model_copy`/list 等畸形声明绕过。

但资源和最终摘要的 UTF-8 编码仍位于统一错误映射之外，因此本项只能判为部分通过。

## 三、总体目标与架构边界审查

### 符合目标的部分

- **Everything is Operation**：三个内置测试能力均由十字段 `OperationSpec` 组合已登记窄组件；
  spec 没有执行、调度或状态迁移方法；
- **单一注册入口**：新 compiler 只读取 `scidiscovery.plugins`，没有目录扫描 fallback，也不读取
  旧 role、transform、operation-spec 或 execution entry point；
- **编译后运行**：`compile_installed_catalog()` 一次启动编译并缓存不可变 catalog；编译阶段只
  解析组件，没有调用 Agent、Transform 或 Effect；
- **最小上下文授权**：Agent 静态模板明确输入暴露、任务私有相对工作区、工具、传递只读资源、
  模型、网络与资源界限，未声明维度按拒绝解释；精确 Artifact 和原生路径绑定仍留在 R2；
- **轻量控制面**：没有科学图、候选枚举、readiness、qualification、current、operation 状态机
  或持久化 catalog；没有领域流程顺序；
- **无生产接管**：旧 Artifact/Task/Approval/Execution/Worker、TCAD 和 scorer 生产代码相对基线
  无差异；当前只有旧路径具有运行权威，新 catalog 是尚未接管的编译基座，不是双写权威；
- **存储不变**：没有 migration、SQLite 表或新持久化记录；编译前后 schema 回归保持完全相同。

### 复杂度观察

`spec.py` 299 行、`catalog.py` 400 行，技术上满足 300/400 门；两者合计 699 行，十字段仍是
无状态声明。但文件已经贴住上限，且 catalog 有较多压缩到单行的检查。后续修复不得通过继续
压缩可读性来“满足”行数；应合并重复错误包装或抽取既有纯函数，同时仍遵守三个通用 operation
模块总计 1200 行和不新增 registry 的约束。这是复审关注项，不单独构成本轮架构打回。

## 四、独立执行证据

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. \
  pytest -q -p no:cacheprovider tests/operations
44 passed

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. \
  pytest -q -p no:cacheprovider
74 passed

sha256sum -c --quiet MANIFEST.sha256
通过（写入本报告前）

python scripts/build_git_release.py \
  --source . --output /tmp/scid-r1-round2-release --force
tracked source files: 228；发行目录及 tar.gz 成功生成

sha256sum -c --quiet /tmp/scid-r1-round2-release/MANIFEST.sha256
通过

git diff --check 404aeb1 -- \
  pyproject.toml src/scidiscovery tests/operations tests/fixtures docs/plans MANIFEST.sha256
通过

wc -l src/scidiscovery/operations/spec.py \
      src/scidiscovery/operations/catalog.py
299 / 400
```

安装态测试在仓库外工作目录中从 clean release 构建并安装 core、full 以及独立坏插件 wheel，
删除 `PYTHONPATH`/源码角色目录并确认 `scidiscovery` 来自 venv 前缀。core/full 只编译三个 builtin
测试 operation；旧领域 entry points 未被当作新 catalog fallback。该证据可信。

## 五、下一次复审门

下一次审查只需重新验证本报告唯一阻断：所有普通资源/声明规范化和摘要编码错误都映射为稳定、
带位置的 `CatalogCompileError`，且至少有一个真实安装态非法 UTF-8 插件负例。随后重跑 44 项
操作回归、全仓、Manifest、干净发行、diff、数据库零变化和 300/400 行数门。

若该项关闭且没有为此新增平行诊断表、运行状态或生产接管，本审查允许 R1 转为“通过”并进入
R2；否则仍只能在 R1 内修复。
