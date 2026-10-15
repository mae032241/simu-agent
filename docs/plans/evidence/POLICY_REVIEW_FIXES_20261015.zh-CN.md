# 角色预算与收口策略审查修复（2026-10-15）

基线：`5ca961e`。本轮修复审查确认的控制边界问题，不声称科研得分改善；未运行真实模型。

## 修复

1. `role_share.effective_route` 保留语义作者补正及原始根身份，由现有补正次数和总预算准入约束。可选 H/A 路由超额时进入已有停止/收口路径，不再由控制层选择 W、机制或任务类型。
2. controller 和 CLI 的角色份额、自动短名单策略默认均为关闭；显式配置仍可启用。安装预检原样透传启停状态，不再为旧来源自动添加 selection_policy。
3. 短名单不再按候选数量或最近时间猜评估版本。单一明确版本/方向可排序；多版本需要显式 `evaluation_key`。未明确时不产生默认排名，只给 A 有界的各组代表与推荐候选，并报告遗漏数量。冲突方向不会混排。
4. 可选 smoke 和 audit 均在 soft/hard 模式保护收口 A 的时间与 token，以及执行提交/确认底线；余量不足时不发起检查。已有不确定调用仍不可重放。
5. 保留隔离模型加载/预测检查、原件和日志追踪、对称比较表、真实入口无模型预检。

## 验证

- 源码定向：角色预算 14 通过；短名单/收口 52 通过。
- 新增补正反例：H 请求无来源 repair 后仍派 H 补正，合法修订后才派 W；连续补正最多两次，重启不重置；份额不足不会派替代 W。
- 新增选优反例：旧评估版本候选多也不获得默认地位；精确选择少数版本有效；版本前缀不匹配、方向冲突不排名；soft 模式也保护作者预算。
- fresh wheel 安装验收：`test_role_budget_share.py`、`test_control_selection.py`、`test_prelive_production_chain.py` 合计 **74 passed / 102.21s，无跳过**。使用 `python -I -m pytest -o pythonpath=`，34 个 research_loop 安装模块与当前源码 SHA 全部一致；含真实 CLI/bwrap 和公开 runner 的零模型交付链路。
- 证据：外层 `.trial/policy-review-fixes-20261015/checks/pytest.log`、`result.json`、`installed-hashes.json`。资源监督 returncode=0、cleanup_complete=true，峰值 RSS 428,544,000B。Wheel SHA256：`8c982393f9e376df6f26b7afcf8976bdf8609713ca6f7cf83274b0aacdd1706e`。
- 独立只读审查已覆盖路由、有限补正、原件重放、策略启停、评估版本与收口预留，未发现阻断；审查者未自行运行测试。

## 过程与范围

初版 H 补正回归夹具错误地把已有机制再次声明为新增，导致后续 W 覆盖不足；已用 existing_ref 修订原机制，未放宽生产准入。首次测试包装未继承串行锁描述符、首次资源包装缺输出目录，均在模型调用之前失败并修正。

没有迁移或重启既有实例，没有增加预算，没有推送远端。已生成的旧自动改道 job 不作静默重写，仍受 retained-job 一致性检查。完整测试套件未运行；本轮只对相关路径做定向验收。
