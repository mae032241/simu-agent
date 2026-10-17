# P5：失效 hypothesis A/B case 精确退役

日期：2026-10-17。基线 `ad89b41`。状态：**实现冻结，thin_test_review_1017 独立静态审查 PASS**；未运行测试、项目导入、脚本/CLI、安装、模型或远端作业，未提交。

## 根因与消费闭包

`run_root_invoke_ab.py` 仍固定 `science.hypothesis.revise.v1`。当前 source/plugins 无该 Operation 注册，且 `tests/operations/test_r4_science_tasks.py:150` 明确要求它不在当前 catalog；`operations.catalog.CompiledCatalog.operation` 只作 exact 字典查找，无别名兜底。A/B `main` 无条件遍历 CASES，`projection → _emit → emit_contract → catalog.operation` 因此在其余环境前提满足后拒绝 source arm；`--prepare-only` 仅禁止模型调用，不绕过这段准备。这个结构 pilot 的直接脚本入口会报错，不将其夸大为薄科研 CLI 的生产故障。

仓内 scripts/src/plugins/tests/deploy/pyproject/.github 中，该 ID 只有本 CASE 和上述反注册负控；没有其它当前注册。`run_root_invoke_ab` 没有其它仓内生产导入、测试调用、公共 console 或显式发布名单依赖。有效 figure case 仍消费通用 projection/scenario/grade/parse_jsonl 等 helper，因此不能因 hypothesis 失效删除这些 helper、共享 catalog/fixture 或整个脚本。仓外消费者未核验。

## 精确变更与静态检查

仅修改 `scripts/run_root_invoke_ab.py`：删除 hypothesis CASE 的两行。保留 figure CASE 的 Operation/输入、ORDER、所有 helper、旧安装 arm/源码 arm、模型参数与命令行为。本文件为第二份、也是唯一新增的实施证据。未改 root 持有的四份当前文档、旧历史报告或其它作者代码。

标准库 AST 可解析；仅静态 literal 读取 CASES，确认剩余 figure 的完整 tuple 与原值一致；逐行空白检查通过。未通过导入/执行脚本或构造假成功回包验证，不需要为两行失效配置删除启动付费 A/B、安装或恢复完整旧测试。

前一 L4 退役 `513a7b0` 当时保留 figure/hypothesis 的历史实施账不改写；本文补充当前精确失效事实。此节点不证明 figure A/B 的旧 `/opt/scidiscovery-m7/site` 环境可用，也不授真实模型运行、全部 P5 退役或全仓回归通过。

冻结清单：上述脚本 + 本文。独审确认 exact catalog 消费链、figure 原值及 helper 保留；由 root 精确提交，无本 worker 测试或 commit。
