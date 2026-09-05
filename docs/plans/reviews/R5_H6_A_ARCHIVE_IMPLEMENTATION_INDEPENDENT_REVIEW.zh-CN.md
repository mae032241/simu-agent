# R5-H H6-A 一次性评估归档实现独立审查

日期：2026-08-31  
审查对象：当前工作树的 H6-A 实现候选  
审查边界：只验收归档、默认测试减法和恢复闭包；不实施 H6-B，不放行 H7

## 1. 结论

**通过，仅放行 H6-B。**

H6-A 逐项兑现了第二轮通过方案：十三份冻结源按原相对路径和 SHA-256 保存；活动树删除七个一次性
脚本和四个 runner，完整历史 baseline 与 conftest 留在归档；当前 baseline 的前三项按字节等价迁留；
活动 conftest 只删除无人消费的 `r5_e2e` wheel、wheel 解析和环境装配。默认 Operation 收集从317项
精确下降到292项，减少的正是21项 runner 和4项固定 Fig.4 验收。

独立复跑同时重现了临时派生树第一次的 `25 passed, 3 failed`，三个失败分别由缺少冻结 Git 基线对象
和 manifest 指向的持久 workspace 证据触发；补入这两个方案已声明的只读取证前提后，同一批归档
测试得到 `28 passed`。没有修改归档测试、生产代码或断言来制造通过，因此这是恢复闭包修正，不是
针对失败打补丁。

没有阻断项。H6-B 只能开始发布文档投影收窄；H6-C 和 H7 仍须等待各自独立门，本报告不放行二者。

## 2. 审查对象与方法

本轮按未提交工作树审查，不假定远端或 Git 基线代表当前候选。核对了：

- `R5_H6_ARCHIVE_AND_COHESION_CLOSURE.zh-CN.md` 第2、5、6、8节；
- H6 第二轮方案通过报告；
- `archive/r5-g-evaluation/` 全部文件、活动 `scripts/`、`tests/operations/` 和 conftest；
- 当前 baseline、catalog、运行时插件、Effect、审批 UI、Execution identity 与 InGaAs 替代覆盖；
- 当前生产指标、Operation 包、33项约束、阶段状态和发布构建入口。

关键候选字节 SHA-256：

| 对象 | SHA-256 |
| --- | --- |
| H6 实施方案 | `5c031ce09d11f7b56227619a27f8fe4add1bbaa8e8abd3184e752711336314e5` |
| H6 第二轮方案复审 | `9a2e990004539e311b9d3aed92f96962524d9e000451aa1ec202a76d25963867` |
| 归档 README | `d79abd36844d2ecca446702b3daf506d1c86d5cb305e5303efa9f75703124c79` |
| 归档 manifest | `312eaf0dfa45e330fb110ec02351315ae7e0ff283b92b9b9bc46090b0f61e74f` |
| 活动 operations conftest | `e1df5758ac3541f49becb17baa468c724ea832dbd835b1848d7ad231f09f0f82` |
| 当前 baseline 测试 | `368309daf5d53edd8295c68742514b58a63fc2d143689acac9b14f0a0b6202b7` |
| R5-H 主实施记录 | `0a285213a163586a6ffb88d7982eba4ea837a63d389bfa0db257bbaad6dd73f0` |

## 3. 归档完整性和单一产品入口

**通过。** 归档 README 的冻结表含13个唯一原路径、13个唯一归档路径和13个 SHA-256；逐项读取
归档文件重算均完全相同。归档 manifest 列出 README 加十三份冻结源，共14个非 manifest 文件，
与目录实际拥有的全部非 manifest 普通文件集合精确相等，`sha256sum -c` 全部通过；manifest 按校验
清单惯例不递归记录自身。归档中没有符号链接。

活动原路径状态符合机械减法：七脚本、四 runner 和旧完整 baseline 均不存在；活动 conftest 保留为
当前 harness。除冻结 fixture 自身外，生产、部署、打包和当前测试入口没有引用
`archive/r5-g-evaluation`，归档也不在 wheel、Operation catalog 或源发布树中，因此没有形成第二产品
入口、兼容入口或归档运行时。

冻结 fixture manifest 当前 SHA-256 为
`786164857890b73d5e56cc9efa058898c2463bf06c52698b2b76509e9795b124`，与归档记录一致。
`tests/fixtures/r5_e2e_tcad/`、测试插件、两个 manifest 引用的持久 workspace 目录均仍在原位；
归档没有复制、移动或接管这些外部证据，也没有接管 `.scidiscovery` 私有状态、`deliverables/` 或
`123/`。

## 4. 默认回归减法和行为等价

**通过。** 活动 conftest 与冻结副本只有三个语义相同的删除块：

1. 不再构建 `tests/fixtures/plugins/r5_e2e_tcad_plugin` wheel；
2. 不再解析该 wheel；
3. 不再创建 `r5_e2e` 安装环境。

`core`、`full`、`ingaas` 及其他负例环境保持不变。活动路径搜索仅在外部冻结 fixture/测试插件中
保留 `r5_e2e` 资料，默认 harness 和测试不再消费它。

`test_r5_current_baselines.py` 的完整字节恰好等于冻结 baseline 从文件开头至第四项测试前的内容，
不是重写后的近似版本。独立 `--collect-only` 得到292项；冻结五文件按 pytest 展开为28项，其中
21项来自四个 runner、7项来自完整 baseline。保留前三项后，默认收集量减少
`21 + (7 - 3) = 25`，与 `317 - 292 = 25` 精确一致。

后四项的当前产品不变量由以下36项聚焦集合验证并全部通过：当前 baseline 3项、installed catalog
9项、运行时插件配置7项、Effect 1项、基础审批 UI 1项、审批渲染5项、Execution identity 5项和
InGaAs 插件5项。归档 README 的映射因此有实际测试支撑，而不是把固定 Fig.4 科学量表提升为新的
产品规则。

## 5. 临时恢复闭包

**通过。** 本审查从当前 `build_git_release.py` 新建带 Git 初始化的临时源发布树，只按原路径恢复
归档的七脚本、五测试文件和冻结 conftest，并补入 `tests/fixtures` 与历史指标脚本。恢复后十三份
文件再次逐项核对 SHA-256，全部通过。

在没有历史 Git 对象和 workspace 证据时，独立运行得到：

- `25 passed, 3 failed in 43.10s`；
- 结构测试因 `r5_baseline_metrics.py` 无法读取冻结 commit 而失败；
- fixture 身份测试因首个持久 workspace 文件缺失而失败；
- replay 生命周期测试因同一 workspace 证据缺失而失败。

随后只补入原仓库 Git 对象历史和 manifest 已声明的两个持久 workspace 目录，同一归档测试、同一
断言重新运行得到 `28 passed in 50.67s`。这精确证实实施记录所述的首次失败分类和恢复前提。没有
复制私有 run state，也没有运行科学 Agent 或 TCAD solver；28项只证明冻结工程测试可取证恢复。
临时派生树在验证后已按其精确临时路径删除，活动仓库没有留下 wrapper、alias、symlink 或复活入口。

## 6. 独立测试证据

所有 pytest 均串行运行，并预先设置 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2`：

| 验证 | 结果 |
| --- | --- |
| 当前替代覆盖八文件 | `36 passed in 57.29s` |
| 默认 Operation 收集 | `292 tests collected in 0.77s` |
| 默认 Operation 全量 | `292 passed in 99.02s` |
| 部署、平台、33项架构约束 | `38 passed in 5.17s` |
| 临时恢复，缺两个外部前提 | `25 passed, 3 failed in 43.10s`，失败原因与记录一致 |
| 临时恢复，补入声明前提 | `28 passed in 50.67s` |
| 归档 manifest | 14/14 非 manifest 文件校验通过 |
| `git diff --check` | 通过 |

## 7. 架构、复杂度与放行边界

**通过。** 当前机械指标仍为：生产 Python 150文件/59,317行，Operation 包7文件/2,064行，R0核心
9,518行，Task职责聚合6,031行。与 H6-0 冻结值完全相同。H6-A 没有新增生产文件、Operation、
catalog 构造点、插件注册、路由、数据库对象、生命周期状态或入口校验；改动是归档、测试 harness
减法和状态记录，不把历史脚本泛化成服务或工作流。

这符合33项约束和“通用能力由启动编译 Operation catalog 注册、控制面只做必要权威门禁、领域逻辑
留在插件”的目标，也符合奥卡姆剃刀：删除25项一次性默认收集和一个无人消费安装环境，未用新
Registry、ArchiveService、迁移状态、兼容层或 facade 替代它们。

## 8. 阻断与非阻断项

### 阻断项

无。

### 非阻断边界

- 本报告不验证归档科学结论，科学 verdict 继续是 `blocked`；
- 当前发布脚本仍递归携带历史计划，这是预定的 H6-B 工作，不是 H6-A 缺陷；
- 巨型生产文件职责审计属于 H6-C；真实 Agent、工具和结构端到端回归属于 H7；
- 本报告只放行 H6-B。H6-B 必须独立审查通过后才能进入 H6-C，H6-C 通过后才可考虑 H7。

