# 独立工程可靠性与通用性评审

日期：2026-10-15。仓库：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`。
HEAD：`f912f3e0820e7eea76cb34b391901a1072699c1b`；R6 受测源码为 `85ca78ce26c92d260eea40ac52943b3655f17614`，证据提交 `dc4193e`。本评审不把 R6 PASS 当作全框架、真实模型或科学效果通过。

独立性：本评审未参与该修复；工程结论独立形成，未以前一个评审或科学评审的结论为前提。只读仓库；仅在 /tmp 保存复现与报告。未提交、push、调用收费模型、启动真实研究场、solver 或访问秘密内容。工作树原有未跟踪证据目录未改动。

遵循仓库 AGENTS 和外层 `scid-cross-boundary-review`、`scid-change-scope-checks`。范围不只本轮 diff：检查 CLI prepare/run/status/pause/continue/closeout、H/W/A/E 路由、native runner/watchdog、usage、managed execution registration/admission、local/cov 能力、交接与历史、收口与旧 daemon/UI/TCAD 接缝。未做全库语义穷举。

## 1. 已证实缺陷

### B1 — P2：自定义透传 launcher 在未启用 role_profiles 时丢失全局 service_tier

定位：`src/scidiscovery/research_loop/native.py:147-161`，尤其 160 行的 `elif settings.get('role_profiles') is not None`。

条件：prepare 使用自定义 launcher（例如 `[python, wrapper.py]`，wrapper 按约定接收/透传 Codex exec argv），设置 `service_tier='priority'`，不传 role_profiles。model 与 reasoning_effort 总会进入实际 argv；service_tier 只在标准单项 codex 或启用 role_profiles 时进入 argv。

证据：无模型真实 runner 运行后，settings 中为 priority，而接收方实际 `-c` 仅有 `model_reasoning_effort="high"`。H 正常完成并封存为 wait，没有配置缺失诊断。该行为不能证明服务器实际用了哪个档位；它证明用户请求未被控制层传给普通自定义透传 launcher。提供自有冻结配置并核对的专用 cov launcher 可自行补偿，不能据此认定所有 custom launcher 均受影响。

影响：对以 argv 为配置来源的 wrapper，用户请求的档位可能被继承配置/default 取代；记录的配置与真正提交的参数不一致，影响延迟、费用预期和复现。

最小复现与原件：`/tmp/scid-eng-gap-probe-20261015.py`；`/tmp/scid-eng-gap-probe-20261015/result.json`。资源监督：`/tmp/scid-eng-gap-resource-20261015/resource.json`，启动器：`/tmp/scid-eng-gap-supervise-20261015.py`。正常结果为 wait；declared_service_tier=priority；actual_config_args 中无 service_tier。

建议：对所有 launcher 统一传递已冻结的 tier，或对 launcher 声明显式协商且拒绝无法传递的配置。补一个“不传 role_profiles + 全局非默认 tier + custom wrapper”的真实 argv 回归；已有 role profile 测试不能覆盖该组合。不要用复制继承配置来替代参数一致性。

未发现已证实 P0/P1。

## 2. 已证实工程边界与明确设计局限

### G1 — 高优先级：两套产品入口仍具有不同能力与治理语义

`docs/ROOTLESS_CLI.zh-CN.md:3-4` 明确旧 daemon、UI、TCAD 权限接口尚未迁移。新 CLI 的 root 是文件实例；旧 `scid`/MCP 走 ResearchInstance、Artifact、审批页和执行策略。`pyproject.toml:27-40` 同时发布两组入口/注册。

`native.py:137-141` 默认本地 W 硬选 `local_execution:command`；custom launcher 默认 external，由 launcher 配置；CLI prepare 没有通用 executor 配置选择。`plugins/tcad_artifact/pyproject.toml` 注册旧 scientific plugins/TCAD daemon，没有新的 execution_interfaces entry point。故“装了 TCAD 插件”不等于 rootless CLI 获得已审查 TCAD 权限链。旧 UI 不负责展示 rootless 节点、预算、unknown 和交付。

影响：新用户不能从一个明确入口得到统一的功能清单、权限状态与诊断；迁移/误配成本高。README Quick Start 仍引导旧 daemon/UI 流，未把 ROOTLESS_CLI 放进主入口说明。

建议：先公布并维护单一支持矩阵与入口选择；为准备实例显示冻结的执行实现、能力、隔离要求、审计/交付是否可用。完成 TCAD 适配或清晰保持 unsupported，不用“注册可扩展”代替生产适配证据。

### G2 — 高优先级：unknown 与系统重启目前是人工恢复断点

`runtime.py:102-119`、`native.py:100-118` 对失去原 runner 身份的执行保留 unknown、不重放。`experiments.py:418-421` 对原有 unknown/running 调用拒绝新接受；`local_experiments.py:313-315` 取消明确不支持，生命周期声明 36-37 行也不授予 cancel/resume。

`budget.py:28-29` 在 boot_id 改变时拒绝消费区间；status 最后需要 snapshot，故系统重启后甚至常规状态读取也会失败。文档已诚实声明须人工修复；没有看到面向操作者、具审计的 rootless reconciliation/boot recovery 命令。

影响：断电/主机重启、runner 失联或提交答复丢失后，保守停止正确，但长期无人值守研究无法自行回到可推进状态；操作者可能被迫直接改原件，破坏原始身份或计量。

建议：增加只读诊断及精确原调用 reconcile 工作流，保留未知范围，不重发或退款；提供跨 boot 的审计终结/恢复程序。把“frontend kill 后同 boot 重连”与“host reboot 后恢复”分开验收。

### G3 — 高优先级：证据快照不足以复现完整科学运行环境

新 CLI 冻结 objective/updates 与节点交接；`controller.py:123-124` 仅存 public_root 路径，`contracts.py:412` 将路径交给角色，没有全局 public 文件清单/哈希。`local_experiments.py:70-84` 只快照所选实验目录；解释器、库、外部导入、绝对 argv 指向文件及环境不在该输入快照内。`docs/ROOTLESS_CLI.zh-CN.md:51-58` 已明确环境/外部依赖不保证复现。

影响：同一 sealed conclusion 可依赖发生变化的公开数据或科学库；当前证据能证明保留的字节与收到的执行结果，不能证明执行完全使用已快照输入，也不能从原件重建完整环境。这是范围不足，不是软隔离漏洞。

建议：支持操作者显式声明科学原件/数据集/运行环境版本，冻结有界清单和环境指纹；区分“指定输入已保留”“实际读取未经观察”“完整环境未保留”。不要扫描全盘猜依赖，也不要求所有临时分析均受管。

### G4 — 高优先级：模型传输与成果目录缺少整体验证资源边界

`native.py:303` 将 stderr 直接接到文件；339-343 行持续写 native.jsonl，仅 pending 单行超过64MiB时停止。没有 stdout 总字节、stderr 总字节、实例磁盘占用或速率上限。复现中同一正常节点保留 stdout=3,189,128 B、stderr=2,097,152 B，并正常封存；受控测试没有制造填盘。这里不声称违反既有“256000B”上限：该文档上限只适用于受管本地实验日志，后者在 local_experiments.py 中确实单独计数。

`contracts.py:454-517` 采集原生 artifacts/ 与嵌套 experiments，只限制单件/总内容字节；没有文件数、目录项数、路径长度、遍历耗时或封装元数据总量限制。大量空文件不消耗 byte ceiling，却扩大 materials、seal、下一节点拷贝与索引。受管 local files() 有1024扫描项/128文件限制，普通 native 成果采集没有等价保护。

影响：即使节点时间/token 有限，工具输出与大量小文件仍能耗尽磁盘、内存或让封存长时间阻塞；不是已观测填盘或OOM，也不是 cgroup 隔离承诺。

建议：先对自有传输与采集增加总量止损、计数/元数据/时间界限和明确 omitted/unavailable；保留终态与诊断，不静默截断为完整结果。将资源监督测试中的限制与产品 runner 限制分开写清楚。

### G5 — 中高优先级：本地通用实验到候选、审计与最终交付仍有能力落差

`local_experiments.py:206-236` 保留 command outcome/metrics/outputs；candidate_id=None。`docs/ROOTLESS_CLI.zh-CN.md:68-76` 明确本地结果不生成候选、不参与排名、不产生 cov 审计资格/外部确认。没有 adapter 时 export-only 是现有成果引用/保留与限制状态，不等于独立交付包或外部成功。

新的 execution registration 具有可组合的 managed interface；但 audit/delivery/observer 仍为额外 operator adapter，cov 是当前完整专用实现。第三方没有 smoke 时 shortlist 把 not_provided 当中性、没有 audit 时不伪造审计，这一点代码语义正确。它不能被解读成通用 local 已达到 cov 的可选择、可审计、可交付能力。

建议：给通用科学结果定义可选候选对象/目标口径和能力发现，不硬编码所有 domain 规则；提供独立于 cov 的小型真实示例插件。对 export 提供完整性说明和可携带包需求的单独契约。

## 3. 当前支持矩阵（源码判断；证据强度分列）

| 能力 | 标准单项 Codex + 默认 local | 自定义 launcher + external/cov | 旧 MCP/daemon + TCAD | 当前证据/限制 |
|---|---|---|---|---|
| H/W/A/E 科学路由与封存 | 有 | 有；launcher须遵守argv/输出协议 | 有旧 Operations/Worker体系 | 本评审静态追链；R6只有无模型夹具，不认证科学效果 |
| 受管输入/输出本地快照、指标 | local W有；需用scid-experiment | 取决于launcher配置；cov有独立receipt | 有domain Artifact/执行收集链 | local只快照指定目录；环境不完整 |
| 自由shell临时计算 | 有，软权限 | 原生权限由launcher负责 | Worker原声明权限 | shell不自动成为managed证据 |
| 通用候选排名 | 无自动候选 | observer/cov支持显式候选与口径 | 由domain插件负责 | 不能把最高代理指标当全局最优 |
| 可选smoke缺失 | 无local候选链 | 中性not_provided；原件缺失仍排除 | domain-specific | 已读shortlist实现；R6有fixture，不是任意第三方生产资格 |
| 候选audit/交付确认 | 需专门adapter；默认无 | cov专用隔离adapter有 | 旧审查/执行策略有 | 各适配器能力不同，不互相继承 |
| 查询/lookup/collect | local已声明 | cov已声明，第三方须声明 | 旧执行接口有 | 原调用查回，不表示重试许可 |
| local取消/原调用resume | 未声明 | cov继承local未声明；其他实现须声明 | TCAD另有cancel/recovery接口 | 不因CLI有cancel命令就称所有driver支持 |
| frontend退出后的同boot重连 | 有durable runner | 有，但外部launcher负责其额外后代 | 有独立daemon协议 | 已有R6定向无模型证据；本评审未重跑 |
| 系统重启后的active计时恢复 | 人工修复 | 同左 | 另一体系；本评审未重新资格化 | rootless boot不匹配拒绝snapshot |
| 同线程Worker有限续接 | 需显式合格launcher/resume/node策略；非默认 | 合格custom launcher可用 | 旧Worker恢复体系不同 | 不保证任意raw launcher的认证/配置自动适配 |
| 状态UI/审批页统一rootless状态 | 无 | 无 | 有旧UI | 文档明确尚未迁移 |
| 配置model/effort/tier | 标准单项codex传递 | profile开启时传递；无profile全局tier有B1 | 独立配置体系 | 本评审仅证明argv，不证明服务器档位或计费 |

## 4. 最影响实际用户运行的前五项（行动顺序）

1. 修复 B1 并明确唯一推荐入口/支持矩阵：避免设置已记录但未提交，以及把旧 TCAD/UI 能力套到新 CLI。
2. 建立 audited unknown/boot recovery：现有保守不重发正确；缺的是不用手改原件的后续操作路径。
3. 为 native 日志、成果文件/目录项与封装总量补边界：产品长期运行的止损尚不完整。
4. 显式绑定公开科学数据与运行环境依赖：避免把局部字节封存误当整个实验可复现。
5. 补通用 local 候选/交付示例与端到端资格：目前 cov 能力不能推广为所有科学问题/插件可用。

该排序针对工程可靠性/可操作性；科学收益、搜索效率和证据判断由另一独立评审负责。

## 5. 验证、盲点与可作出的结论

运行：唯一无模型自建复现通过 `scripts.run_tests.serial_lock + run_one` 执行，保留 resource.json。0.901s；returncode=0；stop_reason=exited；cleanup_complete=true；observed_tree_rss_high_water_bytes=103,628,800；无资源止损触发。`git diff --check` 通过。没有为了重复现有PASS而重跑全套。

读取：R6 JSON/文档、README/ROOTLESS文档、pyproject插件声明、native/runtime/budget/contracts/controller/experiments/local/cov/lineage/history/continuation/worker_delivery与shortlist/delivery相关代码、已有生命周期与注册测试。现有R6已明确 default-local HWA fixture关闭search；selected fixtures不认证默认科学搜索的实际效果。

未验证：真实Codex配置/认证/模型服务档位；当前HEAD收费模型H/W/A/E运行；真实solver/许可证/SSH；实际浏览器与UI状态；跨系统reboot的人工修复；长时间磁盘/数十万文件stress；外部第三方插件安装/升级/禁用全矩阵；科学数值正确性、隐藏目标收益或成本优势。没有证明这些能力不存在，只有当前资格不足。

测试盲点建议：B1组合、native stdout/stderr整体验证边界、空文件与深目录采集、host reboot/reconcile、同一公开数据在H/W之间变化、缺失依赖/不同解释器、无cov的通用candidate交付、UI与CLI实例状态一致性。只应在对应产品能力被承诺后增加相应资格矩阵，不盲跑全库。

框架目前可称为“具有真实封存/路由/保守不重发和局部安装证据的工程原型”。尚不足以称为统一通用科研产品、任意插件可生产执行、硬隔离/精确账单、系统重启后无人值守恢复，或已证实提高科学效果的系统。

## 归档补充

原始复现结果另存为 [无模型复现结果](ROOTLESS_ENGINEERING_GAP_PROBE_20261015.json)。其中 token 为夹具输出，不代表真实模型用量；临时脚本路径保留为本次审查来源记录。
