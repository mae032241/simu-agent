# R5-E 运行时插件门禁独立审查

日期：2026-08-30  
审查者：未参与 R5-E 实现的独立审查者  
结论：**打回；不得放行 R5-F。**

## 1. 审查边界与方法

本轮审查以 `R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 9 节为上位门，以
`R5_E_RUNTIME_PLUGIN_GATE_IMPLEMENTATION.zh-CN.md` 为实现声明，并检查当前工作树中的目录编译、
启动装配、两个 daemon、Root/Worker 本地门、systemd 模板、安装健康探针和相关测试。审查没有修改
生产代码、测试或阶段状态。

本报告把以下来源各声明一次，后文检查项只引用来源编号：

- S1：`docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 9 节；
- S2：`docs/plans/R5_E_RUNTIME_PLUGIN_GATE_IMPLEMENTATION.zh-CN.md`；
- S3：`src/scidiscovery/operations/catalog.py` 与
  `src/scidiscovery/operations/runtime_plugins.py`；
- S4：`src/scidiscovery/artifact_agent/runtime_plugin_bindings.py`；
- S5：两个 MCP daemon、Root Operation routes、Worker Router/dispatch、
  `execution_bridge.py`；
- S6：两个 systemd 模板与 `deploy/install.sh`；
- S7：`tests/operations/test_r5_runtime_plugin_gate.py`、
  `test_runtime_plugin_configuration.py`、`test_baseline_plugin_discovery.py`、
  `test_baseline_effect_lifecycle.py`、`test_r5_frozen_baselines.py`、
  `test_baseline_worker_authority.py`；
- S8：本轮独立执行的命令及其输出。

## 2. 阻断问题

### F1（阻断）：目录整体摘要没有绑定合法 runtime-only 插件的版本和工厂身份

`CompiledCatalog.digest()` 对运行时插件只编码
`(plugin_id, configuration_schema_digest)`。插件版本、配置资源的 `ComponentSpec` 和 runtime factory
的 `ComponentSpec`/实现定位均没有独立进入目录摘要。运行时组件虽然会进入同插件每个 Operation
的可达闭包，但编译器允许声明 runtime factory 且没有任何 Operation 的插件；现有 rogue runtime
插件测试也实际使用了这一合法形态。因此，这不是不可达的理论分支。

本轮用同一合法 runtime-only 插件定义编译两个目录，只把插件版本从 `1` 改为 `2`。两个目录均
成功编译，且 `catalog.digest()` 完全相同：

```text
1 a2a87f5a7e1667032ed11cf65e171454b42b2655ff6fdcb906abe4f0bfd59ccf
2 a2a87f5a7e1667032ed11cf65e171454b42b2655ff6fdcb906abe4f0bfd59ccf
```

相同 Schema 原始字节和相同配置原始字节下，两个 daemon 即使编译了不同版本的该运行时插件，
也会产生相同的目录摘要和三元组，`verify_runtime_summaries()` 无法拒绝。更换 runtime factory
组件定位而保持同一 Schema 内容时存在同类盲区。由此，S1/S2 中“两个进程使用同一份编译目录”
和“当前目录整体摘要”的结论尚不成立。systemd 的共同 Python 路径和运行身份校验能保护当前
标准部署，但不能替代所声明的通用目录摘要不变量，也不能覆盖编译器明确允许的插件形态。

最小修复边界：

1. 在同一次 `compile_catalog` 中为每个运行时插件形成不可变的运行时声明身份摘要，至少绑定
   `plugin_id`、插件版本、配置 Schema `ComponentSpec` 及资源摘要、runtime factory
   `ComponentSpec`；若纳入工厂的稳定静态合同（例如是否需要 Worker TaskService），也必须是
   可确定序列化的声明值，不得散列 callable 或创建第二注册表；
2. `CompiledCatalog.digest()` 必须编码该身份摘要，使零 Operation 的 runtime-only 插件发生版本
   或工厂声明漂移时目录摘要必然变化；现有 Operation 摘要、唯一目录和一次编译权威不应改变；
3. 新增合法零 Operation 运行时插件负例：版本漂移和 factory ComponentSpec/实现定位漂移分别使
   catalog digest 不同，并使由两个实际 daemon 生成的摘要在健康探针处失败关闭；
4. 保留当前配置 Schema 摘要和原始配置字节摘要的精确比较，不用重序列化配置，也不扩大为在线
   协调、持久状态或二次发现机制。

## 3. 其余检查结果

| 检查项 | 结论 | 证据 |
| --- | --- | --- |
| 缺配置、损坏 JSON、配置符号链接、重复 assignment、错误插件编号在 socket/摘要之前失败 | 通过 | S4、S5、S7、S8 |
| contribution 构建成功后才写摘要；摘要不含配置路径或内容 | 通过 | S4、S5、S7 |
| 原始配置字节变化可被探针发现，摘要解析拒绝缺失、符号链接、错误模式/形状/权限 | 通过 | S4、S7 |
| 当前 catalog 摘要能否完整代表运行时目录 | **不通过** | F1，S3、S8 |
| Root 只以本地 adapter 投影 Effect 可用性，缺绑定返回专门 preflight reason | 通过 | S5、S7、S8 |
| Worker 在 `claim_next/claim_exact` 前检查精确 Agent 所需的全限定本地 service | 通过 | S5、S7、S8 |
| 摘要未替代 capability、Approval、Execution 或恢复生命周期 | 通过 | S3—S7 |
| 唯一 `CompiledCatalog`/工厂发现权威，无新表、科研对象、在线协调或可变 registry | 通过 | S3—S6 |
| systemd 使用两个独立 `RuntimeDirectory`，安装健康门比较实际摘要后再做 MCP 探测 | 通过 | S6 |
| 33 项约束族、最小授权和通用插件目标 | 除 F1 外通过；F1 会削弱跨插件目录身份证明 | S1—S7 |

## 4. 复杂度与奥卡姆门

独立计量得到：

- R0 六职责：`9818 / 13657`；
- `src/scidiscovery/operations/`：7 个 Python 文件、2016 行，不超过 2060；
- `src/ + plugins/`：144 个生产 Python 文件、60686 行，不超过 62533；
- `deploy/install.sh`：1026 行；
- `runtime_plugin_bindings.py`：393 行；
- 冻结基线生成器 SHA-256 仍为
  `718eac8e17569cdbb7adeefe7e0e8cc12efab20cae96b614e4fdc77db40e51f5`。

393 行模块的职责集中在安全配置读取、一次启动装配、摘要读写和部署探针；没有数据库、缓存、发现
或请求期协调。把这部分移出 `operations/` 后没有掩盖全生产增量，三重口径能够发现搬移。因此除
F1 的身份缺口外，本轮没有证据支持继续拆类或新增服务。最小修复应留在现有目录编译摘要和现有
测试中，不得引入新的注册表、状态机或插件身份服务。

## 5. 独立命令证据

所有 Python/pytest 命令均先设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

已执行：

```text
pytest -q tests/operations/test_r5_runtime_plugin_gate.py \
  tests/operations/test_runtime_plugin_configuration.py \
  tests/operations/test_baseline_plugin_discovery.py \
  tests/operations/test_baseline_effect_lifecycle.py \
  tests/operations/test_r5_frozen_baselines.py \
  tests/operations/test_baseline_worker_authority.py
=> 27 passed in 45.04s

python scripts/r5_current_metrics.py
=> 9818/13657；operations 7/2016；production 144/60686；install 1026

git diff --check
bash -n deploy/install.sh
python -m py_compile <R5-E 相关生产模块>
=> 均通过

合法 runtime-only 插件版本 1/2 的目录摘要独立探针
=> 两个目录均成功编译，但 digest 相同，复现 F1
```

第一次聚焦 pytest 命令误写了一个不存在的测试文件，pytest 在收集前退出且没有运行测试；随后已
用上列正确文件集合重跑。由于 F1 已足以决定阶段门禁，本轮没有重复实现方声称的 293 项全仓测试；
这不影响可独立复现的目录身份阻断。

## 6. 最终门禁

R5-E 当前结论为 **打回**。F1 关闭并由独立复审确认之前，不得更新本阶段为通过，也不得开始
R5-F。除上述目录身份摘要及其实际双 daemon 负例外，没有要求扩展架构或返工已通过的本地
adapter/service、摘要文件、systemd 或生命周期边界。
