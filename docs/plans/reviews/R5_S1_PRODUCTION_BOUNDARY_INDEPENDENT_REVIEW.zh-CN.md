# R5-S S1 生产边界独立实现审查

日期：2026-08-31  
审查者：独立 critic `r5s_s0_independent_review`  
性质：只读实现、消费者、安装与发布边界审查  
审查候选计划摘要：`6e3f0d115e0dace4c2d65750d8f417012b59cf78f9d55d147c06e6a6945dcc70`  
结论：**通过；只放行 S2**

## 1. 审查范围

本轮绑定 S1 冻结候选，检查三项生产降级是否真实成立：架构测试能力退出核心产品插件、
`table_observation` 退出产品发布、未启用 Worker 进程方案退出产品命名空间。审查同时覆盖静态与
动态消费者、entry point、wheel、clean release、部署、正式 `spawn_agent`/Worker proxy 链、
33 项架构约束和奥卡姆减重目标。审查者没有修改候选代码或文档。

起点清单为 `R5_S1_START_SOURCE_SNAPSHOT.sha256`，216项，清单摘要为
`deb7cbe2b358f94e8e04c6717af15f0e7e673cc09e1b835f4140e41cbca9629d`；终点清单为
`R5_S1_END_SOURCE_SNAPSHOT.sha256`，208项，清单摘要为
`fcebc33985214e87bbb2a65e4169345440ef7586af2845f2bcf12a0b25e9f9d4`。

## 2. 独立结论

216→208 的生产路径差异严格只有 `table_observation` 六个文件和两个未启用 Worker 模块；共同
生产路径只有 `builtin_plugin.py`、根 `pyproject.toml` 和发布构建器发生变化。208项终点清单与
声明生产范围双向一致，逐文件摘要校验通过。

- 表格插件六个文件与起点字节级一致地移入独立 fixture wheel，仍通过唯一
  `scidiscovery.plugins` 入口注册，没有产生第二注册表；
- 核心 wheel 不含架构 fixture、表格插件和两个实验模块；两个旧生产模块没有转发、别名或动态
  导入残留，实际导入结果为 `ModuleNotFoundError`；
- `experiments/worker_process_v2` 不在产品包发现和 clean release 范围；正式 `spawn_agent`、
  Worker broker、Worker proxy 和部署路径摘要保持不变；
- clean release 独立重建为243个文件，manifest覆盖其余242项且全部校验；
- 基础通用、曲线和 TCAD 正式目录摘要保持不变；默认产品仍为216组件/45 Operation，加 InGaAs
  为225组件/46 Operation，外装 table fixture 后为239组件/48 Operation；
- 生产 Python 从150文件/59,200行降至144文件/57,207行，核心为33,321行。没有用生产拆文件、
  生成代码、兼容转发、插件名特判或针对单测的生产补丁伪造减量。

审查确认，保留在测试和实验目录的源码已从产品命名空间、启动编译、wheel、部署和发布责任中
真实退出。这是责任降级，不是假删除。S1 没有改变33项约束的语义。

## 3. 独立复测

在7 GiB虚拟内存上限、串行且禁用 pytest cache 的条件下：

- 跨边界聚焦：80项通过；
- 完整 Operation 回归：280项通过；
- Artifact、部署与 UI 回归：37项通过；
- 迁出的 Worker 进程实验：12项通过；
- `git diff --check`、终点清单和 clean release manifest 校验全部通过。

## 4. 放行边界

S1 通过，只放行 S2 的消费者审计、实现和独立审查。S3—S6、H7、R5 发布冻结和真实外部执行
不得提前启动；S2 不继承本轮结论。
