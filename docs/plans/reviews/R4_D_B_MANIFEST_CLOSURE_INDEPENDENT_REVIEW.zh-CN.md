# R4-D-B 根发布清单收口独立审查

审查日期：2026-08-29  
审查对象：当前根 `MANIFEST.sha256` 所冻结的 280 路径发布集合。  
审查性质：独立发布审查；未修改生产代码、测试或清单。

## 一、结论

**通过，允许 R4-D-B 正式收口并进入 R4-D-C。**

根清单的路径、工作树字节、R4-D-B 六轮实现审查记录、按清单重新复制的发布树、核心编译目录、
审批 Operation 数量、shell 语法和差异格式全部一致。未发现缺失文件、重复路径、摘要漂移、构建
缓存或未被清单约束的发布执行入口。

本报告是清单封存完成后按委托产生的独立审计记录，不属于本次被审查的 280 路径发布集合。委托
明确禁止审查者反向修改生产文件、测试或清单，因此本报告不会被偷偷补入已经通过的清单，也不
改变本次 280 路径发布候选的字节身份。后续若要形成包含本报告的新发布代际，必须另行重建并审查
新清单，不能声称本报告已被当前清单摘要。

## 二、清单自身核验

独立解析 `MANIFEST.sha256` 后确认：

- 精确 280 行；
- 280 个路径全部唯一；
- 每个路径均指向当前工作树中的普通文件；
- 每条摘要均为合法 64 位十六进制 SHA-256；
- 对 280 个工作树文件重新计算摘要，全部与清单一致。

该结果证明当前清单不是只在另一份临时目录中自洽，而是精确绑定了当前被发布的工作树字节。

## 三、R4-D-B 六轮正式报告覆盖

清单精确包含：

1. `R4_D_B_CORE_APPROVAL_IMPLEMENTATION_INDEPENDENT_REVIEW.zh-CN.md`；
2. `R4_D_B_CORE_APPROVAL_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND2.zh-CN.md`；
3. `R4_D_B_CORE_APPROVAL_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND3.zh-CN.md`；
4. `R4_D_B_CORE_APPROVAL_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND4.zh-CN.md`；
5. `R4_D_B_CORE_APPROVAL_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND5.zh-CN.md`；
6. `R4_D_B_CORE_APPROVAL_IMPLEMENTATION_INDEPENDENT_REVIEW_ROUND6.zh-CN.md`。

第六轮报告的清单摘要与工作树字节一致，正式结论为“通过并允许进入 R4-D-C”。六轮历史均被
保留，没有只收录最终绿灯而删除此前打回依据。

## 四、从清单重建发布树

审查者创建全新的临时目录 `/tmp/scid-r4db-manifest-review.ARiqKJ`，只使用清单中的路径作为
`rsync --files-from` 白名单从工作树复制文件。没有调用宽目录复制，也没有把未列入清单的文件带入
候选。

复制后独立遍历结果：

- 发布树恰好 280 个普通文件；
- 文件路径集合与清单精确相等；
- 280 个发布文件的重新计算摘要与清单逐项相等；
- 无 `*.pyc`、`*.pyo`、`__pycache__`、`.pytest_cache`、`build` 或 `*.egg-info`。

随后从发布源码执行目录编译，结束后再次扫描，仍无 Python 或 pytest 缓存。

## 五、关键实现文件与工作树一致性

以下八个关键文件均在清单中，且清单复制版本与当前工作树逐字节相等：

- `src/scidiscovery/artifact_agent/interfaces/mcp_root.py`；
- `src/scidiscovery/artifact_agent/schema/research_cycle.py`；
- `src/scidiscovery/artifact_agent/schema/approval.py`；
- `src/scidiscovery/artifact_agent/service/approvals.py`；
- `src/scidiscovery/operations/spec.py`；
- `src/scidiscovery/operations/catalog.py`；
- `src/scidiscovery/operations/invoke.py`；
- `src/scidiscovery/general_science_plugin.py`。

因此 Root、研究对象 Schema、审批 Schema/服务、Operation 声明与编译/调用、通用科学插件之间
不存在“测试工作树已修复、发布树仍是旧文件”的边界断裂。

## 六、发布源码编译与脚本核验

在只含清单文件的发布树中，以 `src` 为唯一项目源码路径编译 `CORE_PLUGIN` 与通用科学 `PLUGIN`：

- 编译成功；
- 精确得到 32 个 Operation；
- 其中精确 3 个 executor kind 为 `approval`，且均属于 public 视图：
  - `science.evidence.qualify.v1`；
  - `science.parameters.qualify.exception.v1`；
  - `science.parameters.qualify.pass.v1`。

发布树内共 6 个 shell 脚本，全部通过 `bash -n`。`git diff --check` 同样通过。

## 七、范围与剩余风险

本次审查是发布清单和编译边界审查，没有重新运行浏览器审批、live Worker、外部 TCAD solver 或
R4-D-B 已完成的 236 项全仓测试。第六轮实现审查已经记录这些阶段相应的聚焦、Operation 全集和
全仓证据；当前任务要求验证的是它们所对应字节是否被准确收入发布候选。本轮用工作树逐项摘要、
白名单复制、关键文件字节比较和发布源码真实编译覆盖了这一精确风险。

该发布收口没有新增注册表、状态、路由或兼容入口，也没有把审批 provider 重新写成发布脚本
allowlist。发布目录仍由同一插件声明编译，符合轻控制面、单一 Operation 目录和通专分离目标。

## 八、最终结论

**通过，允许 R4-D-B 正式收口并进入 R4-D-C。**
