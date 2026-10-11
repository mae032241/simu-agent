# N2a：旧实现精确交接验收

日期：2026-10-11。基线：0437278。独立审查通过；范围仅为contracts.py、test_history_handoff.py与设计文档。N2b历史/候选概览尚未实现。

## 交付

H/A通过科学结论中的显式 `#reuse-implementation` 链接选择已绑定旧实现；控制层核对封存原件并向下一节点绑定确切文件。普通引用不转交，每一跳都需明确选择；不继承祖先附件包。哈希和收据留在宿主，角色不承担文件封装。

独审发现并修复最终去重材料集合的总容量检查缺口，以及新增视图导致旧冻结任务无法恢复的问题。新任务冻结交接协议版本，旧任务保留旧视图。

## 证据

- 共享串行source gate：history_handoff、controller、native_cli，71 passed in6.94s。归档见 [测试结果](rootless-n2a-20261011/source-result.json) 和 [日志](rootless-n2a-20261011/pytest.log)。
- 真正的bwrap与Codex 0.162.1 sandbox：10项无模型检查通过，确切旧文件只读可见，未选旧材料、原目录与宿主收据不可见；错误摘要拒绝。[隔离结果](rootless-n2a-20261011/isolation-result.json)。
- 独立审查者核对冻结SHA、71项结果、隔离脚本与W5绑定：科学父仍只有H4，旧W2只转交唯一所选文件。
- contracts.py SHA256：4020e775b31204c04da98e025cb518a042dfcacc6867e82bd9d9593859c0e64d。
- history测试SHA256：3ad86bdfb748d3e660c55f5181f76987e2d783f9a6e6849b2d4a57cc49d4a21c。

未调用模型，未做科研评分；所测隔离路径不构成任意系统威胁的证明。安装包的组合入口验证留到N1b与N2冻结之后。N1b工作区未提交实现没有混入本提交。
