# P2c TCAD managed 接线实施记录

日期：2026-10-17。依据[独审通过的本节点设计](P2C_MANAGED_EXECUTION_DESIGN_20261017.zh-CN.md)、[已审 seam](../THIN_TCAD_MANAGED_SEAM_20261016.zh-CN.md)与[主计划](../THIN_CAPABILITY_MIGRATION_20261016.zh-CN.md)。P2b 前置为 `f365776`。生产与定向负控已冻结，已获[独立静态审查 PASS](P2C_MANAGED_EXECUTION_REVIEW_20261017.zh-CN.md)，待提交；只有静态证据，真实生产 blocked。

## 精确范围

- 新增 `plugins/tcad_artifact/tcad_artifact/managed_execution.py`。
- `plugins/tcad_artifact/tcad_artifact/runtime_plugin.py` 仅提共享 `build_adapter`，保留旧 control/local_worker 贡献。
- `plugins/tcad_artifact/pyproject.toml` 增 `tcad_execution = tcad_artifact.managed_execution:REGISTRATION`，binding 为 `tcad`。
- 经 root 及独审同意，`src/scidiscovery/research_loop/experiments.py` 仅两处：显式 unknown 且没有 completed（含链接检查）时 observation 返回 None；全部 known terminal 的新 call 准入均先要求 verified observation，缺证据保持原 call unknown。已有 canonical completed 与 result 矛盾继续报错。
- 既有 `tests/operations/test_runtime_plugin_configuration.py` 复用小 execution package，新增直接 wrapper/Records 测试依赖；不建 Root/runtime/安装 fixture。

未修改 P3 source/qualification/contracts/controller/CLI，不做 P2d retire，不加 LifecycleCapabilities 字段、预算 owner、科研状态账或授权库。

## 接线与原件

managed factory 用原 RuntimePluginFactory/ExecutionInterfaceRegistration，返回 opaque wrapper，`result_protocol=None`。公开 capability 为 ExecutionPackage 输入 schema，没有 local command/snapshot/candidate 协议。原 adapter 构造不调用远端；factory 固定不注入 gate，JSON 不能选 gate/test/allow。实际 prepare 在任何底层 capability RPC/prepare/upload 前完成本地 descriptor/package 校验并遇到缺 P3 gate 的默认阻断；submit 也须复核同宿主 gate 原件。注册成功不启用真实执行。

唯一可信 gate 调用收 phase、原 scope/call、既有 payload/prepared descriptor 与冻结 host target。gate 必须返回可核验的 owner receipt；执行阶段另复用 ExecutionAdmission，collect 阶段复用 CollectionContext。P2 不从 package 中的 pass 文字或 W 成本声明构造权限，不写 reservation/settlement。prepare 与 submit 使用同原 payload descriptor/receipt；准备目录另保留实际复制后的 package descriptor并核对字节相同，不通过改路径悄悄改变授权 subject。target 只取宿主 transport 配置，并冻结 command/已知 bundled transport 配置文件 hash，不向材料复制私密内容。

精确原件读取只透传 P2b metadata/open 回调；当前生产 factory 没有 gate 或冻结原件 resolver 接线。缺这两项仍 fail closed，未来由 P3 owner 在唯一 factory 串行接入，不能按近似路径、相同 hash 或最近记录找原件。类构造依赖注入仅是可信 Python 宿主/fixture 接缝，没有公开绕过参数。

返回 prepared descriptor 保留原 call_id；Records 仍唯一接受并保存 accepted/submission/completed/observation。wrapper 核 scope、native_attempt、interface、prepared 与 canonical source copy，dispatch_lease 只给本进程一次 fresh owner；submit 在 backend 调用前独占写持久 intent并消费 lease。已有 intent/重启只 lookup，None 或丢回执不重发、不退款。lookup 用原 prepared，核同原 external ID 再 query；旧 command status 不含 digest/run_id也不能省略此步。

query 不收集。native terminal 字符串不等于合格 observation；result/collect_original 须保留实际 manifest、日志、全部 outputs 与宿主绑定回执，再发布共同 completed。统一校验函数供首次、collected 已落而 completed 未落的恢复、已 completed 只读复核使用：核 call/scope/mechanism/external/prepared/target、回执状态及输出清单、retained 文件必须属于原 call 的 `tcad-originals/<sha>`，并重验完整 descriptor 与 native manifest。cancelled 保留 native_state、工程 known_failed，不产生科学结论。

## deadline 与缺证据

经独审发现并由 root 批准，在插件内把同一原 CollectionContext 传到分块 hash/copy、manifest 读取、清单复核与首次 completed 发布前检查；不复用已过时 submit 操作 timeout，也不重置 job/整场授权。大小没有新增 cap。首次与 collected 恢复都向同一 gate 消费原授权当前 remaining，不能用重入发新 grant。截止耗尽返回 unknown，保原 raw/partial，不造 completed；同值 partial 可在后续合法剩余授权内重验/重新复制。

context 检查是分块/阶段之间的软截止，不能中断单次文件系统调用、JSON/Pydantic 解析或最后的原件发布。已 completed 的本地只读完整证明复核不申请新的 collect context；通用 observation 层后续原件核验/复制仍由既有 core 实现，本节点不声称它们获得新的硬截止保证。没有动态时间/RSS、并发或文件系统强隔离证据。

缺 collect gate/remaining/传输回执返回 unknown；身份/原件篡改仍 IntegrityError。已 waiting 路径保留原 raw/checkpoint/reservation并停在 terminal_unverified；终态首次出现但无证据时，现有 before_seal 可保留普通科学输出，执行事实按 unknown封存，不能声称原 W 已消费合格终态。该 unknown 阻止后继新 call，不重派未知执行。

## 定向负控与静态证据

测试只注入可信小假 backend 和 owner；backend.prepare 仍使用真实 P2b materializer/packager，但不代表实际 adapter/远端已执行。P2b 的两个真实 adapter.prepare 路径负控保留。本节点新增五个 case：

1. 默认实际 managed factory 在 backend 调用前 blocked；公开 JSON gate 设置拒绝。
2. accepted→queued→cancelling→cancelled 原 call/remote ID保真；错 lookup ID 拒绝；manifest/log 进入 observation；重复读取不再查询/收集；篡改原 backend binding 拒绝。
3. submit 响应丢失、随后 lookup None不重发；native succeeded但无 collection权限不造 completed、不放新 call；已有 completed不能由 unknown result隐藏矛盾。
4. 截止在本地分块保留时耗尽，返回 None observation，保 raw/partial，无 completed；同已过期 context不再次 collect。
5. 已 collected而未 completed的模拟崩溃：篡改 native_state拒绝；恢复原件后用 retained事实完成，不再查询/收集。

四个改动 Python 文件 AST、pyproject 注册 TOML文本解析、定向 diff/尾空白/文档链接检查通过。私有全文+SHA-256快照保存在 repo `.trial/reviews`，不提交。上述测试已编写但未运行；没有 pytest/collect、项目 import、CLI/进程、build/install、模型、SSH、许可证或 solver。

P3c/d 的可信授权 UI/策略、累计 solver reservation/settlement、真实 frozen-source接线仍未实现；P2d恢复、实际 SSH/solver、跨 boot、真实 session wake、领域候选及隔离等主计划未验收限制保留。本节点不授予生产资格。
