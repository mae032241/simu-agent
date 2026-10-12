# T4 公开动作规则与开发性回放

状态：44项定向通过（0.14秒），92候选公开动作回放通过，首节点独审通过；父代理执行，本作者未运行。适用源基线 f4f51f9，audit 请求的 protocol9 接线另由独立作者负责。

## 冻结规则

1. 科学证据支持目标条件、只支持公开 proxy、或仍未知，由 A 用原结论说明适用范围和局限；host不解析关键词造支持、不加必填科学表。
2. exact evaluation_key+direction 只产生 observed proxy 最高；不同版本/未知目标权重不跨比。不使用任意分数阈值、模型复杂度或强制简单模型。
3. proxy领先或弱压力证据不足以自动换掉/淘汰候选；未知时由A选择有判别力的下一步，或保留已有结论而不宣称最优。
4. 所选候选缺精确公开audit资格时需要audit；source未知先解析/延期。历史recorded_unbound不等于failed，也不等于qualified。若audit action可用，A的next_action=audit与candidate_recommendation是审计请求目标，不是最终推荐；收到receipt后再作科学选择。否则报告资格缺口。
5. audit qualification不证明target有效。最新A null、历史推荐、proxy、公开submission观测和confirmed delivery分别保留。
6. unknown submit禁止未经核对重提交，允许同operation查询及其他科学继续；开发建议本身不授执行权限，仍受预算/身份/未知执行guard约束。

生产只新增短A guidance literal，全角色<=2048B，旧已冻结literal不改。开发脚本 allowed_actions(view,request,source_status) 是纯建议函数，不是新生产科学判定器、候选chooser或执行器。source_status仅用已有公开源状态，不以文件存在猜资格。

## 回放入口与数据

从仓库根执行：`PYTHONPATH=src python scripts/acceptance/rootless_public_selection_replay.py --pool-manifest FILE --rules-sha256 SHA --output FRESH_DIR`；独立安装环境也可用安装包 Python 执行同一脚本。

必须先冻结脚本SHA，脚本核对一致后才打开pool manifest。从manifest.groups.instance的原公开ledger读取id/ok/val_score，按冻结公开train/val/meta/runner/exp_cli identity分评估组；不同原instance分开，防run-ID碰撞。历史audit元数据仅记是否recorded_unbound，不加载模型、不新audit、不用隐藏值。

输入白名单不包含official_reward、hidden recovery/排名/测试条件；不读取final-summary或评分输出。公开输入和动作输出分开保存。每candidate的audit请求是标明synthetic的规则probe，不伪造历史A判断/新choice。回放范围为最终公开池快照，未重建每个早期决策时点；不可拿后来可见数据冒充旧A当时证据。

公开夹具：fixtures/rootless-selection-actions-v1.json，复用8负例加1个audit请求不当最终推荐。专属test_public_selection_replay.py校验分槽/未知约束、强proxy不强换/淘汰、unbound audit不授资格、hidden输入拒与原始混合元数据非干扰、hash冻结在pool读取之前、guidance上限。

## 报告边界

父冻结规则后已执行公开92池回放：passed=true，candidates=92，choices_generated=0、rewards_generated=0、model_requests=0。结果在外层 `.trial/t4-public-action-replay-20261012/pool-replay/{public-inputs.json,replay.json,report.json}`；规则脚本 SHA 为 `bf36e7100772586340903075c66754064e829c725fb46e511652578a4365435d`。

定向门禁：`.trial/t4-public-actions-tests-20261012`，44 passed / 0.14s。独审报告：`/tmp/scid-t4-public-action-review-20261012.md`。首次入口未设置 PYTHONPATH，在导入 scidiscovery 前失败，未输出数据；父补 `PYTHONPATH=src` 后成功，保留首失败，不计为通过。回放PASS仅证明规则/遮蔽/信息缺口处理，不证明A选择更好、目标成绩提升或真实audit动作已取得资格。

已有隐藏评分可由隔离后验评估者评原choices，不用于此函数、调阈值或挑新choice。历史池已被诊断过，非独立验证；0模型不能替代A目标适用性判断。T5未观察真实A；本节点仍不产生科学效果资格，不扩大搜索/holdout或模型场次。
