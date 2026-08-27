# TCAD 科学研究 Agent 第二轮复审报告

> 复审日期：2026-08-08
> 复审对象：当前源码、未提交修复、实际 InGaAs/InAlAs 研究 workspace 及其活动研究 Bundle
> 复审目的：校准首轮审计的严苛程度，核销已有改进，并识别当前仍可复现的 Bug

## 1. 结论先行

首轮报告的总体方向没有错，但有三处表述过于绝对：

1. 项目并非“没有真实 TCAD 证据”。本地研究 workspace 包含真实 Sentaurus SProcess/SDevice 历史工作、TDR/PLX/PLT、日志和 511 条运行记录；最新活动 Bundle 也能离线校验。
2. 项目并非“完全没有跨对象一致性”。当前已有确定性的候选资格汇合、精确 deck/review 父关系、执行审批绑定和知识更新 reducer。
3. 项目并非“所有科学闭环均不可达”。特化的 InGaAs Fig.4 基线溯源路径已经用真实 SProcess 和冻结 scorer 跑通；尚未闭合的是通用的新机理、多执行单元和 SDevice 链路。

因此，当前更准确的评价是：

> **这是一个已经具备真实项目级科学实践、且控制平面基础较强的 TCAD 研究 Agent；但通用产品接口仍落后于该项目依靠脚本和专用插件实现的研究能力。**

首轮把它称为“控制平面原型”偏保守；但若称为“通用、生产级、可自动完成任意 Sentaurus 科学闭环”，仍然超出了现有证据。

## 2. 本轮实际验证

| 验证项 | 结果 |
| --- | --- |
| 全量测试 `pytest -q` | `283 passed in 34.85s` |
| 新增部署测试 | `11 passed` |
| `research_state validate` | 通过，511 条运行记录 |
| InGaAs 活动 Bundle 离线校验 | 通过，16 个对象，Bundle SHA-256 为 `684d106d...18e3` |
| 使用当前 Conda Python 的部署预检 | 通过 |
| 三个本地包的离线构建和导入 | 通过，9 个角色、2 个领域 transform adapter |
| Bash 语法检查 | 通过 |
| `git diff --check` | 通过 |
| `MANIFEST.sha256` | 未通过，8 个已修改文件摘要过期，新脚本尚未纳入清单 |

真实 SProcess 日志明确记录：

- `Sentaurus Process Version R-2020.09`；
- deck syntax check 完成；
- 223 个 diffusion steps；
- PLX 91,063 bytes；
- TDR 1,049,554 bytes；
- solver exit code 为 0；
- 冻结 scorer 在 `baseline_recovery` 门失败，并停止后续物理归因，没有接受模型。

这说明该项目确实具备真实执行和“失败即停止”的科学实践。首轮关于“没有真实 SProcess 证据”的判断应撤回。

## 3. 对首轮结论的重新分级

| 首轮结论 | 复审判断 | 新严重度 |
| --- | --- | --- |
| 多案例实验与单工程执行完全冲突 | 表述过重。历史 baseline + 单个新 run 可以合法工作；两个都需新仿真的案例仍缺执行单元映射 | 高，非全局阻塞 |
| 典型 SDevice 无法打包 | 结论成立；文本 `DeckFile` 无法携带 TDR，实际 SDevice deck 普遍引用二进制 Grid | 高 |
| 默认科学闭环不可达 | 过于宽泛。Fig.4 特化路径可达；通用新机理路径仍缺控制等价 transform 和完整 scorer | 高 |
| TCAD 验证低于自身契约 | 对通用 adapter 成立；对 Fig.4 专用 scorer 过于严苛，后者已有 PLX、非有限值、网格和冻结指标检查 | 中到高，按 lane 分级 |
| 跨对象一致性未接入生产 | 部分失实。候选资格和 reviewed package 已有确定性约束；case→执行及新旧 schema 仍未完全统一 | 中 |
| 单位系统可能静默出错 | 完全成立，并已通过反例复现 | 高 |
| 同 UID 服务是高危漏洞 | 对单用户可信 WSL 场景过严；它是明确的信任边界限制，不是当前已证实的远程漏洞 | 中/加固项 |
| 可复现性元数据不足 | 部分改善：活动 Bundle、内容哈希、冻结 scorer、真实 log 均有效；LLM 与 solver binary provenance 仍不足 | 中 |
| 没有真实 TCAD 测试证据 | 错误。workspace 有真实证据；但这些证据不在公开 CI 中，且新控制面尚无真实 SDevice qualification | 中 |
| 大文件影响可维护性 | 观察成立，但不应与功能阻塞同级 | 中/技术债 |

## 4. 当前仍存在的高优先级 Bug

### 4.1 本地执行 adapter 可绕过独立 deck review（P0）

设计文档声称 `ReviewedDeckPackage` 是唯一生产执行路径，但本地 [execution_adapter.py](../plugins/tcad_artifact/tcad_artifact/execution_adapter.py#L23) 同时接受：

- `tcad.reviewed-deck-package.v1`；
- 裸 `tcad.job-spec.v1`。

当 profile 为 `tcad.job-spec.v1` 时，adapter 直接返回 payload，不验证 `DeckProjectDraft`、`DeckReviewReport` 或二者的精确父关系。根控制面会接受 adapter 声明支持的 profile，见 [execution_bridge.py](../src/scidiscovery/artifact_agent/execution_bridge.py#L66)。端到端 shell 测试也在使用裸 JobSpec 路径。

外部 command adapter 已正确只接受 reviewed package，因此两个执行后端的安全语义不一致。若本地 policy 后续配置成真实 `sprocess`/`sdevice`，Root 可以在有人批准一个裸 JSON 后绕过独立代码审查。

建议：

- 从生产 `TCADExecutorAdapter` 删除 `tcad.job-spec.v1`；
- 如测试确需裸 JobSpec，建立只在测试装配中使用的 fixture adapter；
- 在 `execution_request_create` 再校验 payload kind/schema，不能只信 adapter 的 profile predicate。

### 4.2 profile 名称猜测无法证明真实求解器语义（P0）

[project_packager.py](../plugins/tcad_artifact/tcad_artifact/project_packager.py#L50) 通过 profile ID 是否包含 `sprocess`/`sdevice` 推断求解器类型；实际 executable 直到 [execution_control.py](../plugins/tcad_artifact/tcad_artifact/execution_control.py#L225) 才由 policy 映射。

复审反例：

```text
DeckProjectDraft(tool_profile="production_2020", entrypoint="run.sh")  -> 接受
ToolProfile(profile_id="production_2020", executable="/opt/synopsys/sprocess") -> 接受
```

最终命令会把 shell 文件交给 `sprocess`，但 deck reviewer 无法从项目对象中得知这一点。

另一个反例是 `sprocess child.cmd`：生产 `DeckProjectDraft` 接受，独立 skill 验证器以 `entrypoint.nested_solver` 拒绝。这证明指导规则与生产准入规则仍然分叉。

建议在管理员 capability 中增加不可变 `solver_kind` 枚举和 capability digest，并让 reviewer/packager 针对 exact capability 审核。生产验证器应直接复用 skill 中的纯验证函数或共同规则库。

### 4.3 通用控制等价性仍只有库函数，没有生产 transform（P0）

`evaluate_control_equivalence()` 的实现能够发现冻结变量漂移和未声明差异，见 [comparison.py](../src/scidiscovery/artifact_agent/schema/comparison.py#L96)。但全仓库调用点只有测试；已注册 transform adapter 中没有 `control-equivalence` profile，也没有从 reviewed case 工程生成 `RealizationSnapshot` 的生产路径。

调度器却把 `control_equivalence_report` 作为通用诊断前置条件，见 [scheduler_topology.py](../src/scidiscovery/scheduler_topology.py#L219)。因此：

- Fig.4 专用 scorer 路径可以自行实现等价性约束；
- 通用 `new_mechanism` 路径仍无法仅依赖公开 MCP/transform 生成该报告。

建议新增纯 transform：`ExperimentPortfolio + per-case RealizationSnapshot -> ControlEquivalenceReport`，并强制 snapshot 精确父绑定到对应 reviewed project/execution。

### 4.4 `layered_diagnosis` 通过后 readiness 仍不接受 claim（P0）

知识更新 transform 已支持 `validation_report` 或 `layered_diagnosis`，这是本轮应肯定的改进。但 [mcp_root.py](../src/scidiscovery/artifact_agent/interfaces/mcp_root.py#L516) 的 claim readiness 仍只读取 `validation_report`。

复审构造了一份 schema 合法、六层 gate 全部通过、`claim_allowed=true` 的 `layered_diagnosis`。实际结果为：

```text
layered_claim_allowed = True
readiness_claim_evaluability = not_evaluable
available_artifacts = [layered_diagnosis]
```

这会让新诊断模型完成后，Root 仍认为 claim 不可评估。应统一 claim 投影逻辑，并明确多个报告或多个 revision 时的选择规则。

### 4.5 科学多案例没有对应的类型化执行计划（P0/P1）

首轮把这一点判成全局阻塞过重，因为 baseline 可以是已经冻结的历史结果，不一定需要再次执行。但对于 baseline 和 candidate 都需要新仿真的研究，问题仍存在：

- 科学 `ExperimentPortfolio` 要求比较案例；
- `tcad_deck_author` 只返回一个 `DeckProjectDraft`；
- 一个 draft 只有一个 profile、entrypoint 和 argv；
- direct-solver 契约要求独立案例拆分为独立执行单元。

当前角色提示要求“一个 project 实现完整 comparison contract”，但对两个独立 solver invocation 而言，这个要求在数据模型中不可表达。

建议引入较小的 `StudyExecutionPlan`，而不是扩大 `DeckProjectDraft`：每个 case 绑定零个或一个新执行单元；历史案例绑定冻结结果；新执行单元以 DAG 表达依赖。

### 4.6 当前通用工程模型仍无法承载 SDevice TDR 输入（P0/P1）

[DeckFile](../plugins/tcad_artifact/tcad_artifact/project_packager.py#L59) 只有 UTF-8 `content`。实际 workspace 的 `sentaurus/sdevice_dark.cmd` 在第 2 行引用 `build/sentaurus/ingaas_sample2.tdr`，其他大量 SDevice deck 也引用 TDR。

因此，研究 workspace 中已经存在真实 SDevice 实践，不等于新控制面可以重新打包这些案例。当前 reviewed-package 路径仍缺少：

- 内容寻址二进制输入；
- 上游 execution output 到下游 input 的类型化绑定；
- TDR 的 region/material/contact 元数据验证；
- SProcess → SDevice DAG。

这应被描述为“通用 SDevice 产品能力缺失”，而不是“项目没有 SDevice 研究能力”。

## 5. 数值与科学验证 Bug

### 5.1 单位字符串参与展示，但不参与计算（P0）

[validation.py](../src/scidiscovery/artifact_agent/schema/validation.py#L336) 调用 `evaluate_threshold` 时只传 observed 数值和 threshold，没有传报告单位。

已复现：

```text
observed = 1000 mV
threshold = >= 2 V
当前结果 = True
物理结果 = False
```

这既可能产生假阳性，也可能产生假阴性。不能只增加字符串相等检查，因为 `1000 mV` 与 `1 V` 应当等价。建议引入规范单位、量纲和显式换算；无法转换时 fail closed。

### 5.2 通用 runtime assertion 只验证输出存在（P1）

[attest_runtime_contract](../plugins/tcad_artifact/tcad_artifact/project_packager.py#L791) 对路径、媒体类型、大小和 required output 做了可靠检查，也诚实地把 scope 标为 `execution_contract_only`。但 `runtime_assertions` 的实现仍只是检查所指 output name 是否出现，并未执行断言描述中的内容条件。

因此首轮将其称为“没有科学验证”过重；更准确的说法是：

- Fig.4 插件已有专用 PLX parser 和冻结 scorer；
- 通用 adapter 没有 log、PLT、TDR、收敛、KCL 或 bias-point parser；
- `description` 目前只是说明文字，不是可执行 assertion。

### 5.3 研究报告混淆 solver 输出与 transport 输出（P1）

最新 Fig.4 deck 的 `expected_outputs` 只有 PLX 和 TDR 两项；执行层另外生成 `tcad_log` 和 `tcad_manifest`。但报告和 `research/current.yaml` 写成“4 个 declared outputs 均已收集”。

这不会改变该次科学失败结论，但会混淆：

- solver-declared scientific outputs；
- transport-generated audit outputs。

建议分别记录 `solver_outputs_collected=2` 和 `transport_outputs_collected=2`。

## 6. 本轮源码/workspace 分离方案的评价

### 6.1 方案方向正确

以下改动是有效修复：

- 源码根与 5.2 GB 研究 workspace 分离；
- 安装器从 `SOURCE_ROOT` 构建代码，从 `WORKSPACE` 读取项目状态；
- 新增项目初始化脚本和 InGaAs 安装 wrapper；
- 正式安装前先验证源码、Python 依赖和本地 package build；
- 离线 `--no-index --no-deps --no-build-isolation` 构建在当前环境实测通过。

这解决了源代码交付与研究数据生命周期混在一起的问题，也避免把大体量仿真结果误打入软件包。

### 6.2 package “构建”阶段已经提前激活新版本（P0/P1）

`install_all()` 在停止旧服务前调用 `install_packages()`，见 [install.sh](../deploy/install.sh#L605)。但 `install_packages()` 不只构建到临时目录，还立即把旧 `SITE_ROOT` 移走、把新 stage 改名为正式 `SITE_ROOT`，见 [install.sh](../deploy/install.sh#L303)。

这意味着旧服务仍运行时，磁盘上的 Python 包已切换为新版本。延迟 import、角色文件读取或进程重启可能出现新旧混合状态；后续步骤失败时也没有完整回滚。

建议拆成：

1. `build_and_probe(stage)`；
2. `retire_old_deployment()`；
3. `activate_stage_atomically()`；
4. 失败时恢复 previous site 和旧 units。

### 6.3 运行时依赖绑定到可变 base Python（P1）

新安装器只把本项目包复制到 `/opt/scidiscovery/site`，Pydantic、PyYAML 等来自所选 Conda/system Python。这样避免了联网解析，但部署不再是自包含环境：base 环境被升级、删除或切换后，systemd 服务会漂移或失效。

另外，依赖版本检查使用正则提取数字，不符合完整 PEP 440 语义；rc/dev/local 版本可能误判。

建议使用带锁文件的 venv/离线 wheelhouse，或至少记录 base interpreter、所有 distribution 版本和哈希，并使用 `packaging.version.Version` 比较版本。

### 6.4 workspace 路径未做 systemd/脚本安全规范化（P1）

安装器允许任意绝对目录。带空格的 workspace 实测 `--dry-run` 通过，但 systemd 模板中的 `ExecStart` 把 `@PROJECT_ROOT@` 直接放在未转义参数位置，正式服务会把路径拆成多个 argv。

同类风险还包括引号、百分号和换行，以及 heredoc 中直接插入路径。建议：

- 对可配置路径限定安全字符，或进行正确的 systemd specifier/argv escaping；
- dry-run 必须对实际渲染 unit 执行与正式安装相同的 `systemd-analyze verify`；
- Python heredoc 改为通过 argv 传值，不做源码插值。

### 6.5 workspace 初始化权限过宽且会跟随既有链接（P1/P2）

`init_workspace.sh` 在默认 `umask 022` 下创建的项目、`inputs/papers` 和 `config` 均为 `0755`。在多用户 Linux 主机上，论文、研究参数和配置可能被其他本地用户读取。

脚本也没有拒绝已经存在的 project root 或其子路径符号链接。建议设置 `umask 027` 或显式 `0750/0700`，拒绝 symlink，并区分“创建新项目”和“确认已有项目”两种行为。

### 6.6 当前 release manifest 未更新（交付阻塞）

本节记录的是该轮审计时的历史状态：当时 `sha256sum -c MANIFEST.sha256`
有 8 项失败，workspace 和项目安装入口也尚未进入 manifest。该项后来已经修复；
当前通用入口为 `deploy/reinstall.sh`，InGaAs/Fig.4 差异由
`deploy/apply_ingaas_fig4_profile.sh` 提供，发布前会重新生成并校验 manifest。

## 7. 安全结论的校准

首轮把“所有服务同 UID”直接列为高危，缺少威胁模型说明。当前部署明显面向单用户、本地 WSL/研究工作站；在这个前提下，共享 UID 更像是可信用户内部的职责分层，而非多租户安全隔离。

但必须明确：

- socket mode、随机 proxy ID 和隐藏控制元数据不是对同 UID 恶意进程的认证；
- daemon 不检查 `SO_PEERCRED`；
- worker、approval、control 和 local executor 使用同一用户；
- 因此系统不能宣称能抵御本地同用户恶意代码或被攻陷 worker。

建议将当前边界写入 SECURITY 文档。只有在目标变为多用户服务或不可信模型执行时，才把 OS 用户拆分、peer credential 和独立密钥升级为 P0。

Web fetch 的 DNS 预检与 `urllib` 实际连接之间仍有二次解析窗口，存在 DNS rebinding/TOCTOU 风险；如果公开给不可信 URL 输入，建议固定已验证 IP 建连并保留 TLS hostname 校验。

## 8. 推荐修复顺序

### P0：先关闭可绕过或会产生错误科学结论的路径

1. 禁止生产 local adapter 接受裸 `tcad.job-spec.v1`。
2. 用 exact capability 的 `solver_kind` 取代 profile 名称猜测，并统一 skill/生产验证规则。
3. 修复 `layered_diagnosis` claim readiness。
4. 把控制等价性注册为生产 transform，并建立 per-case realization parentage。
5. 为 threshold 和指标实现量纲与单位换算。

### P1：补齐通用 TCAD 和部署可靠性

1. 引入 case-aware `StudyExecutionPlan`、二进制输入和 SProcess → SDevice DAG。
2. 增加通用 log/PLX/PLT/TDR parser 和可执行 runtime assertions。
3. 将安装流程拆分为 build、retire、activate、rollback。
4. 固定第三方依赖环境；校验 service user 对 Python、workspace 和配置的真实访问权限。
5. 修复 systemd 路径转义和 workspace 权限。

### P2：交付与维护

1. 更新 release manifest，并把新部署脚本纳入 release builder 测试。
2. 增加真实 SProcess/SDevice 内部 qualification lane；公开 CI 保留无许可证 fixture。
3. 清理旧 schema helper，避免 `HypothesisPortfolio/ScientificReview` 与新角色模型长期并存。
4. 将测试数量和能力清单自动生成，减少文档漂移。

## 9. 最终判断

首轮结论需要从“项目尚未形成真实 TCAD 科学闭环”修正为：

> **项目已经在 InGaAs Fig.4 的限定路径上形成了真实、可审计、会失败关闭的 SProcess 科学闭环；但该能力依赖项目专用 scorer、历史 workspace 和外部 transport，尚未完整上升为通用 TCAD 产品能力。**

本轮源码/workspace 分离是正确改进，但主要解决部署和数据边界，没有直接修复首轮指出的 case 执行建模、SDevice 二进制输入、单位系统和通用结果验证问题。现在最值得优先处理的不是继续增加角色，而是关闭裸 JobSpec 绕过、绑定 exact solver capability、接通 control-equivalence transform，并修复 layered diagnosis readiness。
