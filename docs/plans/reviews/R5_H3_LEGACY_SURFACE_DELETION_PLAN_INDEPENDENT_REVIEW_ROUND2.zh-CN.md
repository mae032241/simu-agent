# R5-H H3 旧表面删除方案第二轮独立审查

日期：2026-08-30  
审查对象：`docs/plans/R5_H3_LEGACY_SURFACE_DELETION.zh-CN.md`  
候选 SHA-256：`ac8b586f074eba637284b704623aff541fabfbfd001b3f2be8fa70479d45fbab`  
首轮报告 SHA-256：`a60f638b13a650c2f9509e775bbcbaed40ee970ccec7de28dd33bc91d81737db`  
结论：**通过**

## 1. 结论范围

修订方案已经逐项关闭首轮报告的六个最小条件，没有引入新的生产文件、数据库表/列、状态、
OperationSpec 字段、Registry、路由器、兼容转发器、领域核心分支或通用入口校验。H3 仍是恢复唯一
current 和唯一 Worker 文件协议的纯减法。

本结论只批准按计划进入 H3-A；不代表 H3-A、H3-B、H3-C、H3-D 的实现已经完成。每个子阶段仍须
分别实现、回归并通过独立审查后才能进入下一阶段。

## 2. 首轮六项条件复核

| 条件 | 结论 | 修订证据 |
| --- | --- | --- |
| 补齐 `write_result_file`、死活动名和三个测试消费者 | 关闭 | 消费者表第 28、30—31 行已列出三个测试、六个旧服务方法和七个死活动名；H3-B 第 94—100 行明确删除并增加静态负例 |
| 精确列出待删模型并保留 `NamedInput`/`PdfInput` | 关闭 | H3-B 第 87—89 行逐项列出六个待删模型，并明确保留当前 PDF 请求继承链 |
| proxy 只删除旧 finalize 观察，保留 claim/validate 续租 | 关闭 | H3-B 第 90—93 行冻结当前续租行为，第 101—102 行增加失败修订、成功验证和 file finalize 聚焦回归 |
| 冻结普通/PDF/handoff-only 的 `access_modes` 总函数 | 关闭 | H3-B 第 83—86 行以 exposure、媒体类型和精确 Operation 工具授权给出完整机械规则，明确不增加媒体注册表或入口检查 |
| 旧孤立 binding 仅在生产 current 路径不可达 | 关闭 | H3-C 第 114—117 行覆盖实例列表、session candidates、session binding 和 get instance；明确保留原始旧行、不承诺底层任意 resolve 拒绝、不增加启动扫描或迁移器 |
| 保持净删除、逐门审查和明确放弃在线历史兼容 | 关闭 | 第 52—60、145—153、155—164 行继续禁止新兼容面和生产净增，并保留 H3-A→B→C→D 独立门 |

## 3. 复杂度与边界判断

- PyYAML 只移入 test extra，并要求在没有 system site packages、`yaml` 确实不可导入的 base-wheel
  环境验证当前数据库；这证明依赖删除而不增加替代解析器。
- Agent 不再获得 `worker_read_input`；普通输入复用既有 task workspace，handoff-only 不产生路径；
  当前 PDF 提取和领域 contextual handler 继续复用已有 `TaskService.read_input/stage_input`，没有第二
  Agent 文件协议。
- 六个旧服务方法、12 个旧路由、旧模型、旧 capability、旧活动名和旧 proxy 终态分支一起删除，
  不会留下只有实现没有入口的半套兼容面。
- 孤立 binding 只是不再自动升级为 ResearchInstance；修订没有要求清理历史 SQLite/CAS、添加完整性
  状态或在每个入口重复验证。
- 当前 file validation/finalization、Artifact/Task/Approval/Execution、qualification、TCAD Effect、
  人工审批和恢复边界均被明确保留，33 项约束中的承重不变量不会因方案本身退化。

## 4. 实施审查必须看到的证据

方案通过不替代实现证据。后续各门至少应按计划提供：无 PyYAML 的干净 wheel 正例；12 个旧名经真实
Worker 服务端全部 unknown 的负例；普通/PDF/handoff-only 投影；proxy 失败修订和成功封存；当前终态
重启；旧孤立 binding 在生产 current 入口不可达；生产 Python/shell 净删除计量。发现实现为测试增加
第二协议或为旧状态增加校验层时，仍应在对应子阶段打回。

未发现新的方案阻断。允许开始 H3-A，H3-B 仍须等待 H3-A 实现独立审查通过。
