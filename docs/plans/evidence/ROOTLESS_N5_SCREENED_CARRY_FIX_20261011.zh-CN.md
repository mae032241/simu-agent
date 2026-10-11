# N5 首场阻断与 screened 状态承接修复

状态：最小修复独立审查 PASS、55项定向检查通过、独立安装只读验证原A2通过。原真实场保持失败记录，未恢复、未重算科学结果。

## 原场

候选 a952005；同一cov单场6M token/3600启用秒，6.1sol/high/default。27.82分钟完成H1/W1/A1/W2，19次正式实验；A2原生成功但封存被拒，状态seal_pending。观测2,808,523 tokens；未缓存输入+输出331,467。节点边界暂停后以新控制器恢复已执行，原H/W日志hash不变。最佳公开val为run11的0.9232；实际提交run17为0.9073，audit0.9109，leakage=false。未运行隐藏评分，不能把公开指标当目标效果。

A1以同机制screen W002核验h001.m1。A2绑定历史A1承接m1，同时直接W004首次核验m2。控制把每次重复screened都当首次认定，错误要求再次直接携带旧W证据。本次不是停滞刹车或预算耗尽，整体验收不通过。

## 修复及边界

search._apply保留所有绑定来源、摘要与非空校验；仅当封存原件重建的当前状态尚非screened时，要求同机制action=screen W。既有状态可沿用，不信view或当前A自报，不新增schema/状态库，不递归继承材料。显式重新打开pending后恢复首次核验要求；这不是允许首次用任意A宣称screened。

## 验证

- 原码新增正例1 failed（0.48s），精确复现本场同类错误。
- test_search、test_history_handoff、test_result_schema：55 passed（12.34s）。覆盖承接+新认定共存、重放一致，以及首次A-only、伪view、非screen W、空或篡改证据、重新pending等拒绝路径。
- 独立审查n0_baseline PASS，源码两文件SHA匹配，git diff --check通过。
- 独立新wheel读取未改的实际A2：旧安装精确同错拒绝，新安装通过输入、search及correction校验。84个原settings/jobs/native/conclusion文件哈希不变，A2仍未封存，没有模型调用或真实恢复。
- 最终wheel SHA d27f857bb1b3282bd49b3a15dda599770dee31456307a9f27f5af507c09aa35e。

证据位于外层工程的 `.trial/n5-screened-carry-20261011/`（回归、diff、冻结清单及独审）、`.trial/n5-screened-fix-20261011/`（安装/原A2只读验证）、`.trial/rootless-n5-cov-20261011/`（原场）。未扩大到老平台全套、真实补跑或科研效果资格。
