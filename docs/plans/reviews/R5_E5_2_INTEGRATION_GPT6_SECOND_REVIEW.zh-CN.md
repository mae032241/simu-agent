# R5 E5.2：GPT-6 第二轮独立集成审查

日期：2026-09-05

结论：**PASS；剩余 blocker = 0。** P1—P4 生产差异保持既定边界；本轮补充证据足以关闭所提交的安装态与代际证据缺口，允许进入既有部署/真实验收门。此结论不代表部署、安装事务回退、真实 Fig.4 科学资格或 E5/E6 已通过。

## 1. 审查对象与发现分级

唯一审查仓库为 `/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`，分支 `refactor/m7-pre-e5.2`。范围为 `a6742b7..bca7b4952065fedd52eff5f6149bb2a69138e3ff` 加本轮未提交证据补充，包含 P1 `322d281`、P2 `c7c692a`、P3 `e2af10c`、P4 `036a544`。

已完整读取[修复计划](../R5_E5_2_FIGURE_QUANTITATIVE_AND_VALIDATION_CONTRACT_REPAIR_PLAN.zh-CN.md)与审查结束时的[集成报告](../evidence/R5_E5_2_INTEGRATION_REPORT.zh-CN.md)，并检查全部生产差异、对应测试、独立安装目录及临时状态。采用跨边界审查与最小检查技能；没有修改生产代码或测试，没有访问生产状态库。本文是本审查者唯一修改的仓库文件。

首轮 GPT-6 审查仅以协作消息返回，未形成本地审查文档；其结论来源为集成方转述。本文不将该转述冒充已读取的原始审查文件，以下判定依据本轮独立源码检查和执行结果。

| 等级 | 剩余数量 | 判定 |
|---|---:|---|
| blocker | 0 | 无阻断 E5.2 本轮集成目标的问题 |
| high | 0 | 未发现本轮引入的高风险实现缺陷 |
| medium | 0 | 既定安装证据缺口已由最终环境和补充负例关闭 |
| low | 0 | 本轮发现的环境、摘要和回退措辞均已作最小修正 |

## 2. P1—P4 边界与实现

| 补丁 | 核对结果 |
|---|---|
| P1 | 仅在已验证 coincident 分支传递既有 `shared_eligible=True`，CSV 仍逐成员应用 default、检测下限和排除区间。strict overdraw 复制行的禁止定量检查保留；来源颜色、共同坐标、单一真实来源、两侧锚点、成员贡献与距离检查仍存在。删除唯一 overdraw 猜测生成器及调用，没有改 tracker、normalizer 或 scorer。报告使用 validator v5，旧 2/3/4 读模型保留；请求 v2 的旧距离字段仅标明弃用并忽略。 |
| P2 | 适用性由 executor、输出 `evidence_paths`、非 collection 和可见 inventory 声明共同决定。prepare/submit 使用同一 `operation_port_json_schema`，submit 从冻结 Run 绑定重建。静态无绑定与已绑定零 inventory 分开处理；零绑定使用 `maxItems=0`。声明路径和本地引用先检查，再投影实际别名；正常 enum 拒绝与构造/执行程序故障仍分别进入 rejected/failed。选择性投影版本进入现有 digest，无适用输出时保持原 envelope，未增加 ABI 或全局代际字段。 |
| P2 参数消费者 | 清单 usage 改为 `prior_signal` 后，提取上下文仍包含它；资格 projector 改从 package 的有序 `parent_refs` 核对清单和来源。两项共享 projector 的 Approval version 均为 2。没有增加来源实体或在核心按参数端口名分流。 |
| P3 | 只修改通用与图审查的静态提示/资源，明确忠实性、充分性、pass/fail/unknown 边界。聚合器、独立审查边和资格策略未改变；测试中的人工构造审查结果只证明承载及后继准入，不证明真实 Worker 的科学判断。 |
| P4 | 只修改 `ObjectiveClosureRequirement` 原模型：模型级条件、字段级唯一性、默认类型分支均可见于 Schema。原默认值、字段形状和 Pydantic 防御保留，没有改成新判别模型或扩展全局验证器。 |

生产差异共 14 个既有 Python 文件，符合计划总预算；P1—P3 为其中 13 个。没有新增公共抽象、Operation、工具、注册面、表、Run 状态或生产文件。集成提交的复杂度上限调整对应现有文件中的计划内增量；未提交注释已准确说明 `operation_contract.py` 不属于 operations-package 行数指标。恢复的 oracle 文件没有改变变换实现，其摘要核对为 `bd8f548312cdf4eebcc4d3be9f261fb1640a94e9d0b42bf9b784c137706f6002`。

## 3. 安装来源与独立发行证据

本轮以源码目录外的解释器启动、模块路径、wheel 安装元数据及对应提交内容交叉核对，不能只凭环境名称判断安装来源。

| 环境 | 独立核对 |
|---|---|
| `/tmp/scid-e52-cross-install/old-env` | core 来自 P1 wheel；8 个受影响 core 文件与 `322d281` 逐字一致 |
| `/tmp/scid-e52-cross-install/new-env` | core 来自集成 wheel；8 个受影响 core 文件的 Python AST 与 HEAD 一致。仅 `catalog.py` 两行行尾空格被清理，其余内容一致 |
| `/tmp/scid-e52-p4-install/env-p3-isolated` | `include-system-site-packages=false`；P3 core/curve/figure/tcad 均安装于此环境，14 个受影响生产文件与 `e2af10c` 逐字一致，P4 未混入 |
| `/tmp/scid-e52-p4-install/env-p3`、`env-p4` | 分别安装 P3/P4 core wheel，模块均位于对应 venv；P4 的8个受影响 core 文件与 `036a544` 逐字一致 |

原 `env-p3-figure` 的图夹具在禁用用户站点的复跑中缺少间接导入的 TCAD 测试依赖；原环境允许宿主 site，故不能作为“完全独立依赖”的最终证明。集成方仅新建 `env-p3-isolated` 并安装相同 P3 wheel 和测试依赖，随后本审查者独立复跑成功。未为此修改生产或测试。

P3 独立图/参数用例使用 P3 提交中的测试文件；`PYTHONPATH` 只提供该快照的测试包根，不含其 `src` 或插件源目录。安装态 fixture 的 Root/Local Worker 路径与另外核对的真实 entry point/`compile_installed_catalog` 共同构成安装证据；不将其称为真实 Agent E2E。

P4 对照重现报告数值：同一缺失 `comparison_purposes` 的 `comparison_present` 对象在 P3 Schema 中错误数为 0、P4 为 1；合法对象两版均为 0，P4 `uniqueItems=true`。`science.objective.project.v1` 摘要从 `76029d1c…` 变为 `e72e1e0d…`，`science.object.review.v1` 保持 `844970da…`。这是独立安装和合同代际证据；实际安装事务回退仍待部署门。

## 4. 同一状态根的五种旧 Run

已完整检查 `tests/fixtures/e52_installed_generation_probe.py`，并用上述 old/new 两个真实 wheel 环境重新执行五个隔离分例。每例先让旧解释器 prepare 并退出，再由新解释器 verify 同一状态根；没有在一个进程中替换摘要冒充安装切换。

两个环境各自安装 core，但共享宿主第三方依赖。探针还在两代中一致将 audit 的 `max_attempts` 设为 2，以形成有效恢复草稿；这不改变两代之间的比较条件。`90c4ef01… → 5a34f3bb…` 是这个同形恢复夹具的摘要，不能称为默认目录 audit 摘要。P2 投影版本的独立因果证据另由源码态固定声明/资源的测试承担。

| 旧记录 | 实际结果 |
|---|---|
| queued | 当前 Worker 找不到 exact queued Run；旧摘要 Worker 身份被拒绝；直接 submit 拒绝 queued；正确 CAS 的显式失败命令因 contract changed 被拒绝 |
| running | 当前 Worker 不领取；截止前 submit 因 contract changed 拒绝；显式失败同样被拒绝 |
| expired running | submit 先因 deadline expired 拒绝；带 `timed_out=true` 的显式失败仍因 contract changed 被拒绝 |
| failed + draft | `recovery_available=false`；恢复 preflight 返回 `recovery_source_unavailable`，不创建恢复 Run，旧草稿保留 |
| completed | `sealed_output_status=contract_retired`；sealed output/scheduler signal 为空；幂等 submit 仅返回 completed，旧 Artifact 和 receipt 保留 |

五例均验证旧 `RunStatus` 相等并可独立新建当前摘要 queued Run。本审查者额外比较了旧 runs 数据库整行、旧工作区文件内容/权限和 Artifact 文件内容；全部不变，且每例最终恰有旧、新两个 Run。额外检查没有修改探针文件。复核状态保留在 `/tmp/e52-review-generation-wlfxn6s6`。

无关的 `science.object.review.v1` 在两套 wheel 均为 `844970daca34297a6845b4db1eaf87a3bc0182a3d115397af807171c4ba0e69d`。这个负控直接证明摘要不变；不把它扩大为全部无关 Operation 生命周期已重放，也不把新 Run 创建称为旧 Run 恢复。旧 queued/running 仍不能由新合同显式收口是计划接受的既有限制，不要求新增生命周期修复。

## 5. 参数负例与 Codex 投影

P3 参数两分例已覆盖有/无清单正例、错误清单、漏来源、增加来源、错误参数族及独立审查拒绝。为直接补足计划明确要求的“提取有清单，资格请求漏掉它”，本审查者在独立 P3 环境复用原夹具，仅在内存中观察原 Root 请求，并对临时测试状态额外调用正式 preflight/invoke：

- 漏清单：两入口均返回/抛出 `approval_projector_failed`；
- 替换为已有的不同 ref 清单：两入口同样拒绝；
- 两例前后 Approval 列表完全相同。

补充状态为 `/tmp/e52-review-parameter-missing-3x8vfc1x`；没有修改生产或测试文件，没有生成科学批准。

已解析 `/tmp/e52-p3-fig-profile-8w09c_qq/project/.codex/agents/op_science_evidence_extract_figure_v2_3fa52a70e967.toml`，并与该 profile 指向的已安装 P3 `compile_installed_catalog` 比较：完整 operation digest 为 `3fa52a70e967dcf2184c6d96a42e5f0b588749ddbe70a92752357b47dd2a3cde`；agent 名、唯一 Worker 服务器、操作编号、启动解释器及安装目录 `PYTHONPATH` 均吻合。工具集合与 **Local Worker 投影**一致，为 `worker_open_assignment`、`worker_heartbeat`、`worker_submit_result`、`worker_extract_pdf_text`。通用 Worker 声明包含由本地原生文件能力承接的工具，不能拿它直接替代 Local 投影作比较。

同环境中 validator v5、旧距离字段说明及 P3 图 Audit 新资源也已实际读取。profile 来自另一套安装相同 P3 wheel 的环境，报告已准确区分它与后补的 isolated 测试环境。配置文件验证不代表已重启用户 Codex 或部署服务。

## 6. 本轮执行、措辞修正与放行边界

全部检查串行，设置 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`、`MALLOC_ARENA_MAX=2`，未使用 xdist。

| 本审查者执行 | 结果 | 直接命令峰值 / 时长 |
|---|---|---|
| `git diff --check a6742b7` | PASS | — |
| 六个安装解释器的路径/entry point/P3→P4 Schema 与摘要检查 | PASS | 3.44 s |
| old/new wheel 五种状态探针及额外不可变性比较 | 5 例 PASS | 61,460 KiB / 4.50 s |
| isolated P3 `test_five_operation_figure_family_requires_exact_review` | 1 passed | 97,584 KiB / 2.98 s |
| isolated P3 `test_real_parameter_run_reaches_expansion_audit_and_qualification` | 2 passed | 94,476 KiB / 3.07 s |
| isolated P3 漏/换清单正式入口补充 | PASS | 92,048 KiB / 2.07 s |
| P3 Codex profile 与安装态 Local 投影 | PASS | 66,056 KiB / 0.64 s |

P3 两条 pytest 命令从 `/tmp` 启动，解释器为 `/tmp/scid-e52-p4-install/env-p3-isolated/bin/python`，使用 `-m pytest -c /dev/null -q <p3-source/tests/operations/对应文件::上述函数> --tb=short -x`，设置 `PYTHONNOUSERSITE=1` 和 `PYTHONPATH=/tmp/scid-e52-p4-install/p3-source`。其余临时探针使用 `-I` 并清除外部 `PYTHONPATH`。这些常驻内存数值是直接命令指标，不能替代 Codex 整棵进程树或 WSL 基线增量的系统级记录。

以下 low 级证据表述已在审查期间关闭：将两套 core venv 误称为完全不共享 site-packages；未说明恢复夹具的 `max_attempts=2`；以正向 Schema 安装对照宣称事务回退已验证；将不同 P3 测试/profile 环境写成同一目录。最小修正仅为独立依赖复跑及报告措辞，未扩展实现范围。

完整目录的 `58 passed`、`364 passed / 1 skipped / 10 failed` 及精确排除后的结果来源于集成报告，本审查者未重跑完整目录。已核对所指强化后端能力声明/准入路径及旧字段模型未在本轮改动，oracle 摘要亦匹配；没有证据把所列十项遗留失败归因为 E5.2 新行为。保持“完整目录未全绿”的记录即可，不能因此要求本轮开发强化后端、oracle 兼容层或改写 OperationSpec。

本次源码测试与安装探针分别回答局部规则、独立安装和真实状态切换问题，存在必要交叠，未发现必须删除才能满足复杂度边界的重复生产机制。临时检查和合成科学内容不能替代独立真实 Worker 审查。

因此，P1—P4 本轮工程集成判定 **PASS，剩余 blocker 0**。后续沿原计划验证安装事务、服务/Codex 切换、系统级内存门及真实 Fig.4 科学/人工资格；本文不追加强化后端、迁移器、全局生命周期、UI、哈希体系、监控产品或真实科学 E2E 实现要求。
