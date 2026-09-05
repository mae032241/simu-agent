# R5-M2-03 可选论文图证据插件实现证据

日期：2026-09-01  
审查状态：实现与全量回归完成，等待未参与实现者独立审查  
放行范围：不放行 M3，不宣称 M2 完成

## 1. 要回答的问题

M2-03 不再为既有论文图闭环增加集合提交协议，而是先回答该能力是否属于 TCAD 默认闭环。消费者
账本以当前编译 Operation 的精确端口和生产源码引用为准，不以历史流程文档为准。

结论如下：

- 默认 TCAD Operation 没有消费 `science.evidence.extract.figure.v1` 或
  `science.evidence.audit.figure.v1`；
- 默认目录中图证据 manifest 与验证报告没有生产者，唯一消费者是曲线插件自己的 support Transform
  `scidiscovery.curve-bundle.figure-evidence.v2`；
- TCAD 对 `curve_score` 的真实依赖是曲线合同、规范曲线、归一化、评价和诊断，不要求论文图 Agent；
- 因而论文图 Agent 是可选产品能力，不是默认 TCAD 闭环的必要阶段。

## 2. 最小实现

1. `curve_score.plugin:PLUGIN` 不再无条件合并两个论文图 Agent 及其专用组件。
2. 新增独立分发包 `scidiscovery-curve-figure-evidence`，只通过既有
   `scidiscovery.plugins` 入口注册：
   - `science.evidence.extract.figure.v1`；
   - `science.evidence.audit.figure.v1`。
3. 可选插件依赖 `curve_score`，直接复用现有确定性数字化、校准、验证、Schema 和 Worker 工具实现；
   没有复制算法、目录、Run、Artifact 或注册表。
4. 通用安装器可显式选择 `curve_score,curve_figure_evidence`；只有选择可选插件时才检查
   `pdfimages`/`pdftoppm`，默认 TCAD 不再承担无关安装依赖。
5. Root 的 `public` 运行视图只排除已由同一后端能力判断标记为 `unavailable` 的项；`all` 诊断视图
   保留原 Operation 及精确原因。没有第二套能力判断。

本阶段没有新增数据库表、Run 状态、Root 工具、集合草稿或第二提交协议。

## 3. 编译目录结果

| 组合 | Operation | 公开 Agent | Local 可运行公开 Agent | 论文图 Agent |
|---|---:|---:|---:|---:|
| 默认 TCAD（builtin/general/curve/tcad） | 45 | 20 | 20 | 0 |
| 显式增加可选图证据插件 | 47 | 22 | 21 | 2 |
| 默认完整产品再加 InGaAs | 46 | 20 | 20 | 0 |
| 可选完整产品再加 InGaAs | 48 | 22 | 21 | 2 |

可选组合中，审查 Agent 为单输出，可在 Local 运行；提取 Agent 仍声明集合输出，故不进入 Local 的
`public` 调度视图，但在 `all` 中显示 `agent_collection_outputs`。这项诚实限制没有被包装成可运行。

默认完整目录摘要为
`31a380bac3a2e231a44f9f51d867962f37957129de5aac6e5f9f7381dd439600`；可选完整目录摘要为
`6f6592e5ca396cc05eb17b27420becdf0cd6f8b40cfebc77493d1ef07fcc1213`。

## 4. 回归证据

- 新增 `tests/operations/test_m2_optional_figure_plugin.py`，覆盖默认无论文图 Agent、可选插件只增加
  两个 Agent，以及 `public`/`all` 后端投影的一致性；
- 干净轮子矩阵新增显式 `figure` 环境，证明默认 curve/TCAD 轮子不携带可调度论文图 Agent，显式
  安装后专用工具可从安装包真实执行；
- 安装器预览和源发布回归覆盖新的可选插件路径；
- 聚焦目录、轮子、平台和领域边界回归：`27 passed in 49.44s`；
- 串行全量回归：`222 passed in 80.87s`；
- `git diff --check`：通过。

全量回归使用 `ulimit -v 7340032` 和 `MALLOC_ARENA_MAX=2`，未超过本轮 8 GiB 上限。

## 5. 复杂度与架构约束

- 生产 Python：142 文件、49,018 行；其中 `src` 为 96 文件/26,133 行，`plugins` 为
  46 文件/22,885 行；
- Operation 核心包仍为 8 文件/2,103 行；
- Local Root 工具仍为 30 个；
- 生产源码摘要为
  `0b5c37e315984e8dc476efa75bd791be9ba7060607551fcd91876fe311752eb2`；
- 新插件运行代码只有 2 个文件/60 行，声明复用现有实现，不形成第二编译器或第二注册入口；
- 默认产品减少两个不可运行公开 Agent，未用控制面扩张换取表面可用性。

因此候选实现满足 M2-C 的最小方向，但是否放行仍以独立审查为准。
