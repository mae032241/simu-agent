# R5-H H3-C 零消费者别名与历史实例合成删除独立实现审查

日期：2026-08-31  
审查基线：`404aeb14c6ebc4b08bac599db91eaee54c103f48` 上的当前累计工作树  
权威计划：`docs/plans/R5_H3_LEGACY_SURFACE_DELETION.zh-CN.md`  
权威计划 SHA-256：`172da2ee56c5a2d2cd51859f33bb2bbd304340f4375127c322c74c2c2c00f167`  
前置门：H3-A、H3-B 已独立通过；H3-B 报告哈希复算为
`c6726136b932e7fb62cd6ef9e3d5dc39c469dce8734efe0741816b65c4c3b074`  
审查范围：只审 H3-C；不把本结论解释为 H3-D 或整个 H3 已完成  
结论：**通过，只放行 H3-D**

## 1. 最终判断与阻断项

**阻断项：无。**

候选准确删除了两个历史合成面：`builtin_plugin.PLUGIN = CORE_PLUGIN` 及其说明共4行，和
`SchedulerBindingService._initialize` 中扫描孤立 binding、写入 closed `legacy.*` instance 的30行。
生产 Python 相对已通过的 H3-B 冻结值净删34行，没有增加生产文件、数据库结构、状态、注册表、路由、
迁移器、入口校验或兼容层。

发布 entry point 与生产消费者继续显式使用 `CORE_PLUGIN`；孤立旧 binding 和 session 原始行可保留，
但 `list_instances`、`session_instance`、session-binding candidates 和 `get_instance` 都不能把它们解释为
ResearchInstance。底层按旧 instance id 的精确 `resolve` 仍可读原始 binding，符合计划明确不要求任意
底层 resolve 拒绝的边界。

当前格式 installed-wheel 正例通过真实文件生命周期完成 Agent task，建立 Artifact、Task、Approval、
Execution 四类绑定，关闭 instance，并经 `open_runtime` 重开同一 state root 后读取 closed instance、
completed task 和四类绑定。未发现 H3-D 提前实施、针对测试增加生产分支或通用 AI 科学家轻控制目标
偏移。

## 2. `PLUGIN` 别名确为零消费者，真实入口保持 `CORE_PLUGIN`

- `pyproject.toml:27` 的基础发布入口仍是
  `builtin = "scidiscovery.builtin_plugin:CORE_PLUGIN"`；
- `src/scidiscovery/builtin_plugin.py:587-597` 只构造 `CORE_PLUGIN`，模块不再定义或重新导出
  `PLUGIN`；包根也保持空 `__all__`，没有从别处补回兼容导出；
- 对 `src`、`plugins`、`deploy`、`scripts` 和所有生产 `pyproject.toml` 的精确扫描仅命中上述
  `CORE_PLUGIN` entry point，`scidiscovery.builtin_plugin:PLUGIN`、
  `from scidiscovery.builtin_plugin import PLUGIN` 和 `PLUGIN = CORE_PLUGIN` 均为零命中；
- `tests/operations/test_baseline_plugin_discovery.py:72-111` 在无 source `PYTHONPATH`、无 user site 的
  干净 core wheel 中断言模块没有 `PLUGIN`；同文件下一项实际调用 `compile_installed_catalog()`，因此若
  wheel 元数据仍指向旧别名会在生产 loader 路径直接失败；
- 本审查运行的 installed probe 重新从 release source 构建 wheel 后通过，不依赖 checkout 中的
  import 夹具。

测试中把 `ARCHITECTURE_TEST_PLUGIN` 局部改名为 `PLUGIN` 的 import 只是架构测试夹具变量，不是被删的
模块级兼容别名。其他领域插件各自公开 `PLUGIN` 也不属于 H3-C 范围。

## 3. 孤立旧 binding 保留但从四个 current 入口不可达

删除块原来在数据库初始化末尾全表扫描 `scheduler_bindings`，为没有 `scheduler_instances` 行的每个
namespace 合成 closed `legacy.*` instance。当前 `_initialize` 在建立当前表、补齐当前 binding 字段、
建立现有索引后直接结束，不再读取孤立 binding，也没有改成另一种迁移或清理。

四个入口的实际门如下：

1. `list_instances` 只从 `scheduler_instances` 读取；
2. `session_instance` 将 `scheduler_sessions` inner join 到 active `scheduler_instances`；
3. 新 session-binding request 只从 active `scheduler_instances` 冻结候选，候选读取也 inner join
   `scheduler_instances`；
4. `get_instance` 只按 `scheduler_instances.instance_id` 查询，不存在即抛
   `SchedulerInstanceNotFound("unknown research instance")`。

仓库聚焦回归 `test_orphan_binding_remains_raw_but_cannot_become_current` 构造一个当前 instance、一条孤立
Artifact binding 和一条指向孤立 id 的旧 session，重开 service 后逐一冻结上述四个结果，并确认原始
binding 行仍在。

为避免把直接构造 service 夸称为 runtime 重启，本审查另运行了不改文件的独立探针：先用
`open_runtime` 创建当前 state root，再写入孤立 binding/session，随后通过 `open_runtime` 重开同一
state root。结果为：

```text
open_runtime_orphan_probe=pass current_entries=4 raw_rows=2 resolve_legacy=readable
```

探针同时确认原始 binding 与 session 两行均未删除，且
`resolve(instance="old_namespace", namespace="artifact", name="old") == "art_old"`。这证明通过来自
current 入口的既有 ResearchInstance join/lookup，而不是新增全局入口校验或破坏性迁移。

## 4. 当前格式四类绑定、completed task 与 closed instance 可恢复

`tests/operations/test_operation_invoke_installed.py:52-442` 是从实际构建并安装的 architecture fixture
wheel 运行的纵向正例，不是只写 SQLite 行：

- 注册输入 Artifact 并建立 `artifact/fixture_input` binding；
- 通过 `operation_invoke` 创建 `task/bounded_agent`，经真实 Worker materialize、file create、validate
  file、finalize file 达到 `completed`；
- 通过 effect Operation 建立 `execution/bounded_effect`，再由审批创建入口建立
  `approval/bounded_effect.approval`；
- 关闭同一 ResearchInstance，使用相同 task/approval secret 和 state root 再次调用
  `open_runtime`；
- 重开后断言 instance 为 `closed`、task 为 `completed`，并逐项解析 Artifact、Task、Approval、
  Execution 四个原 binding 到原 object id。

该用例精确覆盖计划要求的持久化和重启边界。它直接调用 binding service 关闭 instance，而不是扩大到
审批/执行未完成时 Root `instance_close` 的策略测试；H3-C 要验证的是已有终态和 binding 的持久化，
不是修改关闭准入，因此此取舍不构成缺口。

## 5. 纯减法、无复杂度转移、未提前实施 H3-D

- `git diff --numstat HEAD -- scheduler_bindings.py` 为 `0 30`；该文件相对基线只有预期30行删除；
- H3-B 独立报告冻结生产 Python 为150文件/59,162行，当前指标为150文件/59,128行，差值精确为
  34行；其中 scheduler 30行和 builtin 尾部别名/说明4行完全闭合；
- 当前仍是一个 `scidiscovery.plugins` 入口组和一个启动时 `CompiledCatalog`；operations package
  保持7文件/2,064行，目录/OperationSpec/Worker/审批/Execution 路径没有因 H3-C 改写；
- 当前候选没有新增生产文件、表、列、状态值、Registry、facade、router、adapter、migration
  version、启动扫描或 instance 入口 validator；
- 未删除当前 Schema 建表、`logical_name`/`revision`/`request_fingerprint` 补齐与索引，也未触碰其他
  `legacy` 业务枚举、外部 TCAD Effect、审批语义或 Agent 派发；
- 根发布 manifest 的最终代际更新、全部安装组合、当前文档总收口和 H3 总审查仍明确留在 H3-D，当前
  没有生成 H3 总通过报告。

生产修改只有删除，且测试通过 installed loader、真实文件封存和 runtime 重开验证外部行为；没有发现
为了满足断言新增特例、检测 fixture 名称或保留另一套兼容基座。

## 6. 33项约束与通用 AI 科学家轻控制目标

33项注册表结构门通过；本阶段的语义影响集中且为收紧：

- `AUTH-001`、`MIG-001`：孤立旧 binding 不再自动升级为 ResearchInstance/current 事实；
- `PLG-001`：基础插件仍通过普通 entry point 与统一目录发现，没有增加核心插件名分支；
- `IMM-001/002`、`ROLE-001/002`：当前 Artifact、Task、Approval、Execution 绑定、文件封存和合同身份
  未改，completed task 重开正例通过；
- `CQRS-001/002`：list/get/session 查询保持只读，删除的正是启动期写入伪实例的历史合成；
- `RES-002`、`MIG-002`：同一 state root 的当前终态恢复和独立旧库探针通过，最终发布/回滚矩阵仍由
  H3-D 承担。

其余科学、证据、不确定性、拓扑、人工审批、副作用、UI 和安全约束没有被这两个删除点触及。实现没有
增加知识图、规划器、固定 DAG、科学状态或领域规则；通用核心仍只持有 Artifact/Task/Approval/
Execution、OperationSpec 编译和轻量门禁。因此 `多角色 Agent + OperationSpec + 轻量门禁 + 领域插件`
的目标未偏离。

## 7. 独立检查与可信度边界

所有 pytest 和独立探针均串行运行，先设置 `ulimit -Sv 7340032`（7 GiB 虚拟内存限制）。未重复候选
已经记录的312项完整 Operation 回归。

```text
pytest -q \
  tests/operations/test_baseline_plugin_discovery.py::test_orphan_binding_remains_raw_but_cannot_become_current \
  tests/operations/test_baseline_plugin_discovery.py::test_core_only_install_has_only_the_unported_domain_bridge \
  tests/operations/test_operation_invoke_installed.py::test_installed_unified_operation_entry_creates_all_three_lifecycles \
  tests/operations/test_r5_catalog_stages.py::test_catalog_stages_add_no_second_registry_or_complexity_escape \
  tests/operations/test_architecture_constraint_matrix.py
结果：5 passed in 38.68s；/usr/bin/time 峰值 RSS 74,248 KiB

PYTHONPATH=src python <独立 open_runtime 孤立旧库探针>
结果：open_runtime_orphan_probe=pass current_entries=4 raw_rows=2 resolve_legacy=readable

python scripts/r5_current_metrics.py
结果：production_python={files:150, lines:59128}
      operations_package={files:7, lines:2064}
      worker_lines=810；task_lines=6031；generic_core_domain_tokens=0

git diff --numstat HEAD -- src/scidiscovery/artifact_agent/service/scheduler_bindings.py
结果：0 30

生产 entry point/旧别名/旧合成文案精确扫描
结果：CORE_PLUGIN 只命中 pyproject.toml:27；旧别名和三组旧合成标识零命中

git diff --check HEAD
结果：通过
```

计划第11节记录的 `tests/operations` 312项和部署/平台/约束38项未在本审查重复执行；本报告不把该
实施记录改称独立复跑证据。独立5项选择了会直接因两个删除点、当前终态恢复或复杂度逃逸而失败的最小
集合，并实际重建 installed wheel，足以支持本阶段判断。H3-D 仍须执行计划中的完整安装组合、发布
manifest、部署/平台和总回归门。

## 8. 非阻断债务与剩余风险

1. 整个 R1～R5 仍位于同一个未提交累计工作树，Git 不能原生给出 H3-B→H3-C 的独立 patch。
   本审查用已核验哈希的 H3-B 报告、当前精确符号、scheduler 的基线 diff 和59,162→59,128指标闭合
   34行删除；后续阶段宜保留不可变阶段补丁或文件清单，降低审查重建成本。
2. 仓库内孤立旧库回归直接重开 `SchedulerBindingService`，没有把 `open_runtime` 包装层写进该测试，
   也未显式断言旧 session 行和底层 resolve。二者均由本次独立 runtime 探针验证；由于
   `open_runtime` 对该行为只是构造同一个 service，且生产没有新增分支，不阻断 H3-C。H3-D 可决定
   是否把这三项断言固化进现有单一用例。
3. 33项注册表中 `AUTH-003` 的证据文字仍称 H3-B“等待独立审查”，与已通过状态不同步。该文字不
   影响 H3-C 行为或约束 assessment，且当前阶段明确禁止提前做 H3-D 文档总收口；应在 H3-D 更新
   当前文档时一并校正。
4. 本审查没有重复312项全回归、真实外部 solver、浏览器或全部插件安装矩阵。前两者不受这两处删除
   影响；完整安装、部署、发布 manifest 和总审查本来就是 H3-D 的完成门，不能由本报告提前宣称。

## 9. 审查对象 SHA-256

```text
172da2ee56c5a2d2cd51859f33bb2bbd304340f4375127c322c74c2c2c00f167  docs/plans/R5_H3_LEGACY_SURFACE_DELETION.zh-CN.md
c2ac151646a71fcb315465553b9cf087ff8597563d8e566b61dbb48cda681f72  src/scidiscovery/builtin_plugin.py
08e6396f85fd010bce526fa79312d880e473924dba3d419d50a82c5e2024162a  src/scidiscovery/artifact_agent/service/scheduler_bindings.py
aae1f64c882f8adfe27e081be1df336109551407b2e15b4c6fef7e2dcc97c50f  tests/operations/test_baseline_plugin_discovery.py
e92ed0c455b3d43239e8e6a972c425c64f7f8403d58183f77222212b8dd54a94  tests/operations/test_operation_invoke_installed.py
47c6fd47e64cf422a6fed42f3d15cff4c620692f4c2e1096696ab89613593dc0  tests/operations/test_r5_catalog_stages.py
```

本报告自身最终 SHA-256 由交付消息给出；不写入正文以避免自引用改变摘要。

## 10. 结论

H3-C 已按权威计划只删除零消费者 builtin 别名和孤立 binding→`legacy.*` instance 自动合成。真实
CORE_PLUGIN entry point、当前格式四类绑定、completed task 和 closed instance 重启恢复均保持；旧
binding/session 原始行可保留但不能进入四个 current 入口；没有新增控制状态、兼容层、迁移器、全局
校验或领域特例。**结论：通过，只放行 H3-D。**
