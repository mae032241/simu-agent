# R5-A2 旧发现权威与旧创建入口删除第三轮独立复审

日期：2026-08-29  
审查对象：当前共享工作树中的 R5-A2 第二轮 F1-R2 修复候选  
结论：**不通过**  
门禁决定：**不放行 R5-B**

## 1. 复审范围

本轮未参与修复。审查前重新完整读取并遵循 `scid-cross-boundary-review`、
`scid-find-simplifications`、`scid-change-scope-checks` 三项技能，重点复核第二轮唯一阻塞的撤销、
事务和转换测试，并对旧权威、四启动入口及承重生命周期做最小回归。

只写入本报告，未修改生产代码、测试、计划或阶段状态。当前工作树仍是相对
`baseline/8765-codex` 的大范围未提交 R1—R5 候选；不存在独立 A2 修复提交，本报告只对审查时
精确字节作出结论。

## 2. 紧凑证据审计

来源只声明一次：

| 键 | 来源 |
|---|---|
| S1 | 第二轮报告 `R5_A2_LEGACY_AUTHORITY_REMOVAL_INDEPENDENT_REVIEW_ROUND2.zh-CN.md` |
| S2 | `R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 5.2—5.4 节及不可退化约束 |
| S3 | 修订后的 `R5_A2_LEGACY_AUTHORITY_REMOVAL.zh-CN.md` |
| S4 | `deploy/install.sh`、`deploy/install_transaction.py` |
| S5 | `tests/artifact_agent/test_deploy_scripts.py` |
| S6 | clean-wheel、旧入口负例、Agent/Transform/Effect/Worker authority 拥有者测试 |
| S7 | 本轮独立串行运行的部署 30 项、生命周期 12 项、旧入口 6 项、源码扫描与行数检查 |

| 物质问题 | 判定 | 证据 |
|---|---|---|
| 撤销是否位于生产事务武装之后 | 通过：生产 `install_all()` 的顺序为 begin → retire → activate | S4、S5 |
| 三个表面是否不依赖新插件集合而始终进入快照 | 通过：transport、两项 Skill、全部 unit 始终加入 begin transaction | S4、S5 |
| 成功后 Skill/transport/local unit 是否消失，回滚是否恢复旧字节 | 通过：受控测试调用真实删除函数与真实事务复制/回滚算法 | S4、S5、S7 |
| 删除是否只作用于已证明由该事务和安装器管理的对象 | **不通过：布尔武装与路径 basename 不能证明事务成员或安装器所有权** | S1、S3—S5 |
| 路径与符号链接边界 | 部分通过：Skill 目标/子树拒绝符号链接且删除无 glob；但允许任意同 basename 绝对路径，未绑定 manifest | S4、S5 |
| 转换测试是否真实覆盖生产边界 | 部分通过：调用真实撤销函数和事务算法；但手工置 `ROLLBACK_ARMED=1`，未证明待删路径属于该事务 | S4、S5、S7 |
| 旧发现/创建入口和四启动入口 | 通过 | S6、S7 |
| Task/Worker/Approval/Execution 边界 | 通过 | S6、S7 |
| 新注册表、状态机或发现权威 | 未发现 | S2—S7 |
| 复杂度与奥卡姆门 | 数量门通过；安全缺口可用既有事务补齐，无需新状态机 | S2、S4、S7 |

## 3. 第二轮阻塞已经关闭的部分

### 3.1 生产顺序与快照集合正确

`begin_install_transaction()` 无论新插件集合是否包含 TCAD，都把下列路径纳入同一个既有事务：

- `/usr/local/bin/scidiscovery-tcad-transport`；
- 当前 Codex Skill 根下的 `sentaurus-tcad-code`；
- `/etc/systemd/system/tcad-control.service`。

生产 `install_all()` 先构建并验证包，再调用 `begin_install_transaction()`；只有 manifest 已写入、
active/enabled unit 集已记录且 `ROLLBACK_ARMED=1` 后，才调用旧部署停用和
`retire_inactive_tcad_surfaces()`。TCAD 未选择时删除 Skill/transport；没有本地 TCAD service 时
删除 unit。之后才激活新包、生成配置并启动服务。这一顺序没有“先删后备份”的窗口。

### 3.2 删除动作本身有界，回滚算法可恢复字节

撤销函数没有 glob 或父目录递归：transport 与 unit 用精确文件路径删除，Skill 只删除末级名为
`sentaurus-tcad-code` 的目录。Skill 本体必须是非符号链接目录，子树中出现任何符号链接都会失败
关闭；对文件型目标的 `rm -f` 只移除链接本身，不追随其目标。

新动态测试先用真实 `begin_transaction()` 对三个临时表面建立 manifest 和备份，再 source 生产
`install.sh` 并调用生产撤销函数，确认三者消失；随后调用真实 `rollback_transaction()`，逐字节
检查三个旧内容恢复。它不是用字符串模拟删除或自写回滚算法。core-only/显式 TCAD 的真实
`--dry-run`、插件配置器执行和 clean-wheel core/full 也继续通过。

## 4. 仍未关闭的阻塞

### F1-R3（阻塞）：`ROLLBACK_ARMED` 和同名路径不能证明“精确受管”

第二轮要求只撤销**由本安装器管理且已进入当前事务**的表面。当前实现只验证：

- 全局布尔 `ROLLBACK_ARMED == 1`；
- 目标是绝对路径且 basename 分别为固定 transport/unit/Skill 名；
- Skill 不是符号链接且内部无符号链接。

它没有读取或核对 `TRANSACTION_ROOT/manifest.json`，也没有要求三个实际参数与 manifest 中
`tcad-transport-cli`、`unit-tcad-control`、`codex-skill-sentaurus-tcad-code` 的精确路径一致。测试正是
通过手工执行 `ROLLBACK_ARMED=1` 调用函数；shell 进程甚至没有设置为测试所创建的
`TRANSACTION_ROOT`。因此“测试目录事先另建了一个事务”与“删除函数只删该事务的成员”是两个
没有代码约束的事实。

更直接的可达场景是：用户从未安装 TCAD 插件，但个人 Codex Skill 根已存在一个自己维护的
`sentaurus-tcad-code` 普通目录。一次全新 core-only 安装会对该路径建立本轮通用回滚快照，然后
在成功路径永久删除它。目录中没有 ownership marker，代码也不比较受管来源或上次安装收据；
“名称相同且无 symlink”并不能证明它由 SciDiscovery 安装器所有。事务只能在本次失败时恢复，
不能阻止成功安装删除用户对象。

同样，撤销函数的三个可选参数允许任何具有相同 basename 的绝对路径；虽然生产唯一调用使用
默认路径，测试入口却说明当前防护依赖调用者自律，而不是 manifest 绑定。这里没有宽 glob，但仍
没有达到“精确受管目标”的删除前证明。

这违反插件禁用/能力消失的安全边界，也与第二轮明确要求的“不得无条件删除无法证明由本安装器
所有的同名用户目录”相冲突。它不是测试覆盖偏好，而是一个成功路径的数据删除缺陷。

#### 最小修复要求

1. 删除前把三个目标按稳定名称和绝对路径绑定到当前 `TRANSACTION_ROOT/manifest.json`；仅有
   `ROLLBACK_ARMED=1` 不足。可复用 `install_transaction.py` 的既有 manifest 校验，不新建数据库、
   注册表或生命周期。
2. 为安装器复制的领域 Skill 提供最小、内容绑定的安装器所有权证明（例如随 Skill 写入窄受管
   marker/receipt）；core-only 只撤销证明匹配的目录。对同名但无证明的用户目录必须保留并明确
   报告冲突，不得静默成功删除。
3. 转换测试必须把实际 `TRANSACTION_ROOT` 交给撤销路径，并增加两个负例：手工置位布尔但目标不
   在 manifest 时拒绝；同名无 ownership 证明的用户 Skill 在成功 core-only 路径中保持不变。
   继续保留 symlink、rollback 精确字节、干净 core/显式 TCAD 和 clean-wheel 正例。
4. 可去掉生产函数的任意路径参数，或让测试路径只能经当前 manifest 的稳定目标名解析；不得靠
   basename 白名单扩展 root 删除范围。

一个 manifest 成员检查和一个 Skill 所有权小收据足以闭合，不需要通用插件卸载器或新状态机。

## 5. 回归与复杂度

本轮未发现撤销修复影响科学或控制生命周期：

- 生产发现仍只有 `operations/catalog.py` 的一个 `scidiscovery.plugins` 入口消费者；旧三个组、
  role/transform loader 和四个旧 Root 创建工具仍不可达；
- compiled Agent/Transform/Effect 调用、Task authority、Worker 最小上下文、handoff-only、Approval、
  Execution 和恢复测试继续通过；
- core/full/full+InGaAs 的 clean-wheel 入口没有因部署修复漂移。

复杂度可复现：`deploy/install.sh` 为 1024 行，不超过冻结上限 1026；TCAD 插件配置器为 84 行；
operations 包仍为 2060 行。修复没有建立新注册表、所有权数据库、状态机、entry-point group 或
Operation 名分派。仓库仍不存在逐项编号的“33/33”自动验证器，本报告不伪称运行了该脚本；按
唯一权威、Worker 边界、人工审批、副作用和恢复等行为约束族复核，除 F1-R3 的受管删除证明外未见
新退化。

## 6. 独立运行证据

所有命令严格串行，并先设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

结果：

```text
pytest -q tests/artifact_agent/test_deploy_scripts.py
# 30 passed in 6.97s

pytest -q \
  tests/operations/test_baseline_plugin_discovery.py \
  tests/operations/test_baseline_agent_lifecycle.py \
  tests/operations/test_baseline_transform_lifecycle.py \
  tests/operations/test_baseline_effect_lifecycle.py \
  tests/operations/test_baseline_role_contracts.py \
  tests/operations/test_baseline_worker_authority.py
# 12 passed in 32.99s

pytest -q \
  tests/operations/test_r4_approval_operation.py::test_generic_root_cannot_create_a_scientific_qualification \
  tests/operations/test_tcad_operation_plugin.py::test_explicit_legacy_tcad_adapter_cannot_bypass_compiled_operation \
  tests/operations/test_runtime_plugin_configuration.py::test_generic_daemons_have_no_tcad_runtime_switches_or_imports \
  tests/artifact_agent/test_deploy_scripts.py::test_installer_probes_compiled_operation_authority_without_fixed_counts \
  tests/artifact_agent/test_platform_configuration.py::test_legacy_role_discovery_module_is_absent \
  tests/operations/test_catalog_installed_entrypoint.py::test_legacy_domain_entry_points_are_not_an_operation_discovery_fallback
# 6 passed in 24.43s

git diff --check
# 通过

wc -l deploy/install.sh plugins/tcad_artifact/deploy/configure_runtime.py
# 1024 + 84 = 1108

find src/scidiscovery/operations -maxdepth 1 -type f -name '*.py' -print0 \
  | sort -z | xargs -0 wc -l
# 2060 total
```

最后一组 6 项中有一项部署断言也包含在部署文件的 30 项内，故独立复跑覆盖 47 个不同测试。没有
重复实现方全仓 251 项；当前阻塞由生产删除控制流和缺失负例直接证明，重复科学测试不能改变
结论。

## 7. 最终结论

**不通过。**

第二轮要求的事务顺序、三个表面快照、成功撤销、失败字节恢复和正向安装测试均已实现，旧权威、
承重生命周期和复杂度也未回归。但当前撤销仍把“布尔已武装＋路径同名”当成“事务成员＋安装器
所有权”，会在成功的 fresh core-only 安装中删除无受管证明的同名用户 Skill。动态测试也手工绕过
了事务绑定，不能证明这一前置条件。

因此本轮**不放行 R5-B**。只能按 F1-R3 的最小范围补齐 manifest 成员绑定、Skill 所有权证明和
两个失败关闭负例，再由未参与修复的审查者复核；不得扩展为通用插件卸载系统。
