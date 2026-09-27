# 科研内容展示修复 R1 独立实现审查

2026-09-15。**源码实现审查及已完成的隔离验证 PASS；已识别的必要工程问题已关闭。生产安装后的现场验收仍待完成，不能据此报告整轮交付通过。** 本轮只覆盖 P1/P2 及对应 P4，P3 正文翻译继续暂缓。

## 精确审查对象

- 计划：[修复计划 R1](../INSTANCE_RESEARCH_CONTENT_DISPLAY_REPAIR_PLAN.zh-CN.md) §9；前置审查：[计划 R1 独立审查](INSTANCE_CONTENT_DISPLAY_PLAN_R1_REVIEW.zh-CN.md)。
- 开工基线：[BASELINE.json](../evidence/content-display/BASELINE.json)，源码副本 `/tmp/scid-content-display-baseline`。独立核验其中 189 个文件散列全部相符；没有把 HEAD 上已经部署但未提交的既有改动算成本轮修改。
- 最终源码候选：[SOURCE_MANIFEST.json](../evidence/content-display/SOURCE_MANIFEST.json)，共 11 个生产文件，逐项核验与工作树一致。清单文件自身 SHA-256：`069223bb569dfb7e37e13a561f1896d954f17cbbf3ea2d979f8f70f6f49be6f3`。相对初次实现报告，唯一生产文件变化为 `presentation_render.py` 的条件枚举本地中文映射，已复核；其余 10 个文件散列相同。本结论仅适用于该候选；生产文件后续变化须复核。

审查沿授权读取、原件选择、展示提供者、HTML/下载入口和插件打包入口展开，使用跨边界审查与最小改动技能。本审查者没有运行测试、浏览器、构建、服务或科研 MCP，没有修改生产源码，没有启动子 Agent；只阅读源码、测试、执行记录与截图并新增本报告。下列执行结果来自实施方保存的工程证据，不称为本审查者亲自执行。

## 必要问题及关闭结果

### 1. 部分证据目录不能证明引用唯一：已关闭

初始候选的 `general_science_views._foundation` 在节点的 24 KiB `/evidence` 前缀中找到一条匹配，就显示已连接出处；原件后部相同键可能被截去。另有多键引用只要一条解析成功，就把另一条缺失覆盖为完整连接的情况。

最终候选在原件投影有读取缺口时不声明唯一引用，逐键保留未解析状态；一条已解析引用不消除其他键的缺口。补充用例实际构造超 24 KiB 的证据字段及隐藏的重复键，并检查节点预览和完整参数页；混合已解析/缺失键另有覆盖。TCAD 提供者也检查精确 parent 祖先是否齐全，以及目录自身是否部分读取，不能用无关根节点或未完整读取的目录宣称来源唯一。

### 2. 部分家族与清单不能证明成员唯一：已关闭

初始候选把查询或合并超限放在上下文缺口中，提供者仍可从剩余成员作唯一关联；缺失端口时的回退还省略了 collection 对应校验。

最终候选保留只读的同实例、同 request_fingerprint 查询，并核对保存的 operation、transform 标识与完整有序 parent_refs。查询缺口、候选身份冲突、合并上限与展示输入裁切会标记相应家族读取不完整。提供者同时检查 manifest 成员字段的投影缺口，停止从这种部分集合作成员唯一映射。

正常关联必须同时符合 hash、bytes、media_type 与保存的输出端口；清单 collection、data_item 前缀及媒体用途须对应。缺端口旧记录不再走推断回退，只留下局部缺口和原件入口。重复 data_item 无论后一个成员能否匹配，都使先前映射失效。CSV 链接不能指向图像；单个坏成员的字段类型/身份问题不会使正常图卡整体失败。原图、数值重绘和原图叠点分别标注，缺重绘不触发重新提取或当前科学合同验证。

### 3. 参数条件标签实际不可见：已关闭

首轮真实参数回放中，“适用条件”只显示预览限制。`_conditions` 给非空字典 768 字节，而通用字典渲染器在扣除容器后要求至少再有 768 字节，因此很短的变量类型、对照角色也无法显示。

最终候选将这些平面条件逐项有界渲染，并使用已有枚举的中文值；新增断言检查“变量类型 / 物理参数 / 对照角色 / 固定”实际进入页面。随后根据真实回放补齐 `intended_change`、`frozen`、`permitted_difference`、`exact`、`absolute_tolerance`、`reviewed` 的本地中文标签；没有翻译科学正文或改变原字段。最终参数浏览记录已明确显示“变量类型：物理参数；对照角色：预期变化；等价规则：依审查判断”，该实际可见问题关闭。

## 已检查且未发现阻断的问题

- **原件参数续页。** `parameter_context` 先授权确切原件，在既有 `MAX_SOURCE_BYTES` 内读取完整 JSON，独立于节点 24 KiB 字段前缀。`ParameterPageRows` 保留所选 8 行并计算总行数；原 provider 的 128 行预览限制不会把后页截断。变量与案例逐项保留，不用页内索引代替原索引。超长详情保留值、明确缺口和原件入口。超过原件读取限额不伪报完整计数。
- **出处与科学分类。** 实验设计取值、器件参数声明、实现绑定分别解释；没有科学分类不再推出工具默认。实现值引用按当前项目的确切 parent 依赖范围匹配 approved_parameter_key；缺失或歧义时保留实现原记录而不拼接较新取值。来源类型从已有字段显示，未知值保留。
- **审批与下载。** 普通节点的同调用发现没有进入 `approval_context`。图片、CSV、参数页各 HTTP 入口首先校验普通浏览权限或冻结审批 subjects 的可达范围；没有增加决定权限或修改审批请求。完整下载仍发送原注册字节，CSV 只改善附件文件名。
- **工程范围。** 新插件能力仅为 `scidiscovery.instance_views` 展示入口；提供者只收到展示数据，没有 service、文件读取或科研工具权限。scheduler_bindings 仅新增有界 SELECT，没有修改登记、幂等、准入、输出 Schema、Run 生命周期、执行器或翻译持久化。

## 执行证据与尚未完成的验收

已阅读的最终候选定向回归为 [final-regression.log](../evidence/content-display/final-regression.log)：**53 passed**；[保护器记录](../evidence/content-display/final-regression.json) 显示退出码 0、峰值进程树 RSS 120.39 MiB，预算 512 MiB。覆盖原件超 24 KiB、超过 128 行、嵌套 reviewed package 后页、缺祖先、部分/混合来源、缺端口、家族查询上限、坏成员、重复清单键和超长详情。前次 [review-regression.log](../evidence/content-display/review-regression.log) 的 53 passed 保留为枚举标签增量之前的记录，不冒充最终候选结果。

此前 [边界回归](../evidence/content-display/boundary-tests.log) 为 99 passed、2 failed；两项失败所在模块已纳入上述最终定向回归并通过。不能将两个不同候选的记录改写为最终候选完整跑过 101 项。

已阅读 [图证浏览记录](../evidence/content-display/BROWSER_curves.json) 和 1280/390 截图：三张图件实际可见、两份 CSV 下载散列已记录、无页面溢出，默认节点高度记录为 1840 px。[图证回放执行记录](../evidence/content-display/browser-curves-final.json) 退出码为 0、峰值 RSS 331.94 MiB。该回放使用真实原件字节和隔离控制绑定，记录真实科研写入为 0；不是已部署服务上的最终安装验收。

已阅读最终 [参数浏览记录](../evidence/content-display/BROWSER_parameters.json)：实际展开详情显示中文类型、角色和等价规则，原件总计 28 条，第一页为 1–8 条、下一页为 9–16 条；移动页面没有溢出，HTTP/JavaScript 错误均为空。[最终参数回放执行记录](../evidence/content-display/browser-parameters-complete.json) 退出码为 0、峰值 RSS 277.7 MiB。修复前只有预览限制的旧回放不再用作本项通过依据。

已阅读串行隔离安装的 [保护器记录](../evidence/content-display/installed.json)、[工作台探针输出](../evidence/content-display/content-installed-workbench.stdout) 与 [接续探针输出](../evidence/content-display/content-installed-continuation.stdout)。四个 wheel 的构建与无系统 site-packages 安装完成；退出码为 0、峰值 RSS 394.85 MiB。新展示提供者由安装后的 entry point 实际发现，50 项 Operation 及 Root/Worker 工具合同与冻结快照完全一致；安装态读取真实原件后可组成三张图、两条 CSV 链接与 28 条参数。隔离状态的归档读取/恢复，以及 Root/Worker stdio 下复用 Worker 的两个合成 Run 接续均通过。探针明确未启动真实科学 Agent 或科研外部执行。

**剩余验收只有用户安装后的只读生产现场确认。** 当前可以报告 P1/P2 实现、定向工程回归、真实原件的隔离浏览回放及隔离打包通过；不能报告已部署服务完成验收，也不能把合成 Run 探针解释成真实科研任务成功。

P3 翻译服务、中文阅读副本、缓存及归档扩展均未实施，也不是本轮源码审查的阻断条件。
