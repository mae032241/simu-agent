# T4 后交付集成修复

状态：定向门禁、安装和原公开执行器交付链通过，[最终独立审查通过](ROOTLESS_T4_DELIVERY_REVIEW_20261012.md)；T5 尚未启动。此节点独立于 T4 选择投影。

## 已定位问题与修复

1. 新 cov launcher 的公开运行 alias 是绝对 instance/runs。T5 prepare 的 namespace_runs 改为同一冻结 alias；scid Python 起 adapter、task Python 运行公共 audit，两者明确分开。
2. W 可以同名 train.py 迭代。交付旧候选不能读取当前 row.script 或 current model_runN。core 从已验证的封存 observer context 绑定该候选的 archived proof blob；仅以 execution/SHA 挂入 resolver，返回 proof_label 由 core 精确解析，不挂整个历史、package 或私有根。
3. cov resolver 仅接受唯一 known_success、同 candidate/run、同冻结 row 的 source.py/model 原件。仍为 audit_pending；资格要经原公开 harness 的隔离 audit/promote/confirm。
4. v2 缺失、歧义、unknown、不可回读 proof 不回退；archive SHA/身份失配硬拒。v1 无 managed context 的旧路径保留，但明确只是 current-source snapshot，未保证历史代码版本。

复用已有来源额度、deadline、SHA 去重和执行权限，无新增预算/ledger/候选状态。源码 diff 的通用 core 不理解 cov 文件名，领域选择留在 adapter。

## 验证范围

作者仅 AST 检查，未跑 pytest/build/model/commit。新增专属 tests/research_loop/test_cov_delivery_lineage.py：实际 bwrap resolver，改当前脚本/model/call 后选旧 archived P、alias 错配、archive 篡改、v2 缺/多/unknown/unretained 不回退、v1 兼容。

父级已执行：该新文件 + test_delivery/test_lineage；新 wheel 字节绑定及原公开 harness 真实 task Python 的 audit/promote/confirm，结果见下。fake namespace 正例不能替代真实公共审计，也不证明真实模型科学收益。冻结清单保存在外层 .trial/t4-delivery-integration-20261012/source-freeze.json；T5 prepare 启动前还须最终脚本独审与真实 qualification。

## 父级执行结果

- 三个定向文件：33 passed、2 skipped，11.73s；跳过的是需显式环境的原公开harness两项。日志：外层 `.trial/t4-delivery-source-20261012-01/batch-001/pytest.log`。
- 全新 wheel/venv 的19模块源码、wheel、安装字节一致，CLI回归通过，0模型。结果 `.trial/t5-candidate-installed-20261012/artifacts/result/result.json` SHA256 `b88d8794ab73f648aa76a909a7b65a22cf8c15fef38b305af0c4a623017f3d98`；wheel SHA256 `224c76eef9cd84615c16473d23bf3db65edc181b0970ee26a1c00387dd65fc29`。
- 原公开执行器在真实bwrap里跑2次constant-zero。随后故意把同名train.py覆盖成抛异常的代码；A选择run-1，真实controller完成独立namespace的audit/promote/confirm，终态delivery_confirmed。结果 `.trial/t5-delivery-gate-20261012/result-02/result.json` SHA256 `0feece9b842de18df3be5ebbd7fa47c2818e6c0ad406974a4d5891748580068d`。
- result-01未进入实验：父编写的gate漏传delivery所需all-role节点预算，prepare按合同拒绝。修复gate后跑result-02，生产代码未改；旧失败目录保留。不是模型失败或自动科研重试。

上述实际公开实验和审计不调用LLM、不读隐藏评分；native transport仍为模拟，实际Codex行为及科学效果由T5另验。
