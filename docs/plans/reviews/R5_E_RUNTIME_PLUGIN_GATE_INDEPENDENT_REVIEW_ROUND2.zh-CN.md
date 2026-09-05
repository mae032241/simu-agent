# R5-E 运行时插件门禁第二轮独立复审

日期：2026-08-30  
审查者：未参与本轮修复的独立审查者  
结论：**通过；只放行 R5-F。**

## 1. 复审范围

本轮只复核首轮报告
`R5_E_RUNTIME_PLUGIN_GATE_INDEPENDENT_REVIEW.zh-CN.md` 的 F1，以及该最小修复可能造成的直接
退化；不重开已经通过的 R5-A—R5-D，也不把 R5-F/G 的发布或科学效果要求提前算作 R5-E 缺陷。
工作树没有可用的独立 R5-E Git 提交，因此以复审时当前共享工作树的精确字节为对象。除本报告
外，审查者没有修改生产代码、测试、计划或阶段状态。

来源声明：

- S1：首轮独立报告与 `R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 9 节；
- S2：`R5_E_RUNTIME_PLUGIN_GATE_IMPLEMENTATION.zh-CN.md` 当前修订；
- S3：`src/scidiscovery/operations/catalog.py`、`spec.py`、`runtime_plugins.py`；
- S4：`src/scidiscovery/artifact_agent/runtime_plugin_bindings.py` 与两个 daemon；
- S5：`tests/operations/test_r5_runtime_plugin_gate.py`、
  `test_r5_catalog_stages.py` 及本轮聚焦/全仓测试；
- S6：`scripts/r5_current_metrics.py`、冻结基线生成器、部署脚本与 systemd 模板。

## 2. F1 关闭判断

首轮 F1 已完整关闭。

当前编译器在同一次 `_validate_operation_contracts` 中，为每个声明 runtime factory 的插件建立一个
局部 `runtime_scope`。配置 Schema 和 runtime factory 都通过既有 `_resolve_component` 进入该
集合，其 `resources` 依赖按同一规则递归闭合。运行时身份摘要确定性编码：

- 消费插件编号与版本；
- 闭包内每个组件的全限定键；
- 组件提供插件的版本；
- 完整 `ComponentSpec`；
- 资源字节摘要；
- factory 的 `requires_worker_task_service` 静态权限合同。

因此，零 Operation 的 runtime-only 插件不再依赖“恰好有某个 Operation 把运行时组件带入可达
闭包”。目录摘要同时编码该运行时身份摘要。实现不散列 callable，不记录配置路径或内容，也没有
创建第二发现面。

独立反例确认以下每一种变化都会改变 `catalog.digest()`：

1. runtime-only 插件版本变化；
2. factory `ComponentSpec.implementation` 定位变化；
3. factory 本地递归资源内容变化；
4. 跨插件资源提供方版本变化；
5. 跨插件资源内容或提供方编号变化；
6. `requires_worker_task_service` 静态合同变化。

相同插件声明重复编译则摘要相同。由此，身份既确定又覆盖首轮反例及复审中发现的递归/跨插件
边界。

实际 daemon 负例不是只调用摘要纯函数：测试分别让 control daemon 和 Worker daemon 的真实
`main` 路径编译不同的合法 runtime-only 目录、读取同一原始配置、实际构建 contribution 并写出
各自摘要，只把阻塞 socket 的 server 替换为一次返回。随后现有部署健康探针因目录摘要不同而
失败关闭。版本漂移与 factory 定位漂移均覆盖；本地和跨插件资源闭包另有编译器专项负例。

## 3. 权威、边界与复杂度复核

| 检查问题 | 结论 | 证据 |
| --- | --- | --- |
| 运行时身份是否覆盖零 Operation、递归资源和跨插件所有权 | 通过 | S3、S5 |
| 身份是否确定且不散列 callable | 通过 | S3、S5 |
| 双 daemon 摘要是否真实走贡献构建并拒绝身份漂移 | 通过 | S4、S5 |
| `CompiledCatalog` 是否仍是唯一目录/工厂权威 | 通过 | S3、S5 |
| 新私有摘要映射是否构成第二 registry、缓存或进程状态 | 否；它是同一不可变目录内的编译派生值 | S3 |
| Root 本地 adapter、Worker 领取前 service 门及 capability/审批/执行是否退化 | 未退化 | S4、S5 |
| 摘要是否新增路径、内容或配置泄漏 | 否 | S4 |
| 文档是否如实描述递归身份与当前计量 | 通过 | S2、S6 |
| 是否新增表、科学对象、状态机、entry-point group 或在线协调 | 否 | S3、S4 |

新增身份映射没有独立发现、消费者或生命周期；它只能由同一次目录编译产生，并以
`MappingProxyType` 封存。该派生值留在 `CompiledCatalog` 内比另建身份服务更小，也复用了已有
组件闭包和规范摘要机制，符合奥卡姆边界。

独立复算当前复杂度：

- R0 六职责：`9818 / 13657`；
- `src/scidiscovery/operations/`：7 个 Python 文件、`2053 / 2060` 行；
- `src/ + plugins/`：144 个生产 Python 文件、`60723 / 62533` 行；
- `deploy/install.sh`：1026 行；
- 冻结基线生成器 SHA-256：
  `718eac8e17569cdbb7adeefe7e0e8cc12efab20cae96b614e4fdc77db40e51f5`。

修复没有以迁移统计、压行或新增模块逃避复杂度门。它保持 Everything-is-Operation、单一编译目录、
插件统一入口、最小 Worker 上下文/授权以及控制面只负责确定性门禁的既有 33 项约束族目标。

## 4. 独立验证

所有 Python/pytest 命令均严格串行，并先设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

本轮独立结果：

```text
pytest -q tests/operations/test_r5_runtime_plugin_gate.py \
  tests/operations/test_r5_catalog_stages.py
=> 12 passed in 2.28s

较宽的 catalog/runtime/plugin/deploy 聚焦集合
=> 80 passed in 43.28s

pytest -q
=> 296 passed in 90.48s

git diff --check
bash -n deploy/install.sh
相关生产模块 py_compile
=> 均通过
```

此外执行了不落盘的独立目录编译探针，确认递归资源内容、跨插件提供方编号/版本及
`requires_worker_task_service` 漂移均改变目录摘要。最新专项测试也已把本地递归资源和跨插件
资源/提供方版本写成持久负例。

未在本轮启动真实 systemd 管理器或外部 TCAD 求解器；二者不是首轮 F1 的必要证明。R5-F 仍须
执行发布/安装态总门，R5-G 仍须执行冻结科学效果回归，本轮通过不预先继承这些阶段的结论。

## 5. 门禁结论

结论为 **通过**。首轮唯一阻断 F1 已由确定性完整身份、实际双 daemon 摘要负例、递归及跨插件
回归共同关闭，且没有引入新的权威或复杂度反噬。

本报告 **只放行 R5-F**；不提前宣告 R5 总体完成，也不放行 R5-G 或后续发布。
