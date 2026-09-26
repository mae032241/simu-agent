# R1：最小 OperationSpec 与启动期编译器实施记录

状态：第三轮独立审查通过；本文件只记录证据，阶段状态以主计划第 26 节为准。

基线：`baseline/8765-codex@404aeb1`，叠加已经通过审查的 R0 测试与文档。

## 1. 本阶段实际完成范围

- `OperationSpec` 是十个顶层字段的冻结声明，没有执行、调度或状态迁移方法；
- `ComponentSpec` 在插件内登记 codec、validator、guard、Agent、Transform、Effect、workspace、
  Worker tool、projector 和只读 resource 等窄实现；operation 只持有组件引用；
- 根发行包只新增 `scidiscovery.plugins` 一个 operation 插件入口；目录编译器只读取已安装
  distribution 的这个入口，不扫描源码，也不读取旧 role、transform 或 execution 入口；
- 编译固定分为组件、operation、review/UI 闭包三遍；任一声明缺失、冲突、降级或不闭合都会
  用稳定 reason code 阻止整个 catalog 生成；
- Agent operation 编译出默认拒绝的静态权限模板，闭合输入暴露方式、工作区组件、工具、
  prompt/resource、模型、网络和资源上限；未声明工具与网络不会从角色默认补入；
- operation 摘要覆盖规范、可达组件、资源真实字节、非秘密配置身份、插件版本、权限模板和
  独立 reviewer 摘要；改变提示词内容、网络策略或 reviewer 行为都会改变生产者摘要；
- 调度器安全投影只含科学用途、适用/非适用边界、端口、后果、资源上限和审查要求，不含
  Python 路径、组件编号、安装配置或摘要；
- 内置插件只提供 Agent、确定性 Transform 和无真实副作用 Effect 三个架构测试 operation；
  它们不能用于科学任务或真实外部执行。

## 2. 明确没有完成的内容

- 尚无 `operation_invoke`，新 catalog 不接管 Task、Transform、Approval 或 Execution；
- 静态权限模板尚未绑定精确 Artifact Ref 和单任务原生路径，该职责属于 R2；
- 六个通用角色、TCAD、curve-score 和 UI 尚未迁移，旧入口在过渡期仍供 8765 路径使用，
  但新编译器不会把它们当作发现回退；
- 没有新增或修改 SQLite migration，没有新的 operation、权限或资格持久化状态；
- 没有声称 R1 已证明第二领域无核心修改接入或真实 TCAD 闭环，这些分别属于 R6、R7。

## 3. 失败关闭覆盖

自动负例覆盖：模块/属性缺失、实现协议错误、插件/组件/operation 重复、协议版本不符、
无人使用组件、未知或错误类型组件、空端口、端口重名、非法暴露方式、未登记工具、缺失
prompt、非受限网络、非法跨插件组件、缺失依赖、Effect 后果降级、外部审批缺失、UI subject
缺失、reviewer 缺失、reviewer 非独立、审查环、schema identity、collection 总量、传递资源
授权、reviewer codec、坏组件真实安装入口，以及资源/声明摘要的非法 Unicode 边界。

额外不变量包括：编译只解析而不调用任何 Agent/Transform/Effect；同一进程安装目录只编译
一次；完整安装环境中的旧领域 entry point 不会进入新 catalog；编译前后 SQLite schema
逐字相同。

## 4. 验证证据

| 检查 | 结果 |
| --- | --- |
| `PYTHONPATH=src:. pytest -q tests/operations` | 46 项通过；包含仓库外 clean-wheel 入口测试 |
| `PYTHONPATH=src:. pytest -q` | 76 项通过 |
| `git diff --check -- pyproject.toml src/scidiscovery tests/operations` | 通过 |
| `wc -l operations/spec.py operations/catalog.py` | 299 / 400，未超过 300 / 400 上限 |
| SQLite schema 前后比较 | 完全相同 |

8765 基线没有 `scripts/validate_architecture_constraints.py`，因此本阶段不能声称该脚本通过。
33 项约束由行为回归、安装态测试和独立跨边界审查覆盖；脚本缺失本身保留为审查可见限制。

## 5. 独立审查结果

- 首轮审查打回六组行为闭包问题；实现只在 R1 范围内修复；
- 第二轮有条件通过，并发现非法 Unicode 摘要错误尚未归一；
- 第三轮确认该残留已关闭，`KeyboardInterrupt` 与 `SystemExit` 不会被吞掉；
- 最终结论为“通过”，允许进入 R2；R1 仍未接管旧路径，因此不构成第二运行权威。

三轮报告均保存在 `docs/plans/reviews/`。R2 必须继续证明精确 Artifact 与任务私有路径的
调用期绑定、预检/写入同判断、权限摘要恢复不漂移，以及 Effect 复用既有审批和执行权威。
