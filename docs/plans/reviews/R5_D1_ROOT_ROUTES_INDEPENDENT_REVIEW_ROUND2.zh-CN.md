# R5-D1 Root 路由职责拆分第二轮独立审查

日期：2026-08-29  
审查范围：只复核首轮唯一阻断 F1 的计量修复，并确认 D1 已通过部分没有发生字节变化  
结论：**通过**  
门禁决定：**只放行 D2，不提前放行 D3、R5-D 总审或 R5-E**

## 1. EvidenceAudit

### 1.1 来源声明

| 来源键 | 来源与完整性 |
| --- | --- |
| S1 | 权威计划 `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md`，SHA-256 `ebba87f2db43622a82bdf8e8c66f89cb55e87febe870bee21fd812ac5b64ef1a`；本轮使用其中 D1 与 R5-D 复杂度门。 |
| S2 | 首轮报告 `docs/plans/reviews/R5_D1_ROOT_ROUTES_INDEPENDENT_REVIEW.zh-CN.md`，SHA-256 `2cf3e6c0a53f230a5eb535d389341898a100c904f8fa5a7f87ad35a2be996ef9`；其唯一阻断为 F1。 |
| S3 | 当前聚合脚本 `scripts/r5_current_metrics.py`，SHA-256 `c924afd34cdacea7f11f1cf21f96f1721b3707dec997a7561ebaf75683ac128f`；本轮生成 JSON 的 SHA-256 为 `c9045b2256c3401ff58cc7d6831ad436163efe54a3dd7dbc729f9d482e673be7`。 |
| S4 | 结构门 `tests/operations/test_r5_root_route_split.py`，SHA-256 `e62cd793e25d08d05d17b4277bffaa4be4c01514a8197cbc9a836f0c7819c05f`。 |
| S5 | 冻结生成器 `scripts/r5_baseline_metrics.py`，SHA-256 `718eac8e17569cdbb7adeefe7e0e8cc12efab20cae96b614e4fdc77db40e51f5`；冻结快照 `tests/fixtures/r5_structure_inventory.json`，SHA-256 `1b397e2dfea1bc579b2597caf5d3a37f5ef44e40d66b92f509b349b51b77983a`。两者与首轮观察相同。 |
| S6 | 七个 Root 生产文件；SHA-256 依次为 `48748f10...`、`dcf89456...`、`5f698ea9...`、`5439753f...`、`0b3d1ce7...`、`2aff9996...`、`aad91e7f...`，均与首轮相同。 |
| S7 | 实施记录 `docs/plans/R5_D_RESPONSIBILITY_SPLIT_IMPLEMENTATION.zh-CN.md`，SHA-256 `2189c2183825ed6c6662086d312c63028051b36241dbeaff269a9fd2cf2a172c8`。 |
| S8 | 本轮独立执行记录：首轮相同范围 15 项测试、当前计量重算、七模块 `py_compile` 和 `git diff --check`。 |

### 1.2 检查记录

| 检查键 | 判定 | 证据 | 审计结果 |
| --- | --- | --- | --- |
| `f1_current_aggregation` | pass | S1, S3, S4, S8 | 六个 R0 owner 的当前值统一取自各自 `responsibilities[owner].total_lines`；Root 为 3035，六职责总计为 9635，且总计等于六项之和。 |
| `successor_exactness` | pass | S3, S4, S8 | Root successor 恰为入口、共享模块及五个路由共七项，无集合内重复；六个 R0 owner 当前共 12 个全局唯一 successor，逐文件重算仍为 9635，没有重复或漏计。 |
| `future_reuse` | pass | S3, S4 | 聚合算法遍历输出中的全部 R0 owner，并从同一责任 successor 投影取值；3035/9635 仅为测试预期，不在算法中硬编码。D2—D5 只需扩展相应 owner 的 successor 声明和精确测试，不需要另造 headline 算法。 |
| `frozen_integrity` | pass | S2, S5 | 冻结生成器和冻结快照哈希与首轮完全相同；当前脚本只在自己的进程内叠加 successor，并未改写冻结证据。 |
| `unchanged_route_scope` | pass | S2, S6, S8 | 首轮已通过的七个生产文件字节未变；15 项真实 Root、生命周期、审批与 clean-wheel 范围再次通过，没有因计量修复重开或改变运行边界。 |
| `record_honesty` | pass | S3, S7 | 实施记录明确写出 Root 3035/2885、R0 六职责 9635/13657、全生产 60299/62533，并保留首轮打回与修复历史。 |
| `occam_and_scope` | pass | S1—S4 | 修复只新增一个当前态聚合函数和对应结构断言，没有改生产代码、增加注册表、状态机或运行时权威；复杂度没有从被计量文件搬移。 |

## 2. F1 修复复核

`collect_current()` 先让冻结生成器按当前 successor 声明生成逐职责明细，再对 `r0_core.paths` 中的六个
owner 统一取 `responsibilities[owner].total_lines`。因此当前第一口径不再直接读取拆分后只剩 535 行的
Root 入口，而是读取入口及六个后继文件合计 3035 行。独立重算得到：

```text
Root 当前职责：3035
R0 六职责当前总计：9635
R0 基线总计：13657
聚合标记：responsibility_successors
operations 包：7 文件 / 2056 行
全生产 Python：134 文件 / 60299 行
```

当前六个 owner 的 successor 集合全局无交叠；所有存在文件的报告行数均与 UTF-8 `splitlines()`
重算一致，不存在通过同一路径重复计数或遗漏 Root 路由获得虚假减重。脚本没有把 D1 的两个结果数字
写入算法，后续单元可以复用同一 `collect_current()`；后续每次拆分仍必须把新文件加入相应 owner 的
successor 声明，并由该单元测试冻结精确集合，这属于既定防搬移责任，不是新的注册面。

## 3. 独立运行记录

所有命令均在 `ulimit -v 7340032`、`MALLOC_ARENA_MAX=2`、
`PYTHONDONTWRITEBYTECODE=1` 下严格串行执行。

```text
pytest -q \
  tests/operations/test_r5_root_route_split.py \
  tests/operations/test_operation_invoke_installed.py \
  tests/operations/test_baseline_agent_lifecycle.py \
  tests/operations/test_baseline_transform_lifecycle.py \
  tests/operations/test_baseline_effect_lifecycle.py \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_baseline_plugin_discovery.py::test_core_clean_wheel_runs_runtime_cli_and_both_daemon_entries
# 15 passed in 31.22s

PYTHONPATH=scripts python <六 owner successor 唯一性与逐文件行数重算>
# r0_owners=6, unique_successors=12, total=9635

PYTHONPATH=src python -m py_compile <七个 Root 模块>
# 通过

git diff --check
# 通过
```

修复只涉及计量脚本、结构测试和实施记录，且首轮 15 项范围已经覆盖真实 Root/生命周期与安装态路径，
因此本轮没有无意义重复全仓 274 项，也没有运行浏览器点击或真实 solver。

## 4. 最终结论

首轮 F1 已按精确最小边界关闭：当前第一复杂度口径真实聚合全部 successor，Root=3035、总计=9635；
冻结可信度未变，既有路由运行边界未退化，修复没有引入第二计量权威或新的控制复杂度。

**结论：通过。只放行 D2。**

