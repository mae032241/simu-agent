# T4：公开候选选择与评估盲区

状态：源码、安装门禁与[最终独立评审](ROOTLESS_T4_REVIEW_20261012.md)通过。没有真实模型调用。

## 实现范围

- `selection.py` 只接收封存公开事实，纯投影无执行权限、不读取隐藏评分、不建立第二份账本。
- 在 T2 单一有界谱系视图中替换候选区域；区分同评估版本代理最高、最新 A 推荐、历史推荐、观察到的实际提交，以及独立确认的交付。新 A 的 null 推荐清除当前推荐，不抹去历史事实。
- 缺少冻结交付确认时明确 unknown；不读取可变交付账本来改变旧任务。代理排名不表示目标最优，审计缺失也不变成合格。
- prepare 和新 job 冻结 `selection_protocol=1`。旧 job 缺字段维持原投影；角色指导按 job literal 固定，科学协议8与预算机制不变。
- A 判断候选对全局目标的贡献与盲区。新增指导后四角色总计1738B；控制层不替 A 选择目标条件权重。

## 验证

1. 父级运行5个定向文件：selection、selection_binding、lineage_view、scientific_guidance、closeout。71 passed，13.25s。外层 `.trial/t4-source-20261012-01/batch-001/pytest.log`。
2. 全新 wheel / venv：19模块 source/wheel/install 逐字节一致，实际安装 CLI fake H→W→A、known failure、unknown不重放通过。A003的实际 science-task 断言只有单一lineage、selection_protocol=1、target_best=null、delivery=unknown、推荐null。0模型请求。
3. 安装结果：外层 `.trial/t4-installed-20261012/artifacts/result/result.json`；SHA256 `88466964e6501197cd8cf5730df9ee68f099678b64583b7a400b4be9af8dd720`。wheel SHA256 `63f459e6ba78e80e9af04047650e9f38b2d26eff4be6d01792eb3791c672ff73`。

本节点未验证真实科学选择收益、目标级分数或跨场稳定性。T5仍只授权单场框架组600万token／60分钟。

## 启动前独立集成修复

T5预检发现旧交付适配器的runs路径映射，以及同名脚本被后续实验覆盖后选择早期候选时的原件绑定缺口。另行修复、测试和独审；不混进T4安装资格。交付应使用控制层封存的对应执行原件，不要求W维护引用或哈希。
