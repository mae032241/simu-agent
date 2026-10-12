# N6c：Worker 原线程续接验收记录

状态：源码、回归、独立审查与零模型安装验收通过。基线 `a5f4bb7`。未调用科研模型，未恢复原 N5，未追加额度；实际 Codex 同线程恢复与增量用量未验证。

设计及范围以[原线程续接设计](ROOTLESS_WORKER_RESUME_DESIGN_20261012.zh-CN.md)为准；命令见[CLI 说明](../../ROOTLESS_CLI.zh-CN.md#可选的-worker-原线程续接n6c)。本记录只汇总验收事实，不重复设计。

## 已取得的证据

原日志位于仓库外层 `.trial/`，失败记录保留，未被后续通过覆盖。

| 范围 | 证据目录 | 结果与解释 |
| --- | --- | --- |
| 首轮源码定向 | `n6c-checks-20261012/first` | 76 通过，40.70 秒 |
| 第二轮源码定向 | `n6c-checks-20261012/second` | 97 通过、1 失败、2 跳过，50.72 秒；NaN 负例误用严格 JSON writer，尚未到生产读取门槛即拒绝。夹具已改为原始 JSON 注入，生产未放宽；该轮不记完整通过 |
| 首轮独立安装 | `n6c-installed-20261012` | 夹具误判 resume argv，保留失败日志，不计通过 |
| 第二轮独立安装 | `n6c-installed-02-20261012/result` | PASS，7 项检查、0 模型请求；初次14 + 续接22 = 累计36 observed tokens，cached 不重复加 |
| 完整 research_loop | `n6c-checks-20261012/rootless` | 360 通过、无跳过，170.29 秒；在最后完整性增量之前，含实际 public harness/e11/bwrap 零模型用例 |
| 最终定向门禁 | `n6c-checks-20261012/final` | 106 通过、无跳过，56.03 秒；覆盖最后完整性增量，含实际 public harness/bwrap |
| 最终独立安装 | `n6c-installed-final-20261012/result` | PASS，7 项检查、0 模型请求、累计36 tokens；15模块 source/wheel/installed 字节相同 |

第二轮安装检查涵盖安装字节身份、同节点/会话、checkpoint 保留、原件不变、成本累计、普通 run 不重放以及成功后不再次续接。成功科学 raw 在 continuation 原件中，初次失败原件保留。此处会话与输出由 fake transport 提供，不能证明真实 Codex 会话或任意 shell 幂等。

## 最终收口与快照区别

[最终源码独审](ROOTLESS_N6C_REVIEW_20261012.md) PASS，无剩余阻断。归档报告 SHA-256：`a27fd13fc9b1437b886879d0c09fb91ec15dd860041633d15d055662d3482f42`。最后两处完整性接缝是 seal 前的进程原件 digest 绑定，以及 Popen 前冻结 schema/science-view 的准入复核；由最终106项精准门禁和最终安装验收覆盖，不声称完整360项在这些增量之后重跑。早轮失败及跳过继续保留，最终门禁无跳过。

最终 wheel SHA-256：`e94ff461a186eb5146447cc7d522cdc9f7c77ea405a74c7a84f11a1ef7721fcc`；精确模块 SHA 见最终安装 `module-bindings.json`。实际 public harness/bwrap 用例证明其无模型执行与隔离边界，不证明真实 Codex session 能续接。

## 不变边界

显式新策略、最多两次新增 accepted continuation；原 node/W cap、全部 attempt 消费和交付预留继承，不退款、不自动扩额。unknown、缺必需 meter/真实 session、清理或身份失配仍拒绝；成功待 seal 优先补原结果。旧 fresh-only launcher 与原 N5 不自动迁移。

实际 Codex 同线程有效性、resume 增量用量和权限尚未取得验证。该节点不增加角色机械登记，也不承诺普通任意脚本幂等。后续 T0 仍待设计评审，本节点工程通过不等于科学效果通过。
