# 实例工作台可用性修订实现 R1 独立工程审查

日期：2026-09-15。结论：**REVISE（1 项必需修订）**。

## 审查对象

审查已通过的[可用性修订计划 R1](../INSTANCE_WORKBENCH_USABILITY_REPAIR_PLAN.zh-CN.md)对应实现。计划 SHA256：

```text
0052352c68a53aa11a28b56a1ab0e03bc8e5a937f0fb2593edb6451114266048
```

精确源码由固定的 [USABILITY_SOURCE_MANIFEST_R1.json](../evidence/instance-workbench/USABILITY_SOURCE_MANIFEST_R1.json) 标识，清单 SHA256：

```text
b151d91f1a377a96fc2c652a143823511f1d5591354bd321ac3d1757b1145ce4
```

独立重新计算清单中 14 个文件的长度和摘要，全部相符。与原 `SOURCE_MANIFEST.json` 逐项比较，原清单覆盖范围内仅 8 个 UI 生产文件和 3 个已有测试文件变化，无文件缺失；本轮还新增 1 个测试及 2 个隔离浏览器探针。未把仓库中更早的未提交改动算成本轮修订。

使用 `scid-cross-boundary-review` 与 `karpathy-guidelines`。本次只读取源码、测试源码、既有日志/JSON、合同快照并查看截图；未启动测试、浏览器、服务或科研工具。只新建本审查文档。

## 必需修订：真实执行授权被显示为科学依据批准

**严重程度：高。位置：`approval_ui/render.py:102,124`，同类遗漏在 `workbench_render.py:331`；验收盲点在 `usability_pending_browser.py:84` 附近。**

`render_review()` 只在 `request.kind == "run_request"` 时显示执行审批，所有其他类型均生成“是否批准本次提交的科研依据”。然而生产执行路径在 `interfaces/mcp_root_execution_routes.py:247` 创建的冻结请求使用 `kind="execution_authorization"`，`:233` 检查复用请求也要求此值；`service/executions.py:373` 再次要求这个真实类型。`operations/spec.py:211` 的审批合同默认值相同。`run_request` 是旧选项模板名，不能代替生产请求类型。

因此，用户从实际 TCAD 执行授权 URL 打开待审批页时，会看到“科研审批／是否批准科研依据”，同时表单实际决定的是执行授权。UI 没有改变提交 ID 或写入权限，但首屏把用户正在批准的动作说错了；这违反 U1/U2 关于“批准什么、允许什么”和科研结论与执行授权分别表述的要求。

历史节点页也只识别 `run_request` 与 `artifact_qualification`，没有识别实际的 `execution_authorization`、`scientific_foundation`。[真实执行审批截图](../evidence/instance-workbench/usability-execution_approval-wide.png)可见通用“科研审批”标题下才出现“已授权执行”与原问题。历史页因为原问题可见，影响较小，但应与原审批入口使用同一份正确的纯展示映射。

[pending 探针](../evidence/instance-workbench/usability_pending_browser.py)明确创建 `kind="run_request"`，并使用 `approval_options_template("run_request")`。其截图、无 JS 和布局检查对该合成请求有效，不能覆盖上述生产类型。绿色表单检查和不变的合同快照均不会发现这项展示语义错误。

### 最小修订与复验要求

1. 在既有纯展示代码内统一识别实际 `execution_authorization`、`scientific_foundation`，可保留已经支持的旧模板类型。未知或自定义类型使用中性“请审阅本次冻结请求”，不能统一宣称是在批准科研依据。原审批与历史节点使用一致的文案来源，无需改变任何 Operation、审批合同或存储字段。
2. 默认保留冻结原问题的有界可见内容及原件入口；英文或长问题也不能仅由错误或过于笼统的生成标题取代。完整原文和固定文档继续按需展开，选项 ID、理由要求、CSRF、nonce、审批身份与原件字节保持不变。
3. 将隔离待审批主场景改为生产 `execution_authorization` 和实际已编译选项，或其精确冻结副本；旧模板的中文化可作为独立兼容场景保留。补充实际科学依据类型与未知类型的定向渲染检查，证明执行授权不再显示为科学依据批准、自定义语义不被猜写。
4. 按既有资源限制串行复验受影响的待审批桌面/平板/手机和无 JS 入口，更新源码清单与相关证据后进行 R2 独立复审。无需新增科研 Run、改变 Agent 职责或重写已通过计划。

## 已确认有效的修复与保留证据

在此次冻结版本与所检注册展示提供者范围内，除上述审批类型问题外，未发现新的必需修订。

- **当前成果归属和预算。** `node_context()` 先读取完成 Run 的自身 output，再读取其精确 `experiment_plan`，然后读取其他输入与来源。失败 Run 不提供焦点成果。`build_presentation()` 在项目数和字节裁剪前对当前成果及计划参数排序，先移除背景；最终 HTML 主卡也先保留当前成果预算。对应定向测试和真实重放显示：当前 `pass` 不再被旧输入 `blocked` 占据，失败节点明确没有封存结论。
- **原目标定位。** 通过完整 ArtifactRef 的 producer 查询及冻结输入端口，区分 prior plan 与同 schema 的背景计划；物化计划经 intent 的原 objective 端口定位。当前真实审查恢复 1 个目标且无节点目标歧义；历史来源缺失和真正歧义没有被转换成新资格或总体成功。
- **层级与精确来源。** 主卡具有计划原件入口，意见/限制计数可进入原字段；参数入口及表内区分本节点/绑定计划与关联历史，缺省与不确定性保留。科学原文仍是原文，未增加翻译或摘要 Agent。历史审批的原问题与决定可读，普通历史节点没有新增提交表单。
- **可用性与数值。** 查看了首页、当前审查、390 像素节点、展开参数、两类历史审批、图件和 pending 截图。当前审查由 18,111 像素降至 1,025 像素，约减少 94.3%；首页 1,470 像素，两个历史审批为 974/1,034 像素，失败节点 900 像素。此前指数断行问题已通过独立数值 span/CSS 修复，更新参数截图将 `6.76862812233398e+19` 完整保留；重放记录中相应 `numeric_tokens_unbroken=true`。已加载图件不能与旧截图中尚未触发的懒加载标记混为一谈。
- **原职责边界。** 展示仍消费已授权只读资料；审批请求、决定身份和原提交路径仍由原控制服务所有。UI 没有新增科研准入、选目标、改状态、调用执行或更新资格的职责。`workbench.js` 仍只提示控制元数据变化并提供手动刷新，没有自动提交或依据重绑定。

## 验证证据及其适用范围

已读取[实现记录 R1 快照](../evidence/instance-workbench/USABILITY_IMPLEMENTATION_R1.zh-CN.md)及其引用材料，并独立核对以下事实。下表描述的是本次 R1 审查时已有证据，不把后续同名探针输出追认为 R1 通过证据：

| 证据 | 所能支持的结论 |
| --- | --- |
| `usability-final-regression.log/.json` | 88 项定向检查通过，峰值 141.88 MiB。测试覆盖当前/失败结果、精确计划来源、原件、渲染及执行审批身份；本审查没有重新运行。 |
| `usability-boundary-tests.log/.json` | 34 项权限、HTTP、诊断/推送与原件相关检查通过，峰值 136.0 MiB；与前项有交集，不能相加为独立总数。 |
| `USABILITY_CONTRACTS.json`、`USABILITY_CONTRACTS_OPTIONAL_FIGURE.json` | 独立按字节比较各自基线文件，完全一致，分别有 45/50 项 Operation；保留原 Operation/Root/Worker 合同，不等于所有新 UI 文案语义正确。 |
| `USABILITY_REAL_REPLAY.json`、`usability-real-replay-numeric.json` | 真实已捕获资料的隔离展示、页面高度、原件归属及数值排版；数值复验峰值 478.77 MiB。来源子集导致的 `source_missing` 不能当作生产存储缺失；无变化 SSE fixture 不能证明生产推送。 |
| `USABILITY_PENDING_BROWSER.json`、`usability-pending-localized.json`、`usability-pending-nojs.json` | 旧模板合成 pending 的 1280/768/390 布局、图件和无 JS 表单可操作；峰值分别 444.14/410.66 MiB，未提交决定。需按本次发现补生产类型场景。 |
| `usability-pending-browser.json` | 首次合并探针因内存超过保护上限被终止，记录峰值 523.23 MiB；后续拆成串行独立进程且未提高 512 MiB 预算。保留失败是正确的，不能将首次尝试记为通过。 |
| `usability-installed.log/.json` | 4 个 wheel 的隔离安装通过：50 项合同、2 个展示提供者、静态 HTTP、隔离归档浏览/恢复、Root/Worker stdio、UTF-8 和合成复用接续；峰值 395.12 MiB。日志明确没有真实科学 Agent 或科学执行。这是安装包与隔离入口证据。 |

**最终结论：REVISE。** 现有工作台的内容归属与可用性改进得到支持，但实际执行授权入口的展示语义必须修正后再做 R2。此前计划 PASS 与已经完成的检查保留；本记录不声明新版本已部署、不声明生产浏览器或实时推送验收通过，也不声明任何科研目标完成。
