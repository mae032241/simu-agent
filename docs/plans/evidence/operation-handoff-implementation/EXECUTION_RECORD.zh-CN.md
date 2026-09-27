# Operation 上下文与缺口交接实施记录

日期：2026-09-09。状态：A0/A/B 与复审要求的领域失败恢复接线已实施，独立静态审查 PASS，定向源码检查及一次隔离安装验证完成。C0 因缺可信原生初始化正样本未通过，C 未实施；未部署，未运行真实科研闭环。不能称整份修复计划或总体研究已经完成。

## 范围与基线

实施基线为 R4（将 R3 独立复审 F1 的恢复接线写回计划），保留既有全部 dirty 改动。开始时保存 `/tmp/scid-handoff-baseline/source.tar` 与清单；本目录另持久保存本轮修改文件的原始字节 `baseline-changed-files.tar.gz`、`changed-files.json` 前后摘要以及 `implementation.patch`，恢复仅针对本轮增量，不回退整个工作树。

本轮改变 19 个源码/角色/测试文件，501 行增加、71 行删除（其中包含新回归测试）。没有新增 Operation、数据库状态、执行审批机制或评分阶段。

- 共享职责参考进入现有编译 prompt；revise/TCAD author/reviewer 复用一个受限 current_progress，相关分析和 TCAD 的科学审查正文从 handoff_only 改为 on_demand。历史反馈不进入参数资格 cohort，不覆盖正式计划。
- 设计与审查明确检查任务交付；允许有依据地后移、缩小、改方法或指出不可行，不要求设计者完成所有缺失工作。
- ImplementationGap 与完整工程严格互斥；无需源码或 debug 即可封存并独立审查。能力不匹配允许 missing_inputs 为空；gap 不能冒充 prior_project、完整工程或可执行 package。
- 失败前接通已声明 snapshot hook，沿用 candidate/recovery digest。当前领域草稿先于旧 result；保留 malformed gap，删除 gap 后可恢复新源码。不改变已接受候选身份、重试输入检查或原 Run 状态机。
- 独立审查指出 deck 根符号链接会导致快照越界，已补 `_deck_root` 并在快照与 gap 提交前拒绝该路径；真实提交/失败隔离负例通过。

独立实现审查：[报告](../../reviews/OPERATION_HANDOFF_IMPLEMENTATION_REVIEW_R1.zh-CN.md)。审查者未运行测试，测试证据由本记录负责。

## 验证证据

所有命令串行，使用 `/home/da/miniconda3/bin/python`，`ulimit -v 3145728`（3 GiB 虚拟内存）与有限超时。未运行全量、压力测试或多环境安装矩阵。

| 检查 | 结果与限制 |
| --- | --- |
| source-validation.log：agent contract、TCAD、Run invariants、general transforms 四个受影响文件 | 237 passed、1 failed，36.47 秒，峰值 RSS 125156 KiB。失败是旧符号链接诊断文字被合并，已恢复原诊断，后续 confinement 检查通过；没有降低原断言 |
| analysis-validation.log：两种结果分析及符号链接发布门禁 | 59 passed、1 failed、1 stress deselected，9.59 秒，峰值 RSS 106336 KiB。失败是预期 Operation version 仍为2；按本轮曝光合同升为3更新预期，后续 fix 检查通过 |
| fix-validation.log | 6 passed，2.72 秒，峰值 RSS 101212 KiB；覆盖 gap/真实失败恢复、旧重试和分析版本准入的修正 |
| confinement-validation.log | 2 passed；真实 deck 根 symlink 的 submit/record_failure 拒绝及既有发布门禁 |
| gap-negative-validation.log | 1 passed；gap+pass handoff 拒绝后，同 Run 改为真实 blocked 可封存并独立审查 |
| 完整 cohort 的真实 gap→独立 review→design | 新用例包含在源码检查通过项中；使用实际产出的 Artifact 名并读取新 Worker 输入。审批 fixture 只隔离既有资格流程，不证明真实批准或科学判断 |
| installed-validation.log | 单一 full 环境、三个 wheel、一次隔离安装通过。校验源码隔离、共享 prompt、progress/exposure/context_sources、gap schema、版本及 Worker 配置；7.66 秒，峰值 RSS 75012 KiB。不证明真实 solver |
| git diff --check | 通过；未改写其他既有增量 |

上述命令存在重叠，不相加成独立测试总数。保留失败日志及定向修复证据，不覆盖为全绿历史。安装验证使用本目录 `installed_probe.py`，不调用会创建14个环境的默认 installed_environments fixture。

技能提及的 `scripts/validate_architecture_constraints.py` 在当前仓库不存在，尝试记录在 architecture-validation.log，未把它记为通过。未为运行过期脚本扩充测试框架，也未运行全量科学 benchmark；当前证据限定在所列受影响路径。

## C0 与后续边界

[C0 核定记录](C0_INITIALIZATION_EVIDENCE_DECISION.zh-CN.md)明确：当前可读工程材料没有可信原生正样本，debug 输出路径及 TDR provider 也不能直接提供所需证明。没有实施 C 的新初始化资格语义，也没有以合成夹具或历史 qualified=true 替代证据。

下一步先取得合法来源的 SProcess 初始化原生正样本及源码/入口/运行绑定，再完成 C0 的证据选择与最小收集路径复审；C 通过后才可验证本案例物理执行就绪。A0/A/B 的源码与安装检查不授权自动部署或真实执行；新部署需匹配更新后的 Operation digest，旧 Run 不跨合同提交，旧审查/执行批准不能沿用到修订成果。
