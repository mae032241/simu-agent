# R1 最小 OperationSpec 与启动期编译器独立审查

审查结论：**打回**。

审查基线：`baseline/8765-codex@404aeb1`。本次只审查 R1 新增的
`src/scidiscovery/operations/`、`src/scidiscovery/builtin_plugin.py`、根包唯一新入口及其
测试和实施记录；R0 已通过内容只作为行为基线，不重新裁决。

R1 已经建立了一个小型、无状态、未接管生产路径的编译基座，但当前声明与编译器尚未形成
计划要求的完整行为闭包。下列缺陷会让后续 R2 只能依赖隐式 schema/工作区/审批规则，或在
调用层再建立补充注册与特判；这正是本次重构要消除的断裂。因此在这些问题修复并复审前，
不得进入 R2。

## 一、阻断项

### 1. schema、collection 和组件协议没有被启动期编译闭合

位置：

- `src/scidiscovery/operations/spec.py:40-68`
- `src/scidiscovery/operations/catalog.py:67-82`
- `src/scidiscovery/operations/catalog.py:233-237`

可达场景：

1. 把内置 Agent 输入端口的 `schema` 改为不存在的 `missing.schema`，catalog 仍成功编译；
2. `OutputPortSpec` 没有主计划 17.1 明定的可选 collection 声明；
3. 非 resource 组件只要 `callable()` 即视为协议合格。把 workspace 实现替换为
   `builtins:print`，catalog 仍成功编译；
4. compiler 因而无法实现主计划列出的“缺失 schema”“非法共享工作区”和按组件类别检查
   最小协议等失败关闭门。

影响：

- 端口中的 schema 只是一个未经解析的字符串；若 R2 再去旧 schema/role/profile 表查找，
  会恢复平行注册和按名称补行为；若不查找，Worker 输出合同就不是可验证闭包；
- bundle/附件输出无法仅靠当前冻结 spec 完整表达，领域插件仍需在控制层另加 collection
  特判；
- workspace、codec、validator、projector 等类别在实现层没有可验证差异，误登记的 callable
  会越过启动门，最小上下文授权无法由 catalog 单独证明。

最小修复要求：

- 让每个端口 schema 指向同一插件入口内已登记且可读取的资源/validator 合同，并把其真实
  字节摘要纳入 operation digest；缺失或不可解析时用稳定 reason code 拒绝；
- 补齐最小 collection/bundle 合同，或在主计划中明确证明 codec 已完全替代 collection，
  并以安装态 bundle 负例证明无需第二注册；不能把问题留给按 profile 特判的 R2；
- 为每类可执行组件建立最小、可静态识别的 ABI。特别是 workspace 的根必须由核心绑定为
  单任务私有路径，组件不能返回或选择共享根；增加任意 callable 和共享根企图的负例。

### 2. Agent 权限模板漏掉可达的传递资源

位置：

- `src/scidiscovery/operations/catalog.py:186-207`
- `src/scidiscovery/operations/catalog.py:248-269`
- `src/scidiscovery/operations/spec.py:153-160`

可达场景：给 `test_prompt` 的 `ComponentSpec.resources` 增加一个 skill/resource。编译结果的
`component_ids` 包含该资源，operation digest 也覆盖它，但 `permission_template.resources`
不包含它。相同问题适用于 Agent executor、workspace 和 Worker tool 的传递资源。

影响：实现可通过可达组件看到一份资源，而 R2 按权限模板绑定 Worker 时看不到同一资源；
后续只能在调用层隐式补齐，或者任务运行时缺失。这使“组件闭包”“Worker 权限闭包”和摘要
成为三种不一致的视图，并可能形成静态上下文旁路。

最小修复要求：权限模板必须从同一可达闭包确定性派生全部 Worker 可见 prompt、skill 和只读
资源，明确区分仅供控制组件内部使用与可交付 Worker 的资源，并以传递资源正反例证明没有
隐式补入或遗漏。该模板仍不得包含精确 Artifact Ref 或实际任务路径，那属于 R2。

### 3. 外部 Effect 的人审和 UI 安全下限可以被插件降级

位置：

- `src/scidiscovery/operations/spec.py:97-117`
- `src/scidiscovery/operations/catalog.py:128-142`
- `src/scidiscovery/operations/catalog.py:276-288`
- `src/scidiscovery/builtin_plugin.py:161-183`

可达场景：外部 Effect 的 `ApprovalContract` 只保留一个映射到 `accept` 的选项，并令
`projector=None`，catalog 仍成功编译。当前内置 Effect 自身也没有 projector。编译器只检查
subject 是输出端口、问题非空和决定字符串合法，没有保证存在拒绝路径，也没有保证 UI 能以
受限、确定性的 ReviewDocument 呈现精确 subject。

影响：插件可以把“必须人工审批”降级成没有拒绝选择的形式门；没有 projector 或明确的核心
安全回退时，R4 只能新增按 operation/领域的 UI 特判。两者都违反“插件不能降低审批下限”及
“审批 UI 由同一 spec 编译”的目标。

最小修复要求：

- external 审批至少必须存在核心 `reject` 语义；接受、带例外接受和修订选项继续按声明提供；
- ApprovalContract 必须引用通过最小 projector ABI 校验的只读呈现组件，或者规范中冻结一个
  唯一的核心通用安全 projector 并由编译器显式写入摘要，不能以 `None` 表示未定义行为；
- 增加“仅接受选项”“缺失/错误 projector”“projector 未覆盖精确 subject”的负例。

### 4. 默认拒绝网络和资源上限只做了表面校验

位置：

- `src/scidiscovery/operations/catalog.py:93-107`
- `src/scidiscovery/operations/catalog.py:110-125`
- `src/scidiscovery/operations/spec.py:181-203`

可达场景：

- `NetworkPolicy(mode="restricted", allowed_domains=("*",), max_requests=1)` 成功编译；空域名
  `("",)` 也成功编译；
- 单个输出端口的 `max_item_bytes` 大于 operation 的 `limits.max_output_bytes` 时仍成功编译；
- scheduler 安全投影只给出 timeout 和总输出字节，没有给出计划 18.1 要求的完整资源上限，
  至少缺少内存和文件数。

影响：所谓 restricted 网络可等价于未受限网络；互相矛盾的端口与 operation 上限会把错误
推迟到 Worker finalization；调度智能体也无法根据完整成本边界选择 operation。后续若由 R2
临时解释这些矛盾，会再次出现两套准入语义。

最小修复要求：冻结并验证可执行的受限域名语法，拒绝空值和全局通配；校验端口数量、单项
大小、collection 文件数与 operation 总资源上限相容；调度安全投影补足不泄密的资源上限。

### 5. reviewer “可消费输出”的判断没有闭合 codec

位置：`src/scidiscovery/operations/catalog.py:306-320`。

可达场景：producer 输出与 reviewer 输入声明相同 schema 和相交 media type，但分别引用两个
不同 codec，catalog 仍成功编译并把 reviewer digest 纳入 producer digest。

影响：摘要闭合了两个不兼容声明，却没有证明 reviewer 能读取被审 Artifact；真实运行只能在
物化层失败，或者依赖隐藏 codec 转换。审查关系因此仍可能出现 producer → downstream 的
行为断裂。

最小修复要求：首版应要求相同的已解析 codec，或显式登记并编译 codec 兼容/确定性转换关系；
不得仅凭 schema 字符串和 media type 交集判定可消费。增加安装态不兼容 codec 负例。

### 6. “任一步失败都有稳定 reason code”尚未成立

位置：

- `src/scidiscovery/operations/catalog.py:67-82`
- `src/scidiscovery/operations/catalog.py:337-361`

可达场景：一个已安装组件模块在 import 时抛出 `RuntimeError`，`_load_implementation()` 只捕获
`ImportError/AttributeError`，原异常直接逃出；Python 类型注解也不是运行时门，插件把嵌套 tuple
误写为 list 等畸形声明时，规范化摘要可直接抛出裸 `TypeError`。

影响：启动仍会失败，但诊断不具有稳定 reason code 和插件/operation/字段位置；部署工具无法
把它与插件版本、回滚和修复动作可靠关联，也不符合主计划 19 的失败合同。

最小修复要求：在每一编译遍的插件边界把普通加载、结构校验和规范化异常转换成稳定的
`CatalogCompileError`，同时保留明确 reason code 与位置；不得吞掉 `KeyboardInterrupt`、
`SystemExit` 等进程控制异常。增加真实临时 wheel 或等价安装态坏插件负例，不能只在内存中调用
`compile_catalog()`。

## 二、已确认通过的部分

- `OperationSpec` 恰有十个冻结顶层字段，没有 `execute()`、调度循环或状态迁移；当前不是巨型
  operation 类；`spec.py` 275 行、`catalog.py` 399 行，符合 R1 行数门；
- 新 compiler 只读取 `scidiscovery.plugins`，没有源码扫描 fallback；清洁安装 core/full 均只
  编译内置三个架构测试 operation，旧领域 entry point 没有混入新 catalog；
- 编译顺序确为组件、operation、review/UI 三遍，插件/组件/operation 冲突、缺失引用、审查环
  和 Effect 后果降级等已有负例会失败关闭；
- operation digest 已覆盖规范、当前可达组件声明、资源字节、权限模板、插件版本和递归 reviewer
  digest；改变 prompt、网络策略或 reviewer version 会改变 producer digest；
- 调度投影未泄露 Python 实现路径、组件编号、配置身份或 digest；
- 本阶段没有修改旧 Task、Approval、Execution、Artifact、Worker 调用路径，没有新增 migration、
  数据库表、readiness、qualification、current 或科学本体；新 catalog 尚未成为第二运行权威；
- 旧 role/transform/operation-spec 入口当前仍是 8765 唯一活动路径，新入口只是未接管基座。
  这在 R1 是有界过渡，不构成当前双写或双权威，但必须按主计划在 R4 收敛，不能长期保留；
- R0 行为回归和现有 33 项权威/谱系/人工决定/执行边界没有因 R1 的未接管代码而退化。

## 三、独立运行证据

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. \
  pytest -q -p no:cacheprovider tests/operations
36 passed

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. \
  pytest -q -p no:cacheprovider
66 passed

sha256sum -c --quiet MANIFEST.sha256
通过（写入本报告前）

python scripts/build_git_release.py \
  --source . --output /tmp/scid-r1-independent-release --force
tracked source files: 227；release manifest 生成成功

git diff --check 404aeb1 -- pyproject.toml src/scidiscovery tests/operations docs/plans
通过
```

额外直接反例的实际结果：

```text
missing-schema-resource ACCEPTED
arbitrary-workspace-callable ACCEPTED
restricted-domain-'*' ACCEPTED
restricted-domain-'' ACCEPTED
output-exceeds-operation-limit ACCEPTED
approval-without-reject-or-projector ACCEPTED
transitive-resource-reachable True
transitive-resource-authorized False
mismatched-review-codec ACCEPTED
component-import-runtime-error RuntimeError（未转换为 CatalogCompileError）
```

## 四、未验证风险

- R1 尚未连接 Task/Worker/Approval/Execution，故本轮不能证明精确 Artifact、任务私有原生路径、
  broker 恢复和工具代理服务端拒绝会从权限模板一致派生；这些仍是 R2 的强制验收项；
- 尚未实现 TCAD、curve-score 或第二领域的 `scidiscovery.plugins` 入口，不能据此声称一次注册已
  实证跨领域接入；
- 没有真实浏览器 UI 和真实 external adapter 经过新 compiled operation；本轮仅能审查静态合同
  的安全下限；
- `catalog.py` 已达 399/400 行。修复阻断项不能直接突破复杂度预算；应先抽取或删除重复校验，
  且不得为 schema、workspace、approval 或 codec 新增平行 registry。

## 五、复审门

只允许在 R1 内修复上述六项，并补真实安装入口可失败的负例。复审必须再次运行安装态
core/full、全仓测试、manifest/release、数据库零变化和行数预算检查。修复不得提前新增
`operation_invoke`、迁移 TCAD、切换旧调用路径或修改持久化 schema。
