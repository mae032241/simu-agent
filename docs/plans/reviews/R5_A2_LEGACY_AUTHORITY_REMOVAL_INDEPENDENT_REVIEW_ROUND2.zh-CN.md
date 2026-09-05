# R5-A2 旧发现权威与旧创建入口删除第二轮独立复审

日期：2026-08-29  
审查对象：当前共享工作树中的 R5-A2 首轮 F1 修复候选  
结论：**不通过**  
门禁决定：**不放行 R5-B**

## 1. 复审范围

本轮未参与修复。复审前重新完整读取并遵循 `scid-cross-boundary-review`、
`scid-find-simplifications`、`scid-change-scope-checks` 三项技能，核对当前架构、33 项行为约束族、
R5 第 5.2—5.4 节、首轮独立报告及修订后的 A2 实现记录。

复审以首轮唯一 F1 为主线，同时对其可能影响的唯一发现权威、Root 创建入口、Task/Worker 权威、
Approval/Execution 生命周期和四个真实启动入口做最小回归。只写入本报告，未修改生产代码、测试、
计划或阶段状态。

当前工作树仍是相对 `baseline/8765-codex` 的大范围未提交 R1—R5 候选，不存在可直接用 Git 表示
的独立 A2 修复基线；本结论只适用于审查时的精确工作树。

## 2. 紧凑证据审计

来源只声明一次：

| 键 | 来源 |
|---|---|
| S1 | 首轮报告 `R5_A2_LEGACY_AUTHORITY_REMOVAL_INDEPENDENT_REVIEW.zh-CN.md` |
| S2 | `R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 5.2—5.4 节与不可退化约束 |
| S3 | 修订后的 `R5_A2_LEGACY_AUTHORITY_REMOVAL.zh-CN.md` |
| S4 | `deploy/install.sh`、`deploy/plugin_selection.py`、systemd 模板 |
| S5 | `plugins/tcad_artifact/deploy/configure_runtime.py` |
| S6 | `tests/artifact_agent/test_deploy_scripts.py` |
| S7 | clean-wheel 四入口、Agent/Transform/Effect 生命周期、Worker authority 和旧入口负例测试 |
| S8 | 本轮独立串行运行的 47 项测试、源码扫描、行数计数和 `git diff --check` |

| 物质问题 | 判定 | 证据 |
|---|---|---|
| 干净 core-only 预演是否不选、不导入、不要求、不渲染 TCAD/curve | 通过 | S4、S6、S8 |
| 显式 TCAD 选择是否才为 control/Worker 注入配置并渲染本地服务 | 通过（干净安装路径） | S4、S6、S8 |
| TCAD 配置算法是否插件自有且无第二注册表/Operation 名分派 | 通过 | S4、S5、S8 |
| core-only 与显式 TCAD 预演、配置器执行是否真实可信 | 通过：执行真实安装脚本 `--dry-run` 和真实配置器进程，不是字符串替身 | S5、S6、S8 |
| 从已选 TCAD 切换为 core-only 后领域能力是否消失 | **不通过：旧 Sentaurus Skill 和 TCAD unit 文件仍留在活动安装表面** | S1、S3、S4、S6 |
| 旧发现/创建权威和四启动入口是否回归 | 通过 | S7、S8 |
| Task/Worker/Approval/Execution 边界是否回归 | 通过 | S7、S8 |
| 复杂度与奥卡姆门 | 局部通过：主脚本净减 32 行，插件配置器 84 行且职责内聚；但禁用路径未闭合 | S2、S4、S5、S8 |

## 3. 首轮 F1 已正确修复的部分

### 3.1 干净 core-only 路径已真正去除隐式 TCAD 选择

- `deploy/install.sh:10` 的 `SCID_PLUGINS` 默认值为空；空选择不会调用本地插件解析器。
- 通用 `require_sources()` 不再要求 TCAD 插件、Sentaurus 手册/Skill 或 TCAD systemd 模板；
  `validate_source()` 只导入通用包，不再 `import tcad_artifact`。
- TCAD 状态目录、手册/工具、`TCAD_COMMAND_CONFIG` 和领域部署源码只在已解析选择集合包含
  `tcad_artifact` 后检查。
- `render_units()` 在 core-only 时给 control/Worker 传空插件配置参数，且不渲染
  `tcad-control.service`。本轮真实 core-only `--dry-run` 通过，输出中只有三个通用服务。

这关闭了首轮发现的“标准入口无条件要求 TCAD”的主要缺陷。

### 3.2 显式 TCAD 路径仍可用，配置算法已经归插件所有

选择集合精确包含 `tcad_artifact` 时才设置 `TCAD_ENABLED`，加入 `sentaurus-tcad-code` Skill，给
通用两个 daemon 传 `tcad_artifact=<config>`，创建 transport wrapper，并在没有外部 command
transport 时渲染本地 TCAD service。

policy 迁移、默认 smoke policy 和 socket/command transport JSON 的物化算法已移到
`plugins/tcad_artifact/deploy/configure_runtime.py`。该文件只消费显式路径参数并调用 TCAD 插件
自己的 policy 迁移函数；没有 entry-point 扫描、目录缓存、Operation 名称判断或新的生命周期。
通用安装器保留一个对显式 `tcad_artifact` 部署选择的窄条件，这是首轮允许的修复方案，没有形成
第二注册表。

本轮实际执行该配置器，生成的 policy 和 socket transport 与输入路径一致。显式
`tcad_artifact,curve_score` 的真实 `--dry-run` 同样通过并只在该路径渲染 TCAD service。

## 4. 仍未关闭的阻塞

### F1-R2（阻塞）：插件禁用/能力消失路径没有撤销先前激活的 TCAD Skill 与服务单元

首轮最小要求不是只让“全新 core-only”变绿，而是要求只有显式选择 TCAD 才启用其 Skill、配置、
transport 和 service。当前从一次显式 TCAD 安装切换为 core-only 时：

1. `PLATFORM_SKILLS` 在 core-only 只包含 `scientific-paper-evidence`，但
   `install_platform_skills()` 只覆盖当前选择的 Skill；没有删除或停用先前由本安装器复制到
   `${service_home}/.codex/skills/sentaurus-tcad-code` 的目录。Codex 仍会把该 Skill 作为已安装能力
   发现，尽管 TCAD 插件已经不在 compiled catalog 中。
2. `retire_old_deployment()` 会停用 `tcad-control.service`，但删除列表只移除旧 service 和 TCAD
   drop-in，不删除 `/etc/systemd/system/tcad-control.service` 本体。core-only 的
   `install_units()` 不会覆盖或删除它，因此旧 TCAD unit 仍留在安装表面，只是当前未启动。
3. transport wrapper 会在 core-only 时删除，TCAD 配置也不再传入 daemon；这两项是正确的。但
   A2 实现记录第 4 节所称“未选择时会清理属于 SciDiscovery 的旧 TCAD 部署残留”仍不符合实际
   字节。

这不是插件热卸载或活动任务跨版本迁移；它是标准离线安装器用新的显式插件集合替换旧部署时的
能力消失边界。R5 虽不实现通用插件生命周期状态机，但安装器仍必须保证最终激活面与当前选择
一致。残留 Skill 尤其会越过 compiled Operation 的最小上下文和单一能力权威：领域 Python 包与
Agent 已删除，Codex 却继续看到该领域 Skill。现有两个干净预演测试没有先种入旧 TCAD 安装物，
因此无法发现这一回归。

#### 最小修复要求

1. 在 core-only/未选 TCAD 的安装事务中，撤销**由本安装器管理**的
   `sentaurus-tcad-code` Skill 和 `tcad-control.service` unit；保留科学状态和历史配置可以接受，
   但它们不得继续出现在 Codex 能力或 systemd 已安装单元表面。
2. 复用现有 install transaction 对这些精确路径做备份/回滚，不新增插件注册表、所有权数据库或
   生命周期状态机；不得无条件删除无法证明由本安装器所有的同名用户目录。
3. 增加“先显式 TCAD、再 core-only”的受控安装转换测试，至少种入安装器管理的 Skill、unit、
   transport 与配置引用，验证转换后：TCAD Python/Agent 不在目录、Skill 不可见、unit 不存在或
   不再属于当前部署、transport 不存在、两个通用 daemon 无 TCAD 配置；同时保留显式 TCAD 正例
   和回滚覆盖。
4. 修正 A2 实现记录关于“清理旧 TCAD 部署残留”的表述，待上述转换真实通过后再写成已实现
   事实。

该修复只需要给既有部署事务补齐两个精确受管目标和一个反向转换，不需要引入新抽象。

## 5. 回归与复杂度判断

F1 修复未触碰 Operation、Task、Approval、Execution 或 Worker 生产实现。独立回归确认：

- 生产 `entry_points()` 消费仍只有 `operations/catalog.py` 的唯一
  `scidiscovery.plugins` 组；旧三个组、旧 loader 和源码角色发现无生产命中；
- 四个旧 Root 创建工具仍从真实 router 失败；私有 compiled Transform/Effect 无第二调用者；
- Task 新建仍要求精确 compiled authority，Worker 最小上下文、handoff-only、恢复和 Effect
  生命周期拥有者测试通过；
- core/full/full+InGaAs clean-wheel 启动与目录回归通过。

复杂度口径可复现：`deploy/install.sh` 从首轮 1026 行降至 994 行，插件自有配置器 84 行，二者合计
1078 行；operations 包保持 2060 行。新增配置器收纳的是从通用安装器移出的领域算法，没有复制
注册或状态权威，符合奥卡姆方向。仓库仍没有逐项编号的“33/33”自动验证器，本报告不伪称运行了
该脚本；按唯一权威、谱系、Worker 边界、人工决定、副作用和恢复约束族复核，除 F1-R2 的插件
能力消失外未见新退化。

## 6. 独立运行证据

所有命令严格串行，并先执行：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

本轮结果：

```text
pytest -q tests/artifact_agent/test_deploy_scripts.py
# 29 passed in 7.19s

pytest -q \
  tests/operations/test_baseline_plugin_discovery.py \
  tests/operations/test_baseline_agent_lifecycle.py \
  tests/operations/test_baseline_transform_lifecycle.py \
  tests/operations/test_baseline_effect_lifecycle.py \
  tests/operations/test_baseline_role_contracts.py \
  tests/operations/test_baseline_worker_authority.py
# 12 passed in 32.70s

pytest -q \
  tests/operations/test_r4_approval_operation.py::test_generic_root_cannot_create_a_scientific_qualification \
  tests/operations/test_tcad_operation_plugin.py::test_explicit_legacy_tcad_adapter_cannot_bypass_compiled_operation \
  tests/operations/test_runtime_plugin_configuration.py::test_generic_daemons_have_no_tcad_runtime_switches_or_imports \
  tests/artifact_agent/test_deploy_scripts.py::test_installer_probes_compiled_operation_authority_without_fixed_counts \
  tests/artifact_agent/test_platform_configuration.py::test_legacy_role_discovery_module_is_absent \
  tests/operations/test_catalog_installed_entrypoint.py::test_legacy_domain_entry_points_are_not_an_operation_discovery_fallback
# 6 passed in 24.18s

git diff --check
# 通过

wc -l deploy/install.sh plugins/tcad_artifact/deploy/configure_runtime.py
# 994 + 84 = 1078

find src/scidiscovery/operations -maxdepth 1 -type f -name '*.py' -print0 \
  | sort -z | xargs -0 wc -l
# 2060 total
```

29、12、6 三组测试无重叠拥有者场景，合计 47 项。本轮没有重复实现方的全仓 250 项：当前阻塞由
安装事务的确定控制流和缺失的能力消失测试直接证明，重复科学/Schema 测试不能改变结论。

## 7. 最终结论

**不通过。**

首轮 F1 的主要部分已经正确修复：全新 core-only 安装不再隐式要求 TCAD；显式 TCAD 选择仍能
预演；TCAD 配置算法已归插件所有；旧发现/创建权威和承重生命周期没有回归，复杂度也没有反弹。

但“只有显式选择才启用领域能力”尚未形成对插件集合替换封闭的总函数。TCAD → core-only 后旧
Sentaurus Skill 和 TCAD service unit 仍保留，现有测试只证明两个干净起点，不能证明能力消失。
因此本轮**不放行 R5-B**。只能按 F1-R2 的精确最小范围补齐受管资源撤销、事务回滚和转换测试，
再由未参与修复的审查者复核；不得在此之前进入 R5-B。
