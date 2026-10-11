# N4 两级纠偏工程验收

状态：实现、双独立审查、必要无模型回归与最终 wheel 安装入口通过。真实模型测试依用户要求暂停，科研效果与真实恢复资格待验。

基线：N3 `c19498a`。受审源码摘要见 ROOTLESS_N4_SOURCE_FREEZE_20261011.json；提交前仅同步设计文档状态文字，生产与测试源码保持该清单摘要。

## 实现范围

- 显式 prepare `--correction-policy` 冻结 `review_after=3 / pause_after=2`，未启用旧实例不新增门控。协议6 A的 nullable `progress_assessment` 提供科学判断，旧1–5不改包。
- 按新封存 A 计数，等待/E不计；无进展与评估未知分开。控制只核已绑定原件与去重，不替 A 判科学正确。达到首阈值实际派H，原A字节不改；H回应后继续未解才暂停。
- trigger/ack是不可变事实，沿既有seal/job重放。单条发布后立即重算，已发表暂停不被晚到结果抹掉。已接受工作仍能收集封存；只阻止新的派发。
- 确切ack最多放行到下一非延期封存A；普通continue/旧ack不能豁免，不退款不续额。确认后未知也不能绕过既有未解暂停。说明超出完整事件16KB写前拒绝，保留原账本和暂停标记。

## 证据

- 完整 rootless：`tests/research_loop`，200 passed / 73.27s。完整源码候选记录：`.trial/n4-evidence-20261011/scid-n4-rootless-final-20261011/`。
- 最后字节限增量仅 correction.py/test_correction.py：4 passed / 7.25s；UTF8/转义说明及正常/跨桶ack。证据 `.trial/n4-evidence-20261011/scid-n4-ack-byte-bound-final-20261011/`。没有将修复前200项误写为最终全量重跑。
- 科学/源码独审 `/root/n_plan_review` 与恢复/计数窄审 `/root/n0_baseline` 均核对最终12SHA并 PASS。审查发现的发布顺序、跨桶ack及记录容量问题已修，报告副本在 `.trial/n4-evidence-20261011/recovery-independent-review.md`。
- 从最终源构建 wheel，在新 venv 调用安装CLI：12节点后暂停，第三次A确实改派H；普通continue不动，错误ack保留用户暂停；确切ack只新增W/A两节点即再次暂停，旧ack拒绝，累计168观测tokens而上限仍2000，无重派发。
- 最终安装同时验证超长ack原子拒绝后status仍可读、原pause/ledger不变。证据 `.trial/n4-installed-final-20261011/`；wheel SHA256 `f3ad3cb1d01e4a1e7168c107c87c2a1589f4cca61b5130d4cb8c3d08bda8c0fb`。
- 上述 .trial 路径均相对外层工程目录。所有模型调用为0，未修改真实测试实例/冻结包；共享串行测试锁未绕过。`git diff --check`通过。

## 未验证的边界

不宣称能识别A的语义误判、跨所有原生shell的违规或自动达到科研目标。无证据的新文件/节点本身不算进展，但有新原件而A判断错误仍是已知限制。主机确认权限依赖隔离启动器，说明文字不是身份认证；raw Codex仍软隔离。N1/N5真实A、长期恢复、科学收益缺口保留；本次未跑老平台全套、TCAD或浏览器。
