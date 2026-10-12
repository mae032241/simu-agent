# T5 最终冻结输入独立只读审查

结论：PASS，可启动已授权的唯一框架场。0测试/0模型/0源码或实例修改。

- candidate：`f8427dfe69319e2cac0ecf6b7033da409172159f`；wheel SHA256 `224c76eef9cd84615c16473d23bf3db65edc181b0970ee26a1c00387dd65fc29`。
- manifest SHA256 `e39db2d64ab0be344ed0b943d534690118bfe6fae8b2f421cb164a69a5cc76ec`；qualification SHA256 `9b2ad02b1ae3b96e6b0424b4c0b37073740abbf119a7689be51968ada28e383e`；settings SHA256 `15204b11a15b92cc246cdf53fb7c3902fe6f330f37bbc1ad4dc5eb4d425139f6`。
- 80个manifest originals SHA全部匹配；qualification evidence SHA、settings identity、global original、adapter declared inputs匹配；19个research_loop source/wheel/install模块逐字一致。
- 原public严格8文件（instruction/task.toml/Dockerfile/exp_cli/runner/train/val/meta）全冻结；没有hidden/历史solution输入。namespace配置仅原public、runtime与新场工作/产物范围；未重审生产或宣称实际Codex科学行为已资格。
- instance fresh，无job或started marker。6M tokens/3600 active seconds/24steps；gpt-6.1-sol/high/default，role指导合计1881 UTF-8B，无helpers、无resume政策、无自动retry/amend/ack。
- 每节点 cap：H/E 500k/420s，W 1.2M/900s（与search上限取min），A 550k/420s。
- closeout A每次550k/300s，最多3次；inflight 500k，cleanup30s+submit90s+confirm30s。原控制reserve合计2.15M tokens/1050 seconds/5slots，包含于6M/3600/24，不是额外授权。resolver/audit/提交/确认继续计原消费。
- token为turn.completed观察，不能保证严格零超额；confirmation unknown不当成功、不盲重提交。本次只批准既有授权范围的启动，不证明最终科学效果。
