# U4 cov 单场：H→W 工程阻断

结论：**工程验收失败，科学效果未验证**。用户在U0–U3无模型验收后授权开始真实测试；本场独立实例、600万token／3600启用秒、gpt-6.1-sol high/default，无对照或重复场。启动器最小修复提交`935e5ae`，核心wheel与已审U3一致。

## 实际结果

- 运行310.602秒，H001正常封存，科学意图解析成功并派发W002。
- H用量：215,639 token；缓存输入175,616；未缓存输入加输出40,023。
- W的host启动器在调用原生Codex前失败，未产生线程或原生事件。框架保守计量仍记录unknown_steps=[2]；不伪造零用量回执或清除原接受记录。
- 正式实验0，交付0，无可评分候选。W实际分片、A介入、最终交付均未观测，不能记为通过。
- 原冻结输入未改；没有预算扩额、自动重跑、隐藏评分或模型注入。进程已终止。

## 根因

`cov_lineage.configure`调用`lineage.build(root, 2)`读取已有H的候选/机制谱系。该默认入口仍用已退役的`exploration_order_version == 1`决定是否调用统一`search.fold`。CURRENT14不再写该旧标记，于是进入旧手写状态构造，缺少`order`。但search_policy已启用，随后仍回放H计划；第一次追加机制时抛出`KeyError: order`。

这是U3清理旧协议时遗漏的核心状态构造分支，与模型输出、隐藏分或cov算法无关。`lineage.project`预传统一state的路径正常，默认build路径不同，因此先前局部回归未暴露。

## 验收覆盖缺口

科学路由测试启用search并封存H，但没有调用cov配置入口；真实namespace测试直接从W开始且关闭search。因此“封存的H机制计划→真实W启动”没有被组合验证。

最小后续修复应复用统一`search.fold`，删除lineage重复初始化和旧标记分支，不能只补一个order字段或重开旧协议标记。回归需通过封存H、接受W、cov.configure及实际启动器，同时保留无search场景。用户已要求先测试定位，不急架构改造；本次只记录，没有继续修改生产或重启该实例。

## 本地原始证据

目录：`.trial/rootless-u4-cov-20261013/`（仓库外层工作区）。

- `acceptance-summary.json`、`failure-evidence.json`：有界结果与原件SHA。
- `final-result.json`：原控制终态与预算；`frozen-manifest.json`：候选/输入冻结。
- `instance/native-evidence/001/`：H原科学输出、封存、用量。
- `instance/native-evidence/002/native.stderr`：configure→lineage→search完整异常；同目录保留已接受意图和终态。
- 启动前host准备断言曾期待旧portfolio字典形状，实际控制正确加入version=2；修复仅host断言并核同一未启动实例，保留`prepare-postcheck-repair.json`，未改研究预算或settings。

独立诊断见[U4失败复核](U4_COV_FAILURE_REVIEW_20261013.md)。
