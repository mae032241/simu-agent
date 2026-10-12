# N6b 独立跨边界源码审查（2026-10-12）

## 当前结论

**最终 PASS，无剩余源码或本节点提交资格阻断。** 审查基线为 `7c6072cdc916cbaca9bfd7542ac0049df2f9101a`，对象为本轮 N6b 工作区源码、新增测试与实际安装证据。审查者未实现本轮代码、未运行测试或模型、未改科研实例或提交 Git。使用 `scid-cross-boundary-review`。

最后三文件冻结 `.trial/n6b-implementation-20261012/final-delta-freeze.json` 已逐 SHA 核对：

| 文件 | SHA-256 |
| --- | --- |
| budget.py | d78c683a7438c366eecaf5b703335e1e7ab43c337d0c6e0c4c6c50ad9c70a609 |
| controller.py | ce0643fd55b165e516abefde6f5aeb628b401d145af688d72616b09ae5639d42 |
| test_closeout.py | 605526017eddcb46c596943e4810cb52bf198209b16e43f5bd9c88054497083d |
| delivery.py | 1b3e1a03d11f87ad28a796f6a8fa86243d2e9a1e0409f1ed15a08b84c7889446 |
| cov_delivery.py | eac83d833adb9e3eb26c7494db4327134bd0909bf49a8422cefb604c6ebf2023 |
| test_delivery.py | 6c99b374fbe144e89be40d75346562ff46b8c0205cf79ceef848cedca04c38c9 |

其余源码/测试依据 `.trial/n6b-checks-20261012/rootless-freeze.json`。`git diff --check` clean。父代理后续只改验收状态/审查记录的文档更新不在此生产代码资格内。

## 实际追踪的路径与结论

1. **prepare → 探索准入 → native Popen → 收口预算。** 交付策略只在新 prepare 显式冻结；旧实例不后补字段。探索真实接受与 Popen 复核使用同一预算准入，扣原锚点已消费时间，已 prepared 节点不重复加一个名额。收口 A 同样保留剩余自身 allocation、cleanup 未消费部分、submit/confirm 秒数、inflight token 和两个动作名额。预留属于原总额，未创建平行余额。硬阈值 token 是原生 turn.completed 的 input+output 观察量，不重复加 cached，也不声称实时精确上限。
2. **已知停止洞 → 连续已封存前缀 → 收口 A。** 普通 run 仍不能跳洞。closeout 明确冻结最后连续 sealed 前缀及必要直接补正 A，不给失败 W 伪 seal。prepared job 冲突在发表 begin 前拒绝；显式 closeout 可用后续空 slot，原 job 不覆盖。原 pause 与 N4 exact ack 仍生效，收口 A 不算科学进展、不消费科学许可。
3. **原候选观察 → 交付源快照 → A 科学选择。** 核心不从 status=ok、代理最高、A 普通推荐或旧 actual 猜审计资格。泛型 resolver 只从确切已封存候选观察及冻结读取范围取得来源；每源模型、代码、公开 harness/data 有界冻结为 audit_pending。A 选择候选而不填写/伪造审计。无 adapter 收窄为本地 export-only，不派新 A 或 resolver。默认源 brief ≤4096 字节，完整源 ≤128、单件32MiB、总128MiB，并保留 omitted/unavailable；候选第17项可经既有分页选择，不因前16项展示而永久不可选。
4. **选定候选 → 原公开审计 → promote → confirm。** A raw/job/seal、完整源包、adapter 与调用解释器身份均复核。实际 cov adapter audit 在 scratch 执行原 exp submit，audit namespace 不挂真实 target、hidden 或控制目录。只有审计完整、指标有限、leakage=false 且模型/来源身份一致才 promote。skip/fail/timeout/malformed 不更新旧 target。核心不 unpickle。promote 多文件写入 marker 最后；半写/崩溃保持 unknown，不能冒充 confirmed。
5. **持久 action → 进程 phase → 重启查询。** submit/confirm 意图与结果沿原 control-ledger，动作消耗原步数和 active 时间。每次 Popen 的 phase PID/boot/start/sid/pgid/task identity 持久化；缺 final promote proof、错误 identity、cleanup_unknown 均阻下一动作。已接受 submit 不重发，符合条件只可接受有界同 operation confirm。最后增量另核实际 leader 已死、普通同 sid/pgid child 仍活：只读 /proc 发现活成员即拒 confirm，观察失败保 unknown，绝不向 stale PGID 发信号。记录了原 fixture 精确 child PID 收尾，而非 sleep 掩盖生产问题。
6. **纯导出与状态。** export-only 不启动模型/外部 action，不补 scientific seal；可写本地收口与时钟事实，因此不是文件系统零写。status 使用前缀安全只读投影，不写历史缓存。resolver 明确 cleanup_unknown 的 export-only begin 仍阻 inactive/amend，不能靠导出退款。submit confirmed 尚未最终 confirm 时 current_actual 为 unknown；科学目标始终 not_asserted。

## 已关闭的实质发现

- 核心原先直接解释 cov 来源：改为独立、冻结且有界的 resolver/provider 接口。
- 启动器 symlink 目标变化：同时冻结调用路径及 resolved 路径/hash。
- 输出限额曾限制合法模型写入：改为 stdout/stderr 合计有界读取，保模型资产独立限额。
- 全池重复读取静态公开输入：预冻结对象去重、验证按 path→hash/size 去重，冲突 alias 硬拒；删除 binding 的重复全包读。
- audit-only/no-outcome 窗口、错误 PID identity 与普通存活 child：最终 phase proof、精确身份及只读同 group 活性 guard。
- prepared slot 永久陷阱、Popen 只看自身 cap、收口 A 侵占后续动作 floor、无 intent 拒绝误称 retained：各自精准拒绝及负例。
- resolver cleanup_unknown 允许 inactive/amend、pending 候选被要求先自造 qualification：最终 typed guard 与科学任务文字已对齐。

## 已读取的验证证据

- `.trial/n6b-checks-20261012/rootless/batch-001/pytest.log`：**336 passed /139.49s**，对应 rootless-freeze 快照，不虚称它包含后续全部增量。
- `fourth/batch-001/pytest.log`：**17 passed /20.28s，无 skip**，包括实际原公开 exp_cli/runner/train/val/meta 在 taskpython+bwrap 下的合法 ZeroPredictor audit/promote 与 audit skip 拒绝。fake 安装单独不能证明这个隔离边界。
- `final/batch-001/pytest.log`：**65 passed /34.74s**（closeout/node_budget/delivery 三文件，真实 public ENV），覆盖 floor/cleanup/pending 增量。
- `final-recovery/batch-001/pytest.log`：**13 passed /9.52s**，最后同 group child 与无 intent typed 诊断已通过。未重复全套336项；全套快照与两次后续精确增量分开记录。
- 首安装 `.trial/n6b-installed-20261012/result/result.json`：wheel `d9e502fa2a3921563999e90540a432e5e1b9b4bfead504962d0d66a6a43117c0`、十项无模型 CLI checks PASS；作为修订前安装证据保留。
- **最终安装** `.trial/n6b-installed-final-20261012/result/result.json`：wheel `e5e37103747954c3a484ae25c9530f745203782eb3a31438582e566e933dd82b`、十项无模型 CLI checks PASS，包括旧 node-policy、正常/token/time/steps 收口与已知 hardstop 洞。亲阅 result/module-bindings，并另行只读逐字比较13个 research_loop 模块：当前 source = 最终 wheel 内容 = venv 安装内容；wheel SHA 与结果一致。

测试由作者/父代理经共享串行入口执行；本审查仅读取日志、夹具和冻结原件。初轮字段/fixture 失败与后续修正保留，不将初失败归为最终通过。

## 扩大范围的复审

原450–700行估量失准：本轮 N6b 新生产约1240余行（delivery448、cov257、核心约535，末增量另加少量），新增测试约417余行。**修订范围可接受**：新增职责集中在四条必须真实接通的路径——普通候选来源快照、原公开隔离审计及提交、持久未知执行恢复、停止洞的前缀收口。仍只有原 control-ledger 和一个预算权威，没有新 Root、候选树/ledger、独立调度引擎或平行余额。已削除重复 I/O；不应为达到旧估数删除资格/恢复验证。新增通用后台引擎或第二状态权威不在本次批准内。

## 资格限制

- 0科研模型请求、0 N5恢复、0真实实例修改；不证明真实科学效果、最优候选、零 token 超调或收口一定成功。
- 原额度不足/usage unknown/原 pause/unknown execution 仍可使收口仅导出或停止；不会追加额度。原 N5 只余约7.2 active 秒，不能据本节点声称实模型恢复完成。
- 实际 cov 隔离资格依赖冻结 launcher/runtime 与公开 harness；普通任意 shell 仍为软边界。标准同 group 子进程受观察/清理，逃逸或 daemon 需 launcher 保证，不承诺任意脚本幂等。
- N6b 会重接仍活原 runner、补封存已成功原输出；不实现已停止 Worker 原线程续接。后者为独立待实施节点，设计及评审不能当已上线。
- 有界全池源冻结可能遗漏/容量不足或来源不可回读；明确 unavailable/omitted，不猜来源、不把未审计候选伪造为已 qualified。

最后精准门禁、最终 wheel/source/venv 字节一致和安装 CLI 复验均已关闭。本报告批准本节点代码与验收证据提交；保留以上科学、预算、隔离及 Worker 续接限制。
