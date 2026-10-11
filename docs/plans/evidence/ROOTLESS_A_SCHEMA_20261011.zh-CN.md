# 第3场 A 输出 schema 修复

基线 e33ee9a。第3场 H/W 已封存，33次正式实验，公开最高run30=0.9165，实际提交run33=0.9137、audit=0.9091、leakage=false。A首次请求因 `candidate_recommendation` 未包含在严格schema的required中被API400拒绝；不是分析结论或科学封存内容不合格。

根因：构造required之后追加了可空候选推荐字段。最小修复：新协议4要求字段存在，但允许null表示不推荐；不强迫科学选择。旧协议1/2/3 schema与已封存原件保持原行为，新版不偷偷改写已准备的失败A。

独立执行 n0_baseline，独立复审 n_plan_review：PASS。67项定向测试通过（11.62秒），覆盖四角色严格schema、推荐为空/字符串/缺失、旧协议原schema与封存恢复、未知候选仍拒绝。生产argv引用的实际schema生成入口已核对。本节点没有重投模型，也未改动既有实例或安装包；真实A恢复仍未验证。

证据见 [源文件身份](rootless-a-schema-20261011/source-manifest.json)、[API错误](rootless-a-schema-20261011/native.jsonl)、[测试](rootless-a-schema-20261011/pytest.log)。
