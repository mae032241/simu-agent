# R5-A2 旧发现权威与旧创建入口删除第四轮独立复审

日期：2026-08-29  
审查对象：当前共享工作树中重新冻结的 R5-A2 第四轮候选  
结论：**通过**  
门禁决定：**放行 R5-B**

## 1. 审查边界

本轮未参与修复，并在候选字节更新后从头复审，没有沿用中断前的观察或第三轮的通过项。审查完整
遵循 `scid-cross-boundary-review`、`scid-find-simplifications` 和
`scid-change-scope-checks`，只验证 F1-R3 修复、与其相邻的部署/插件生命周期，以及旧权威和承重
生命周期是否回归；没有实施 R5-B，也没有修改生产代码、测试、计划或阶段状态。

工作树仍是相对 `baseline/8765-codex` 的大范围未提交 R1—R5 候选，无法把第四轮修复隔离成一个
提交。本结论只约束审查时的精确工作树。关键字节摘要为：

| 文件 | SHA-256 |
|---|---|
| `deploy/install.sh` | `7c956bd766b0fc50ec04f7d03bf6464900c74e7b5a2a44498b9b9dbaeed76bf7` |
| `deploy/install_transaction.py` | `c21de5f9238abc928f9d2e9440d544a492f22e1f3cf7e0f8530c650828eb0f3a` |
| `tests/artifact_agent/test_deploy_scripts.py` | `f035edf5338cfd69e7674db68874ae5389668b12c947fee165916026bd33a21a` |
| `docs/plans/R5_A2_LEGACY_AUTHORITY_REMOVAL.zh-CN.md` | `f444d0abb9c469fc4dcb16ca6030c248e1c9537818ea87cf78bf0f18c95df6b3` |

## 2. 紧凑证据审计

来源只声明一次：

| 键 | 来源 |
|---|---|
| S1 | `R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 3、5.2—5.4 节 |
| S2 | `R5_A2_LEGACY_AUTHORITY_REMOVAL.zh-CN.md` 当前候选记录 |
| S3 | `deploy/install.sh`、`deploy/install_transaction.py` 的上述精确字节 |
| S4 | `tests/artifact_agent/test_deploy_scripts.py` 的上述精确字节 |
| S5 | `operations/catalog.py`、Root/Task/Worker/Approval/Execution 生产路径及 clean-wheel 拥有者测试 |
| S6 | 本轮独立串行运行的 31 项部署、12 项安装态生命周期、6 项旧入口/边界测试和独立临时负例 |
| S7 | `ARCHITECTURE.zh-CN.md`、三项审查技能及 R5 冻结复杂度口径 |

`EvidenceAudit`：

| 检查 | 判定 | 证据 |
|---|---|---|
| `manifest_exact_binding` | 通过：删除同时要求 prepared manifest 中 name、绝对 path、kind=`path` 唯一精确匹配 | S2、S3、S6 |
| `ownership_receipt` | 通过：标记规范绑定 manager、稳定名称和排除标记后的完整树内容摘要 | S2、S3、S6 |
| `unsafe_tree_rejection` | 通过：标记本身、目标或树内 symlink 及特殊节点均拒绝并保留 | S3、S6 |
| `content_drift` | 通过：删除前重算摘要；超过首个 1 MiB 的尾部变更也被检出 | S3、S6 |
| `retire_and_rollback` | 通过：同一事务进入生产撤销，三表面消失，回滚恢复旧字节 | S3、S4、S6 |
| `explicit_tcad_marker` | 通过：显式选择 TCAD 后实际生产 Skill 安装函数写入可复核标记 | S3、S6 |
| `single_authority` | 通过：仍只有 `scidiscovery.plugins` 和 `operation_invoke` 两项权威 | S1、S2、S5、S6 |
| `lifecycle_regression` | 通过：Task/Worker/Approval/Execution、四启动入口和 clean-wheel 未退化 | S1、S5、S6 |
| `occam_and_constraints` | 通过：复用既有事务，无新注册表、状态机、所有权数据库或 Operation 分派 | S1—S3、S6、S7 |

## 3. 第三轮唯一阻塞的关闭情况

### 3.1 当前事务成员不再由布尔或 basename 代替

`remove_transaction_target()` 先以 `expected_state="prepared"` 读取规范 manifest，再要求同一条记录
同时满足：

- 稳定 `name` 精确相等；
- `_safe_target()` 得到的绝对 `path` 字符串精确相等；
- `kind` 精确为 `path`；
- 匹配项数量精确为一。

因此手工设置 `ROLLBACK_ARMED=1`、提供同 basename 的另一路径、改用另一个稳定名称，或拿 sqlite
条目冒充普通路径，都不能授权删除。本轮独立负例逐项调用生产事务函数验证，所有目标均被保留。
shell 层的布尔值现在只证明安装事务已进入可撤销阶段，真正的目标授权由规范 manifest 完成。

### 3.2 Skill 所有权与内容绑定已经闭合

`install_platform_skill()` 在新目录仍处于 staging 时调用生产
`mark-managed-directory`。规范标记包含且仅包含：

- `manager=scidiscovery-install`；
- 对应事务稳定目标名；
- schema 版本；
- 排除标记自身后的目录树内容摘要。

删除前会重新计算同一摘要并比较规范 JSON 原始字节。摘要覆盖相对路径、目录/普通文件类型以及每个
普通文件的 SHA-256；文件以 1 MiB 分块读取。标记必须是非 symlink 普通文件，目标必须是非
symlink 目录，树内任何 symlink 或 FIFO 等特殊节点都会失败关闭。

本轮除检查实现外，还独立运行了以下负例：标记改为指向完全相同规范字节的 symlink；目录包含
外部 symlink；目录包含 FIFO；2 MiB 以上文件只修改末尾字节。四类情形均被拒绝且原目录/外部目标
保持不变。已有拥有者测试同时覆盖缺标记、内容漂移和未绑定路径。

这一标记是本地安装器的防误删内容收据，不是对恶意本地用户的密码学签名；当前本地可信部署模型
没有把后者列为要求，本报告也不把它夸大为抗本地 root 篡改的安全证明。

### 3.3 正向撤销、回滚和显式安装均走生产路径

生产 `begin_install_transaction()` 无论新插件集合如何，都快照 Sentaurus Skill、TCAD transport 和
TCAD unit。`install_all()` 的顺序仍为构建/验证包、建立并武装事务、撤销旧表面、激活新安装。

拥有者测试把创建备份时的同一个 `TRANSACTION_ROOT` 交给生产
`retire_inactive_tcad_surfaces()`，确认三个目标被删除，再调用真实
`rollback_transaction()` 恢复旧内容。未绑定、无标记和内容漂移负例也调用同一个生产撤销函数，
不是字符串模拟。

本轮另以显式 `SCID_PLUGINS=tcad_artifact` 运行 `require_sources()` 和生产
`install_platform_skills()` 到隔离目录。实际生成的 `sentaurus-tcad-code` 标记是非 symlink 规范
文件，名称和重算目录摘要均精确匹配。由此，所有权证明既用于卸载，也确实由显式 TCAD 安装路径
产生。

## 4. 权威、生命周期与奥卡姆复核

生产源码的插件发现消费者仍只有 `operations/catalog.py` 对
`scidiscovery.plugins` 的一次读取。安装器提及三个旧 entry-point group 只是失败关闭探针，不构成
发现。旧角色/变换 loader 和四个旧 Root 创建工具没有生产定义；真实 Root 负例仍返回 unknown
tool。`TaskService.schedule()` 继续强制精确 `TaskOperationAuthority`、operation context 和提交
前置条件，私有 Transform/Effect 入口仍只能消费已经预检的 `BoundOperationCall`。

clean-wheel 测试继续从安装包真实执行 `open_runtime()`、`scid init codex`、control daemon 和
Worker daemon；core/full/full+InGaAs 的插件集合、Operation 增量和既有摘要不变。Agent、Transform、
Effect、handoff-only 输入、Worker 编译权限、UI 决定和 Execution 生命周期拥有者测试均通过。

本轮修复把删除前置条件放入已有 `install_transaction.py`，只增加两个窄命令和一个目录收据，没有
建立插件所有权数据库、第二注册表或新状态机，也没有按 Operation 名称选择领域行为。TCAD 配置
算法仍在插件自己的 84 行部署模块中；通用安装器只对用户显式选择的 TCAD 插件启用其配置、Skill、
transport 和 unit。

可复现行数为：`deploy/install.sh` 1021、`deploy/install_transaction.py` 330、TCAD 插件配置器 84、
operations 包 2060。通用安装脚本仍低于冻结的 1026 行门。事务帮助器因防误删增加的内容摘要和
规范校验是新安全边界的直接实现，没有把复杂度搬入新注册表或生命周期系统。

仓库仍没有逐项编号的“33/33”自动验证器，本报告没有伪称运行该脚本。按单一权威、不可变谱系、
Worker 最小上下文、人工审批、外部副作用、恢复、核心/领域分离和失败关闭等行为约束族核对，未见
本轮修复造成退化。Codex 原生工具限制仍是既有提示约束原型，本轮也没有把它重新描述成平台级
沙箱。

## 5. 独立运行证据

所有命令严格串行，且每次先设置：

```bash
ulimit -v 7340032
export MALLOC_ARENA_MAX=2 PYTHONDONTWRITEBYTECODE=1
```

结果：

```text
pytest -q tests/artifact_agent/test_deploy_scripts.py
# 31 passed in 7.39s

pytest -q \
  tests/operations/test_baseline_plugin_discovery.py \
  tests/operations/test_baseline_agent_lifecycle.py \
  tests/operations/test_baseline_transform_lifecycle.py \
  tests/operations/test_baseline_effect_lifecycle.py \
  tests/operations/test_baseline_role_contracts.py \
  tests/operations/test_baseline_worker_authority.py
# 12 passed in 32.90s

pytest -q \
  tests/operations/test_r4_approval_operation.py::test_generic_root_cannot_create_a_scientific_qualification \
  tests/operations/test_tcad_operation_plugin.py::test_explicit_legacy_tcad_adapter_cannot_bypass_compiled_operation \
  tests/operations/test_runtime_plugin_configuration.py::test_generic_daemons_have_no_tcad_runtime_switches_or_imports \
  tests/artifact_agent/test_deploy_scripts.py::test_installer_probes_compiled_operation_authority_without_fixed_counts \
  tests/operations/test_baseline_role_contracts.py::test_installed_runtime_has_no_legacy_role_contract_loader \
  tests/operations/test_catalog_installed_entrypoint.py::test_legacy_domain_entry_points_are_not_an_operation_discovery_fallback
# 6 passed in 25.76s

git diff --check
# 通过
```

此外，本轮用独立临时目录运行三组短程序，分别验证：

1. name/path/kind 精确绑定、标记 symlink 拒绝及 2 MiB 文件尾部漂移；
2. 目录内 symlink 和 FIFO 特殊节点拒绝；
3. 显式 TCAD 选择后生产 Skill 安装函数实际写入且重算通过的所有权标记。

这些检查均通过。实现记录中的全仓 `252 passed` 没有被当作继承批准；由于本轮精确变更位于部署
事务/Skill 标记边界，已独立复跑完整拥有者文件、安装态四入口和相邻承重生命周期，没有为仪式性
重复全仓科学测试。

## 6. 剩余风险

没有阻塞 R5-A2 的缺陷。现有提交态测试已经覆盖缺标记、未绑定和内容漂移；标记 symlink、特殊
节点及跨 1 MiB 边界漂移由本轮独立命令验证，但尚未作为三个独立测试名固化。后续若继续修改
部署事务，可把这三项并入同一拥有者负例，避免安全边界回归；这不改变当前精确字节已经失败关闭
的事实，也不要求在 R5-A2 内新增产品实体。

## 7. 最终结论

**通过。**

第三轮唯一阻塞已经按最小边界关闭：当前事务的 name、绝对 path、kind 与安装器内容收据共同授权
删除；缺标记、内容漂移、未绑定、symlink 和特殊节点均失败关闭；正向撤销、失败回滚和显式 TCAD
安装均使用真实生产函数。修复复用了既有事务，没有新增注册表、状态机或第二发现/行为权威，旧
Root/Task/Worker/Approval/Execution 边界与 clean-wheel 入口没有回归。

因此本轮**放行 R5-B**。本结论不代表 R5-B 已实现或通过，R5-B 仍需按上位计划单独实施和独立
审查。
