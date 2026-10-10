# 自动采集来源限制：源码节点验收

日期：2026-10-10。基准：dev `4788f27`。状态：定向回归及独立语义审查通过；不构成安装、真实模型或发布资格。

## 范围与修复

本节点收口既有未提交的自动采集改动，并修复复核发现的旧回执恢复缺口。

- 自动科学附件保守继承全部精确任务输入的限制；实际采用的科学来源仍单独记录在 `derived_from`，不把所有输入假称为已采用证据。
- `task_scope` 与 `author_declared` 区分任务关联和作者声明；`known` 只表示精确绑定，不表示科学结论经过验证。
- 缺少控制层来源范围确认的旧自动回执不能直接支持新主张；检查先于缓存来源边。
- 自动附件恢复（包括旧回执）要求保留原任务的完整输入范围，不能只保留作者声明的干净来源后重新封存。
- 第三方插件的自定义采集目录同样经过封存及下游主张准入检查。

显式 `worker_publish_files` 保持现有 `source_aliases` 合同；作者遗漏来源的风险留在 F2b 审查范围。本节点不宣称修复全部发布路径。

## 测试与独立审查

使用共享串行锁下的 `scripts/run_tests.py --lane source`：

1. `source-restrictions/checks-01`：29 passed、3 failed，监督器耗时 47.319 秒。两个新增第三方夹具使用了不支持的输入用途；一个旧测试仍期待仅声明干净来源的自动文件不受完整任务范围限制。
2. 修正上述夹具/合同期望后，`checks-02` 仅重放三处：3 passed，5.08 秒。生产准入规则未放松，来源图与限制范围分离的断言保留并补强。
3. 其余 29 个通过节点对应实现未变。这里记录的是 32 个节点各自的通过证据，不是最终候选一次全套测试通过。
4. `/root/hwa_plan_review` 独立审查最终文件摘要及生产接线，结论 PASS；实施者为 `/root/f0_test_debt`。检查包括自动封存、不可变限制标签、缓存前旧回执检查、恢复权限和第三方主张准入。
5. `git diff --check` 通过。未运行全量、wheel 安装、原生 Worker、真实模型或 TCAD；后续最终候选仍需对应验收。

测试范围为 `test_capture_scope_restrictions.py`，以及 `test_artifact_capture.py` 的恢复、第三方目录和声明来源分离用例，及 `test_scientific_use_provenance.py` 的显式发布来源传播用例。

## 证据定位

原始证据保存在外层工作区 `.trial/hwa_revision_20261010/source-restrictions/`：
`REPORT.md`、`final-candidate.json`、`PATCH.final.diff`、两个 checks 目录。
原始日志及产物未随本节点加入 Git。`CONTRIBUTING.md` 的既有分支职责文字独立处理，不属于本修复。
