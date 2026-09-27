# R5-M5 插件所有权与默认产品面收敛实现证据

日期：2026-09-01

状态：返工后独立复审 PASS；M5 完成，仅放行 M6

对应计划：`../R5_M_POST_L_OCCAM_SIMPLIFICATION_PLAN.zh-CN.md`

## 1. 本阶段回答的问题

M5 不增加新的注册层或运行器，只回答四个问题：

1. 通用文件工具和领域无关 Schema 是否存在多个注册所有者；
2. 论文图能力是否仍以残缺 Operation 混入默认 TCAD 产品；
3. TCAD 是否在普通启动时同时加载多套执行适配器；
4. Hardened、portable 和远程管理模块是否仍污染默认 Local 路径。

结论是：公共能力已经收敛为单一提供者，可选论文图能力形成完整纵向插件，普通启动不再加载未选择
的运行产品；没有新增注册表、数据库事实、Root 工具、Run 状态或领域专用调度分支。

## 2. 公共组件所有权

### 2.1 文件工具

`builtin` 现在唯一注册下列七个工具：

- 分段写入的开始、分块和提交；
- 文本补丁；
- JSON 补丁；
- 删除；
- 移动。

`general_science`、`curve_score`、`tcad_artifact`、`ingaas_fig4` 和可选论文图插件不再重复注册这些
工具。注册为公开组件只表示其他插件可以显式引用，不会自动加入任何 Operation 权限；例如 TCAD 作者
显式获得删除工具，TCAD 审查者没有该工具。

### 2.2 通用科研资源

`general_science` 唯一拥有并公开领域无关的 JSON/不透明编解码器，以及科学 intake、foundation、
hypothesis、review、evidence audit、research objective、experiment portfolio、opaque 和 wildcard
等 Schema 资源。曲线、TCAD 和 InGaAs 只通过带 `plugin_id` 的 `ComponentRef` 消费这些资源。

完整六插件注册审计没有发现重复 `$id`。TCAD 的 `project_schema` 由 TCAD 唯一拥有并公开，InGaAs
显式引用，不再复制。

### 2.3 提供者可以独立安装

目录编译器过去一方面允许跨插件引用公开组件，另一方面又拒绝“本次组合中尚未被消费”的组件，导致
`core-only` 和提供者先安装无法成立。现在只豁免未被消费的 `public=True` 导出；任何未被消费的私有
组件仍以 `component_unused` 失败关闭。对应正负测试同时存在，因此该改动不会把私有死组件藏起来。

## 3. 可选论文图插件

默认 `curve_score` 不再注册没有默认生产者的论文图 bundle 转换。显式安装
`curve_figure_evidence` 后一次增加且只增加三项能力：

1. 图像证据提取 Agent；
2. 独立图像证据审查 Agent；
3. 已审查图像证据到曲线 bundle 的确定性转换。

三项 Operation、所需提示、Schema、校验器、语义合同和转换组件由同一个可选插件入口注册；默认目录
完全看不到它们。它复用曲线实现代码，但不建立第二目录、兼容转发或插件私有调度路径。

## 4. TCAD 执行产品与资源合同

### 4.1 只加载被选择的适配器

TCAD 继续支持 `socket` 和 `command` 两种管理员显式配置，但 `runtime_plugin` 不再在模块导入时同时
加载两套适配器。构建运行贡献时只导入配置选中的实现；两个隔离子进程分别证明：

- 选择 socket 后只出现 `execution_adapter`，不出现 `command_adapter`；
- 选择 command 后只出现 `command_adapter`，不出现 `execution_adapter`。

没有把两套纯标准库适配器再拆成两个发行包。这样做不会减少默认依赖或已加载代码，只会增加包、入口
和版本胶水；M5 因而选择“显式配置加惰性加载”这一更小的实现。SSH、Python 3.6 runner 和守护进程仍
是显式管理/进程表面，不进入普通启动导入路径。调试继续复用所选适配器和同一生命周期。

### 4.2 资源类型唯一

工程打包不再定义自己的 `ProjectExpectedOutput` 和 `ProjectResourceLimits` 模型。旧导出名只是在源码
级指向执行合同的 `ExpectedOutput` 与 `ResourceLimits`，打包时也不再进行 JSON 往返复制。测试确认
两组名称分别是同一个类型对象。

## 5. 管理和加固能力退出默认导入

以下模块改为仅在显式选择对应命令或后端时导入：

- portable bundle 管理命令；
- Hardened Worker MCP、加固文件和工作区实现；
- TCAD command/socket 适配器；
- TCAD 守护、SSH 和 Python 3.6 runner。

默认 CLI、Local runtime、Codex 平台、核心/通用/曲线/TCAD 目录编译的隔离子进程证明上述模块均不
在 `sys.modules`。显式 Hardened 回归仍能运行纯 MCP Operation；SEC-002 的 Local 原型限制没有被
改写成已解决。

## 6. 重复实现审计

完整注册集合只报告两类“相同 Python 实现”复用：

- 曲线与论文图插件各有一个非空校验组件，但分别绑定诊断语义合同和图证据语义合同；强行共享一个
  无合同校验器会被目录编译器以 `validator_semantic_contract_mismatch` 正确拒绝；
- TCAD 作者与审查工作区共享空 `WorkspaceContract` 值，但前者绑定物化、文件策略、收尾和快照，
  后者只绑定只读物化，配置身份也不同。

二者都不是重复所有权，合并反而会扩大审查者权限或丢失精确语义绑定。除此之外没有重复 Schema
标识或重复公共组件实现。

## 7. 复杂度变化

| 指标 | M4 通过态 | M5 候选 | 变化 |
|---|---:|---:|---:|
| 生产 Python 文件 | 140 | 140 | 0 |
| 生产 Python 行数 | 47,428 | 47,389 | -39 |
| 默认五插件 Operation | 44 | 43 | -1 |
| 默认五插件组件 | 209 | 186 | -23 |
| 默认 Agent / Transform / Approval / Effect | 20 / 20 / 3 / 1 | 20 / 19 / 3 / 1 | Transform -1 |
| 安装可选论文图后的 Operation | 46 | 46 | 0 |
| 安装可选论文图后的组件 | 未冻结 | 199 | — |
| Root 工具、Run 状态、数据库事实 | 不变 | 不变 | 0 |

插件规模为：builtin `7/0`、general `56/14`、curve `40/8`、TCAD `77/20`、InGaAs `6/1`、
可选论文图 `13/3`，数字依次为组件/Operation。

当前生产树摘要：

```text
174ea93ea60f6b8d616b3af8077065d0a8355383cd6403dd4c88a69584df13f5
```

默认五插件目录摘要：

```text
1ffe9a189ec7dd9e721c7e290452462f3d517ac45ea44bcaeefe0817539dd80e
```

安装可选论文图后的目录摘要：

```text
9a3b85190354fe6ae05cc6b99612a8d4c8e5c7a4244df1d0e320d17643b85719
```

## 8. 自动化证据

串行测试均设置 7 GiB 虚拟内存上限和 `MALLOC_ARENA_MAX=2`。

聚焦的插件所有权、运行产品和可选后端回归：

```text
42 passed in 5.93s
```

扩展的目录、安装、领域边界、曲线、TCAD、InGaAs、Hardened 与 Local 回归：

```text
136 passed in 64.82s
```

M3 冻结语料已显式安装可选论文图插件。由于 M5 有意改变组件所有者，目录摘要、Operation 摘要及其
派生请求指纹会变化；测试只递归排除这些编译身份字段。首轮审查返工后，19 个未改变合同的 Transform
继续逐字段比较全部转换内容、媒体、Schema、父引用、幂等重放、冲突拒绝、修订和 guard。论文图
bundle 单独明确断言转换内容和其他行为不变，同时输出父链从 manifest/report/table 三类精确扩为
intake/audit/manifest/report/table 五类；该准入变化没有被排除或伪装成等价。

最终完整串行回归：

```text
pytest -q
234 passed in 108.43s
```

M5 受影响的生产与测试模块已做无落盘语法编译，`git diff --check` 通过。测试覆盖真实安装
入口、盲 CSV 插件单入口接入、Local TCAD、显式 Hardened、默认/可选目录组合和两种 TCAD transport
隔离加载。

## 9. 当前判断

M5 把注册所有权集中起来，但没有把公共组件变成隐式权限，也没有为可选功能建立第二套系统。默认
产品减少一个悬空转换和 23 个重复/非默认组件；可选插件仍完整恢复论文图纵向能力。TCAD、Hardened
和 portable 的代码被保留，但不再由普通启动提前加载。

本文件只证明实现候选与自动化证据，不能自行放行 M6。必须由未参与实现的新独立审查者复核后，M5
才可标记完成。

## 10. 首轮独立审查与返工

首轮报告
`../reviews/R5_M5_PLUGIN_OWNERSHIP_AND_DEFAULT_SURFACE_INDEPENDENT_REVIEW.zh-CN.md` 结论为 FAIL。
审查者用真实 Root 复现：bundle 只绑定 manifest、validation report 和 curve tables 时，即使没有
任何独立审查 Artifact，`operation_preflight` 仍返回 admissible。原因不是 Transform 函数缺少一个
条件，而是 Operation 输入合同没有消费被审 `scientific_intake` 与审查者输出 `evidence_audit`，三项
能力只是共置、没有闭合。

返工没有增加审批实体、状态机、注册表或 Operation 特判：

- bundle 的已编译输入新增精确 `scientific_intake` 和 `evidence_audit`；
- Root 既有 producer review admission 自动要求 audit 来自
  `science.evidence.audit.figure.v1`、以该 exact intake 为 reviewer input 且 verdict 被接受；
- 既有 `figure_parentage` guard 要求 validation report 覆盖 exact manifest/全部 table，同时 audit
  覆盖 exact intake/manifest/report/全部 table；
- 新增真实 Local audit Agent Run 和 Root preflight 正例，以及缺 audit、未受信 audit、旧 intake
  revision、混合 table family 四类负例；
- M2/M5 oracle 显式断言这次父链收紧，其他 19 个 Transform 的严格等价范围不减。

返工聚焦集为 `31 passed in 81.04s`，最终全量为 `234 passed in 108.43s`。全新独立复审见
`../reviews/R5_M5_PLUGIN_OWNERSHIP_AND_DEFAULT_SURFACE_INDEPENDENT_REREVIEW.zh-CN.md`，结论 PASS；
其独立运行 B1、M3 oracle 和防退化三组共 31 项，全部通过。M5 完成，仅放行 M6；不宣称 R5-M
完成，`SEC-002` 仍为 `known_issue`。
