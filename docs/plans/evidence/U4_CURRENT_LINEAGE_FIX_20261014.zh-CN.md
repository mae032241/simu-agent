# U4：清除谱系入口的旧协议残留

日期：2026-10-14。分支：dev。真实场结果另记，本文只记录修复与无模型验收。

## 根因与修订

1. `lineage.build` 以已退役的 `exploration_order_version` 判断是否使用 `search.fold`，当前协议没有该标记，落入缺少 `order` 的手工状态，真实 H→W 启动报 KeyError。删除兼容分支及第二份状态初始化，统一由 `search.fold` 生成完整状态；已有投影直接复用，不重复消费。
2. 完整链路回归进一步发现 `lineage.contexts` 仍手写旧五字段执行范围，会拒绝当前含 `handoff_protocol` 的范围，导致 W 封存失败。统一使用 `protocol.stage_scope` 精确比较；同一科学节点各原生片段共用稳定 owner，原生 attempt 仍由独立执行记录约束。
3. 旧协议执行兼容测试改为存档不可执行且不修改原件的负例。未加入旧格式写入、恢复或自动迁移路径。

## 验收

证据根：外层 `.trial/`，未调用模型。

- source-01：23 通过、12 失败。4 个真实 scope 不匹配和 8 个旧协议兼容期望，均已处理。
- source-02：27 通过、8 失败。剩余为存档测试修改 marker 后未更新夹具身份摘要，测试先触发防篡改；只修夹具，未放宽生产校验。该次存在测试文件冻结交叉，最终以 source-03 为准。
- `u4-lineage-source-03-20261014/batch-001/pytest.log`：37 通过，12.61 秒。
- `macro-role-installed-20261012/artifacts-u4-lineage-02-20261014/result/result.json`：新 wheel 安装及 CLI 基础链路通过。
- 同目录 `u4-lineage.log`：49 通过，19.73 秒，无跳过。覆盖安装包、真实 launcher.main/bwrap、已封存 H、注册实验调用、W 两个新上下文、同一调用只查询不重提、observer 封存及 A 消费。
- 同目录 `u4-original-replay.json`：旧失败现场只读回放通过，4 个机制恢复投影，58 个文件未变化。
- 独立审查见 [审查记录](U4_CURRENT_LINEAGE_FIX_REVIEW_20261014.md)。

## 真实复测范围

沿用单场 cov 框架授权，不跑对照或隐藏评分。旧失败场保留；新场使用当前协议、新安装包。原总额 600 万 token / 3600 秒，扣除已观测 215639 token / 310.602 秒，剩余 5784361 token / 3289.398 启用秒。原 W 无模型轨迹但用量保留 unknown，不改写成已知零。

模型 gpt-6.1-sol high，默认服务层。分片使用已验证 new_context；真实 same_session 仍未获启动器支持，output_repair 关闭。通过这些无模型检查不代表真实 U4 或科研效果通过。
