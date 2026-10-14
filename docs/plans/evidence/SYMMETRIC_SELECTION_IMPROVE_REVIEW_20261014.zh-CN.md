# 候选对称选择与improve指引独立复核

## 最终结论与范围

**PASS，限定科学指引冻结/送达与既有准入边界的零模型工程资格；未发现剩余阻断。** 安装验收四个文件共48通过，来自38项既有回归与10项新增回归两个批次，无skip，不称全仓绿色。基线 `32e4b08`；生产仅 guidance.py，新默认角色科学指引修订。没有新增配额、修改控制准入、policy或schema。审查者仅阅读授权源码和指定证据，仅编写本报告，未运行测试、构建或模型。

## 根因纠正

最初将extra1误认为improve的硬一次上限。实际单机制improve只有一个ref，breadth awaiting=False，该条件不拦局部迭代。父代理基于原W008冻结配置的纯准入解释，连续四次prospective call均admitted=true且grant_used=null；没有实验执行或原场写入。指定证据为外层 `.trial/receipt-cov-c-rewards-20261014/improve-admission-check.json`，本复核只读取此授权控制证据。真实W008按A要求进行多次refit，不能以未存在的配额作为耗资根因。因此本次不机械把1改为4。

## 审查边界

- A以原目标相同标准比较保留与替换的收益、损失和未知；既有候选不获默认优先权，未知目标最优性不能独自阻止替换；同时proxy领先不强制选择。原审计缺失/未绑定仍未知，审计资格与目标证据、推荐与实际提交/确认保持区分。
- W improve允许依据观察调整候选并继续局部搜索；validate为具体选择补充公平对照证据。二者都不默认每候选后做完整验证，不把浅搜组合要求施加到局部任务。H科学scope、方法归W、必要checks、原runtime/feedback、unknown只查询不重放及辅助者资格保留。
- prepare冻结新literal，job/native_role_instruction沿冻结原文进入实际任务和native prompt；重建已有job读取retained literal。custom及无显式role_guidance的已有job不随默认文本更新。生产未触碰observer、历史重放、resume、common accept、预算或审计资格逻辑。
- DEFAULT与OPPORTUNITY均保2560B总边界；候选选择权仍属科学A，本改动不自动根据调用数/proxy生成判断。

## 已观察证据与限制

父代理fresh wheel/basic实际CLI门禁PASS；安装证据均位于外层 `.trial/macro-role-installed-20261012/`：`artifacts-symmetric-guidance-01-20261014/breadth-context.log` 与 `artifacts-symmetric-guidance-newtests-20261014/breadth-context.log` 及对应result JSON。审查者实际核对两批returncode0、0模型请求，各32模块安装实际字节SHA＝记录SHA＝当前源码。既有scientific_guidance、breadth_admission、closeout_search_replay三个安装文件38通过，16.19s，无skip。新增tests01静态复审通过：实际prepare/build覆盖DEFAULT、OPPORTUNITY、domain后缀、None和custom；旧冻结W的job/task/seal字节不变；真实common local improve三call同scope且grant为null；作者保留旧候选或推荐proxy更低新候选的纯投影均保留且target_best仍未知。新增10项安装通过，2.02s；不声称真实科学选择改善。

本次只证明科学指引可冻结并送达及既有机械边界保持，不证明真实A选择改善、真实improve算法效率、目标达标、token节省或旧场恢复。没有读取隐藏reward或推荐具体获胜算法。

生产SHA256：`0e0677e1a89d4d6b4d2c30f3fdafccbc096d2b41c968fb19ead30b5a1abd8f02`；冻结manifest：`/tmp/scid-symmetric-guidance-production-01.json`。

新增测试SHA256：`53760222c4dc9ab361cd255cd4490eb9ae63b7632b7a50d0d771c02664139298`；冻结manifest：`/tmp/scid-symmetric-guidance-tests-01.json`。
