# dev 交接：P1–P5 增量收口与 main 选择性整合

## 1. 当前任务和用户决定

用户要求继续补齐薄框架 P1–P5，然后检查 main 的 UI/功能改善，尝试合入；完成后写详细 handoff。
每个节点遵循实施 → 独立审查 → root 定向验收 → git 提交。本轮不授权新的付费模型场、远端 solver 或推送。
用户拒绝旧安装矩阵、重复全量测试及并行安装；测试必须控制内存。

科学角色保持 H/W/A/E；不恢复 LLM Root 或 MCP 调度，不把文件哈希/封装/引用推算重新交给模型。
授权边界按用户决定维持可信 Worker 的软边界，不宣称抵抗同用户恶意进程；强隔离不在本轮。

## 2. 路径与 Git

- 外层工作目录 `/home/da/project/ai4s/tcad/git_release/scidiscovery-agent` 不是 Git 根。
- 实际 dev 仓库：上述目录下 `123/scidiscovery-e5.2`，分支 `dev`。
- main 来源工作树：上述目录下 `123/main`，本地 HEAD `15d2985`；本轮保持只读。
- 2026-10-17 成功 fetch github main：远端 `e27352a7f0efec6c8100a3d0036ec0e4d11a6577` 已是 dev 祖先，无待合远端提交。
- 实际待移植的是本地 main 后续提交及 WIP。不能把‘远端已包含’误解为‘本地 main 全部改动已合入’。
- main 44 个 tracked WIP 加6个 untracked 的冻结评估见 `MAIN_THIN_INTEGRATION_ASSESSMENT_20261017.zh-CN.md`。
  tracked diff SHA256 为 `89145d9d996a582667e2195f2a40efd53abf37a86e5bc9794cb293901acab015`。
- 不运行 `git add -A`：仓库有大量既有未跟踪 `.trial/` 和9月证据目录，不属本轮，不擅自删除或提交。

## 3. 先前已提交的薄框架节点

| 提交 | 实施范围 | 必须保留的限制 |
|---|---|---|
| `86e1683` | 新部署默认薄 CLI，旧入口显式启用 | 仍有实际消费者的旧入口不贸然删除 |
| `b670c2b` | 原实例缺失普通材料恢复 | 不授予任意归档恢复推进权 |
| `c59e4b6` | P2 原 accepted 调用跨 boot 有限维护，P4 外部 owner 与冷 checkpoint | 同宿主原路径、显式登记、恢复暂停、原预算/原调用不重发 |
| `e7e8bb1` | P3 自包含 TCAD V2 准备原件、可选 observer 声明来源 | 未声明仍 unknown，不证明任意 shell 外读隔离 |
| `326b573` | 本轮迁移验收账、当前文档、main评估、浏览器用例显式启用 | 不是全部生产资格通过 |

计划权威入口：`docs/plans/THIN_CAPABILITY_MIGRATION_20261016.zh-CN.md`。
本轮功能结果：`docs/plans/evidence/P_FINAL_INCREMENTAL_ACCEPTANCE_20261017.zh-CN.md`。
消费者保留/删除决定：`docs/plans/evidence/P5_ENTRY_RETIREMENT_LEDGER_20261017.zh-CN.md`。

P1 配置接线及 P5 默认入口已实施；P2/P3/P4 的本轮缺口已补齐并分别独审。
**源码实施收口不等于 P1–P5 全部生产验收**：浏览器、真实 TCAD、实际掉电、跨宿主仍有限制。

## 4. main 选择性整合

### 曲线追踪（已提交 `6fa5f9b`）

生产文件 `plugins/curve_figure_evidence/curve_figure_evidence/figure_line_tracker.py`，
精确采用 main WIP hash `aeb6ca7f701624e15bdb83813b6fe4e9f9d2f81fb3330895f993d70d9f03578f`。
修复实际锚点路径、断段被全局锚数量误删、反向半像素取整和 singleton 浮点支撑范围；
保留真实歧义和 gap，不猜完整曲线。新测试为 `tests/operations/test_figure_anchor_tracking.py` 六项小栅格。
独立审查与运行结果见同目录 `MAIN_CURVE_ANCHOR_MIGRATION*` 两份证据。

### 薄 UI

借鉴 main 独立结果页、精确指标和分栏信息；适配现有封存原件，不复制旧 SQL/read-model。
已提交 `6eaf319`；精确实施、验收和接口见本文件末尾最终状态。

### 没有整包合入的内容

- main `15d2985` 的旧 SQL general_science_results / MCP 路由及旧容量阈值。
- 旧 Root admission/debug/takeover 及已淘汰的会话治理。
- TCAD SubmissionNotCreated 相关整套旧执行改动：需单独验证幂等键/真实未提交证明，不能把未知提交当成未提交退款或重发。
- 旧安装/部署文档不能覆盖新默认薄 CLI。
- 图片自动主图/聚合没有精确声明时不猜图；可后续基于 exact identity 单独适配。

## 5. 测试纪律及已知结果

唯一执行者 root。作者冻结后才运行，串行、不安装、不跑全量、不启动真实模型。
解释器 `/home/da/miniconda3/bin/python`；既有依赖已由用户在 base 安装。

```
/home/da/miniconda3/bin/python scripts/run_tests.py \
  --config .trial/p_migration_validation_20261017/resources.json \
  --lane source --output .trial/<唯一证据目录> tests/<精确目标>
```

HTTP/独立进程用 `--lane process`，一次命令一种 lane。监督配置：
数字线程1；树 RSS 采样止损805306368B；最低可用10GiB；可用降幅1GiB；120s；日志2MiB。
这是采样止损，**不是 cgroup 硬隔离或 OOM 保证**。不为跑过测试随意抬上限。
失败先保存原日志，定位修复独审后仅复测影响项，不将‘基线也失败’当放行理由。

前轮13个不同功能目标最终通过，发生两次失败：fixture错误、通用accepted身份错取Local私有字段；
后者已修为 `accepted.interface.config_sha256`。详细批次/内存/原失败均保留。
本轮曲线6通过（0.48s）；监督1.054s，RSS68,874,240B，cleanup_complete=true。

浏览器资格仍未完成。之前 Chrome 长TMPDIR失败修复后，RSS达1,121,267,712B触发止损。
`tests/research_loop/test_instance_browser.py` 仅 `SCID_RUN_BROWSER_CHECK=1` 显式运行；默认跳过。
不要重复启动 Chrome 或提高限额。本轮 HTTP/HTML测试不冒充真实浏览器通过。

## 6. 后继应如何继续

1. 先核 `git status` 与本文件最终提交栏；不要覆盖其他作者未提交文件。
2. 若只是继续整合，先查本地main源指纹，按一个可审查功能移植；无须整包 merge ancestor。
3. 优先确认用户下一步是否是 UI 浏览器资格、真实远端/模型验收或剩余 main 功能；这些不是本轮静态 PASS 可代替。
4. 新真实测试须单独预算和明确范围；已结束场额度不重用，不私自启动模型/solver。
5. 恢复必须走现有 checkpoint/维护 CLI，不直接编辑账本，不通过复制目录制造新的可推进 owner。
6. 保持通用插件边界；cov/local/TCAD 的能力缺失要诚实标识，不能伪造候选或来源资格。


## 7. 本轮最终交付状态

- 曲线功能提交 `6fa5f9b`；UI功能提交 `6eaf319`。最终文档提交承接其后，不在正文自引用自己的未知hash。
- UI路径：`/results?after=N` 为20项封存记录分页；`/results/<step>` 为精确结果页。
  原 `/nodes/<step>/science` 与 `/nodes/<step>/materials[/index]` 不变。
- 权威数据：`instance_science` 验证同一seal/raw和job哈希；排名取job输入时已冻结的
  `history.view.candidates`，页面显式说明观测边界。普通A本节点推荐单列，null不回填旧推荐。
- UI不在每次读取时遍历并重算历史排名，不采实时预算时钟，不把结果存在当科学成功。
  CSS为模块常量，由哈希CSP授权；无JS/CDN，无新增安装资源。作者内容转义，HTML/SVG附件仍下载。
- `execution_authority.implementation` 将新 `instance_render.py` 纳入既有实现身份冻结。
  因此不要假装旧进程/旧冻结运行自动采用新UI代码；保持已有实现变更校验，不篡改旧签名。
- 新2项source和既有HTTP目标的增量验收全部通过：
  `test_result_cards_preserve_exact_ties_and_do_not_replace_empty_a_recommendation`、
  `test_result_routes_are_read_only_exact_and_independent_of_live_clock`、
  `test_loopback_science_download_uses_existing_browser_scope_and_safe_headers`。
- 日志分别在 `.trial/main_ui_source_20261017/batch-001/` 和 `.trial/main_ui_http_20261017/batch-001/`；
  2source耗时0.64s、1HTTP耗时1.02s；监督合计2.100s，峰值66,510,848B/67,137,536B，清理完成。
- 本轮合计9个不同定向目标通过，无安装、全量、Chrome、模型或solver新运行。
- main源最终复核HEAD/diffhash未变；仓库剩余历史未跟踪目录保留。未向远端推送。
- 没有正在运行的测试或付费场；实施者已冻结，审查者只读。下一轮可安全从最新Git节点继续。

最终证据入口：`docs/plans/evidence/MAIN_SELECTIVE_INTEGRATION_20261017.zh-CN.md`。
本handoff是当前交接入口；历史报告内的‘当时尚未合入/fetch失败’仍作为历史截面保留。
