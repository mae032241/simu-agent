# P5 部署与续研交接

日期：2026-09-08。P0—P4 已完成；[独立实现 R2](../../reviews/RESEARCH_CORRECTION_IMPLEMENTATION_REVIEW_R2.zh-CN.md) 仅放行冻结的 Local 工程候选。实际部署、资格恢复与 P6 两轮真实研究尚未完成。

## 候选与已做检查

- [最终增量](p4-candidate-final.json)：14 个生产文件、17 个验证 fixture、2 份架构文档，候选 digest `27da282cee930c816f32a0f070153de8516cd8f2b3179429f73bb433984d3bc9`。
- [完整验证记录](p4-checks.json)：676 passed、10 failed、0 skipped。七项是非默认 Hardened 的既有能力限制，三项是结构快照/阈值问题；实际新增行数另行审查，未提高阈值。此处不把完整验证称为全绿。
- 单批 wheel 安装目录与源码的 49 项 Operation 身份完全一致，ABI 17；生产服务当前仍是旧目录。
- [只读预部署记录](p5-predeployment.json)：实例为 M7-test0，核对时 queued/running Run、待决审批、外部执行均为空。部署前若状态发生变化，需重新核对。
- 以下命令仅将末尾改为 `--dry-run` 已实际执行，退出码 0；源码、依赖、图像工具和部署预演通过。systemd 扫描既有系统单元时的权限/未知配置项提示原样保留于日志，未据此声称已部署。
- [完整候选目录清单](p5-source-directory.json) 登记 Git 可见的全部当前文件、删除项与摘要，包括先于本次任务存在的工作树改动；不把最终 33 文件增量冒充完整发布树。本清单自身不纳入自己的摘要，也不纳入 Git 忽略的缓存、状态与构建产物。

## 必需资格及升级后的处置

下表是部署前的可建立性核查，不是科学路由命令或未来 preflight 结果。操作名称来自本会话实际 Root 编译目录；新安装候选保留这些 Operation，身份摘要改变。部署后必须重新查询目录，以实际声明绑定。

| 现有确切原件 / 资格 | 升级后处理与已注册建立路径 |
| --- | --- |
| `ingaas_inalas_fig4_source_paper` | 原始 PDF，4,714,974 字节，无旧 producer 标签。可作为确切来源。已注册 `science.figure.request.prepare.v1` 可仅绑定论文；其可选 research_objective 不构成旧目标资格的启动依赖。 |
| 旧 figure_request / materialized figure family / intake / audit | 不继承旧 producer/review 资格。以原 PDF 经新请求、`science.figure.evidence.materialize.v1` 产生完整新 family，供 `science.evidence.extract.figure.v2` 与其精确独立边 `science.figure.evidence.audit.v1`。完整 family、来源、审查 subject 必须同源，不混拼新旧输出。 |
| `fig4_e55_intake_split_1.scientific_foundation` | 旧资格不可直接恢复。新 intake 与精确 passing audit 可由 `science.intake.split.v1` 建立新 foundation；`science.evidence.qualify.v1` 绑定该 foundation、原 extraction、独立 audit、完整生产者/验证/冻结来源，再由精确 UI 决定资格。只重审旧对象不够。 |
| `fig4_e55_research_objective_1` | 旧目标保留为历史原件，不换 schema 重摄入。新合格 foundation 的 objective_contract 经 `science.objective.project.v1` 产生新目标；科学 Agent 与资格审查须保持原研究问题及来源约束，Root 不代写科学目标。 |
| `fig4_e55_hypothesis_portfolio_1.output` / `fig4_e55_hypothesis_critic_1.output` | 原件可作背景；必要可信输入由 `science.hypothesis.propose.v1` 和其精确边 `science.hypothesis.criticize.v1` 基于新 foundation 建立。 |
| `fig4_e55_reference_bundle_2` | 旧 bundle 不作为新的 Transform/Approval 合格来源。已注册 `scidiscovery.curve-bundle.figure-evidence.v2` 可绑定新 intake、精确 audit、原 PDF 及完整新 figure family，建立新 bundle。 |
| `fig4_e55_sprocess_capability_1` / `fig4_s5_execution_context_1` | capability 是 active_adapter 冻结快照，没有 compiled producer 标签；仍需对照实际执行适配器重新确认可接纳性，不能据此宣布 solver 当前可用。旧 execution_context 有旧 producer 身份；可通过 `tcad.execution-context.project.v1` 从合格 capability 重新投影。需要新 capability 时使用现有受控绑定入口。 |
| `fig4_e55_experiment_plan_revision_5.output` / `fig4_r4_tcad_author_1.output` | 分别 90,853 / 86,262 字节，适合新设计端口的原件限制。可作为明确绑定的历史 current_progress，不能作为新版计划、review subject 或执行资格。原 blocked/拒绝历史不改写。 |
| 新计划、曲线合同、项目、审查、执行批准 | 按新的实际当前目标建立，原审查/批准不继承。当前任务是否需要额外设备参数由科学设计和独立审查判断；尚未覆盖的研究目标本身不构成程序自动阻断条件。 |

因此未发现“只有已退役产物、没有可接纳原件或已注册建立能力”的发布前死路。这只证明目录和来源层面有建立路径；新 ABI 的真实精确 preflight、科学审查及人类批准仍是 P5 后续门槛。不得把本表当成固定科研阶段图或授权令牌。

## 沿用现有配置的部署命令

在用户终端以当前服务用户 da 执行；包装脚本会自行调用 sudo。无需重复导出服务用户/组，也不另设 TCAD 状态目录。当前 TCAD 使用已有外部 command adapter，预演只生成 control 与 approval-ui 两个服务。

```bash
SCID_WORKSPACE=/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/workspace/ingaas_inalas_photodetector \
SCID_CODEX_LAUNCH_ROOT=/home/da/project/ai4s/tcad/git_release/scidiscovery-agent \
SCID_PYTHON=/home/da/miniconda3/bin/python \
SCID_PLUGINS=tcad_artifact,curve_score,curve_figure_evidence \
SCID_INSTALL_ROOT=/opt/scidiscovery-m7 \
SCID_STATE_ROOT=/var/lib/scidiscovery-m7 \
SCID_CONFIG_ROOT=/etc/scidiscovery-m7 \
SCID_TCAD_COMMAND_CONFIG=/etc/scidiscovery/command-adapter.json \
/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2/deploy/reinstall.sh reinstall
```

本命令沿用已核实的 m7 安装、状态、配置目录，以及原工作区、启动目录和 command adapter 路径；备份仍使用现有 `/var/backups/scidiscovery`。安装脚本负责原事务快照、失败回退和配置重建，不手改数据库、审批或历史 Run。

本会话仅能写项目目录和 /tmp；安装涉及 /opt、/etc、/var/lib、/var/backups，无法在此会话代为完成。不是独立审查拒绝，也没有发起系统写入后伪报成功。

## 安装后的受控继续

1. 保存安装输出及事务目录，重启 Codex 加载新配置；明确继续 M7-test0。若新会话未绑定，只使用 instance_current 返回的实例管理页面选择已有实例。
2. 核对运行身份、生成 profile、49 项目录和 ABI 17 候选摘要；重新查询实际输入端口及 review edge，核对旧合同 Run 的退役结果。
3. 对确切来源和必要资格逐项使用新目录 preflight；成功后才用同一不可变请求 invoke。需要 Agent 时，仅派发控制返回的 agent_type，禁用父聊天继承。资格和执行批准均交现有精确 UI。
4. 选取必要旧原件作为可读背景，保留其旧资格状态；完成新必要资格后，让设计 Agent 判断本轮目标、遗漏影响与后续条件。所有科学判断以 completed Run 的 sealed_output 与 scheduler_signal 为准。
5. 按审定计划 P6 留下真实设计、author、独立审查、授权执行输出和分析；再在新会话完成第二轮设计与实际实验输出。工程 PASS 和此部署交接均不证明两轮推进已完成。

本交接只登记部署准备和恢复入口，不新增实施范围、Operation、服务、阶段对象或领域判断。

