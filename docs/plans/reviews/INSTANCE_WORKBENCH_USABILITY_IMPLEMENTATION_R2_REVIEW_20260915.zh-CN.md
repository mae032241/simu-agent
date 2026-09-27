# 实例工作台可用性修订实现 R2 独立工程复审

日期：2026-09-15。结论：**PASS（工程实现与隔离可用性验证通过；不代表生产部署通过）**。

## 精确对象与范围

本次复审 [R1 实现审查](INSTANCE_WORKBENCH_USABILITY_IMPLEMENTATION_R1_REVIEW_20260915.zh-CN.md)唯一必需修订：实际执行授权被错误显示为科学依据批准。原[可用性修订计划](../INSTANCE_WORKBENCH_USABILITY_REPAIR_PLAN.zh-CN.md)保持不变，SHA256 为 `0052352c68a53aa11a28b56a1ab0e03bc8e5a937f0fb2593edb6451114266048`。

精确源码采用固定的 [USABILITY_SOURCE_MANIFEST_R2.json](../evidence/instance-workbench/USABILITY_SOURCE_MANIFEST_R2.json)，清单 SHA256：

```text
25eb763b5d807822da25ddc0950990b5cc2b95824b853159b63b0757322acd6c
```

独立重新计算 14 个清单文件的字节数与摘要，全部相符。与固定 R1 清单比较，仅 3 个生产 UI 文件变化：`presentation_render.py`、`render.py`、`workbench_render.py`；另修改 1 个定向测试文件和 pending 浏览器探针。`app.py`、`read_model.py`、`presentation.py`、CSS、工作台脚本及其他清单文件均与已审 R1 相同。

使用 `scid-cross-boundary-review` 与 `karpathy-guidelines`；只读检查源码、测试代码、已有验证输出和截图，并写本报告。没有运行测试、浏览器、服务或科研工具。

## R1 必需修订已关闭

1. **真实类型与两个入口一致。** `presentation_render.py:258` 的 `approval_heading()` 是一个纯展示映射：`execution_authorization` 显示执行审批，`scientific_foundation` 显示科研依据审批；旧模板类型保留兼容。未知或非文本类型返回“科研审批／请审阅本次冻结请求”，没有猜写批准行为。`render_review()` 与 `render_node()` 均复用该函数；没有在映射中加入调度、资格或决定权。
2. **原问题不会被中文提示替代。** `render.py:101` 对所有语言的冻结原问题显示最多 320 字符的有界原文；更长问题另有展开入口和完整请求原件。历史节点也保留原问题与原决定。没有新增科学翻译、摘要或修改请求内容。
3. **验证改用实际执行类型与选项。** pending 探针使用 `execution_authorization`，表单值为 `authorize_execution`、`reject_execution`，显示“授权执行／拒绝执行”。探针检查原表单实际 input value，读取后请求仍为 pending，没有提交决定。合成 subject 和合成问题仍明确标注为 UI 验收资料，没有伪称为真实科研请求。
4. **自定义合同继续原样可读。** 新增参数化测试覆盖实际执行、科学依据和未知类型，并检查英文原问题在默认内容中、原选项 ID/文案及 `requires_rationale` 保留、冻结请求字节不变、请求状态不变。修订没有改动原审批写入流程、CSRF、nonce 或审批身份。

实际查看了 [R2 pending 桌面截图](../evidence/instance-workbench/usability-pending-r2-wide.png)、[390 像素截图](../evidence/instance-workbench/usability-pending-r2-390.png)、[历史执行审批](../evidence/instance-workbench/usability-execution_approval-wide.png)与[历史科学依据审批](../evidence/instance-workbench/usability-evidence_approval-wide.png)。执行页明确显示执行授权，科学依据页明确显示依据审批；原问题和决定没有再被错误类型标题替换。未发现新的阻断或必需修订。

## 功能与框架边界结论

结合 R1 已独立核对且本轮未改动的来源、预算与权限实现，本修订已经解决本轮明确的界面可用性问题：

- 当前审查自身结果成为主结论，旧输入仅作为背景；失败节点不借用输入的正式结果。读取、提供者合并和 HTML 三层的成果优先级保持。
- 原目标通过精确绑定与 producer 输入定位，当前计划参数与关联历史参数分别显示。多分支、分页、原件、日志、缺口和不确定性入口保留；没有由 UI 推导科学资格或总体研究成功。
- 默认页面采用中文标题、状态、轨迹与短概览，长科学原文按需展开。当前节点默认高度仍为 1,025 像素，较旧 18,111 像素减少约 94.3%；精确原文和图件可进入，科学计数法保持整行和原精度。R2 真实材料重放保留上述行为。
- 原审批与历史阅读职责分开，选项的展示中文化不改变提交身份和冻结对象。没有新增 Agent、提示词要求、科研准入、状态机或持久化机制；Operation、Worker 和执行/归档控制职责保持原有边界。

因此，**在本次冻结实现、所检现有展示提供者、真实资料隔离重放和隔离待审批入口范围内，可用性修订已通过**。这项判断不依赖仅有 HTTP 200、DOM 字段存在或测试数量。

## 本轮证据

下列测试由实施者运行，本审查读取其源码与既有结果，没有重复执行：

| 证据 | 独立读取结果与适用范围 |
| --- | --- |
| [R2 定向测试](../evidence/instance-workbench/usability-r2-tests-pass.log)及对应 JSON | 53 项通过；进程树峰值 132.98 MiB。包括实际类型、自定义类型、原问题可见和原件/状态不变的断言。与 R1 的 88/34 项有交集，不相加为独立总数。 |
| [R2 pending 结果](../evidence/instance-workbench/USABILITY_PENDING_BROWSER_R2.json)、`usability-r2-pending.json` | 1280/768/390、图件实际加载、手机依据先于决定均通过；默认高度 1,442 像素；峰值 463.26 MiB。实际类型与两个选项值明确记录，没有决定写入。 |
| `usability-r2-nojs.log/.json` | 无 JS 时原生 details 和原决定表单可操作；没有提交决定；峰值 426.35 MiB。 |
| `usability-r2-real-replay.json`及更新的 `USABILITY_REAL_REPLAY.json` | 真实已捕获资料重放成功，历史审批标题、节点布局、来源分组、图件与数字整行检查保留；峰值 491.17 MiB。 |
| [R2 隔离安装日志](../evidence/instance-workbench/usability-r2-installed.log)及对应 JSON | 4 个 wheel 安装检查通过，耗时 16.512 秒、峰值 395.2 MiB。日志确认 50 项合同一致、2 个展示提供者、静态 HTTP、隔离归档浏览/恢复、Root/Worker stdio、UTF-8 与两次合成复用接续；明确没有真实科学 Agent 或科学执行。 |

所有上述 R2 成功记录的 `exit_code=0`、`stop_reason=null`、预算为 512 MiB。新增测试第一次因夹具只有 1 个选项而被原合同拒绝的失败保留；修正的是夹具，没有放宽生产校验。R1 的超预算终止记录也继续保留。本轮仅改变纯显示逻辑；R1 已逐字核对的 45/50 项合同快照，以及 R2 安装后的 50 项一致性结果，共同支持框架合同未被本轮修改。

## 交付边界

**最终结论：PASS，无仍需阻断交付的工程修订项。** R1 的 REVISE 保留为历史，本 R2 关闭其唯一发现，不回写旧报告。

此次通过覆盖工程实现和隔离验证。线上仍需重新安装与重启后才能获得新页面；本审查没有确认新版本已部署。重放中的 SSE 是无变化 fixture，不能据此宣称生产实时推送验收通过。未导出的祖先、历史目标缺口和未知 schema 的展示限制仍须如实保留；本通过结论不补全这些科学记录，也不代表科研目标完成。
