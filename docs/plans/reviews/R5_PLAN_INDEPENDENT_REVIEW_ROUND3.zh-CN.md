# R5 详细实施方案第三轮独立审查

日期：2026-08-29  
审查对象：

- `docs/plans/R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md`；
- `docs/plans/OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md`；
- `docs/plans/README.md`。

复核依据：`docs/plans/reviews/R5_PLAN_INDEPENDENT_REVIEW_ROUND2.zh-CN.md` 第 7 节  
审查性质：只核对第二轮冻结的四项局部复修；未参与方案修订；未修改生产代码；未运行测试  
最终结论：**通过**

## 1. 结论摘要

第二轮冻结的四项复修均已完整进入当前方案，表述与阶段依赖相互一致，也没有借修订新增在线
共享权威、持久状态、注册表、强制真实 solver 门或宏大效果基准。本轮没有发现需要继续冻结的
方案问题。

## 2. 四项复修核对

### 2.1 部署健康门的诚实边界：已闭合

`R5_CONTROL_WEIGHT_REMOVAL_IMPLEMENTATION.zh-CN.md` 第 9.2 节现已明确：

- control 与 Worker daemon 只在各自完成真实配置解析、Schema 校验和 contribution 构建后写出
  短生命周期摘要；
- 一次性只读探针只决定 systemd/安装组合是否为 healthy，不重新读取配置冒充进程事实；
- Root preflight 只验证 control 本地绑定，Worker claim 只验证 Worker 本地 tool service；
- R5 不把对端摘要放入逐请求准入，也明确不承诺发现绕过健康探针后的跨进程漂移；
- 在线协调、租约和跨进程共识仍留给 R7。

该修订消除了“外部一次性探针同时充当未定义逐请求权威”的矛盾，没有新增数据库、Artifact、
capability 或运行时注册表。

### 2.2 R5-G 私有运行材料与可发布证据隔离：已闭合

第 11.1 节现将两类材料明确分离：

- 完整 state、secret、socket、隔离 Codex home 以及原始 daemon/模型日志进入权限 `0700`、非
  `/tmp`、Git 忽略且不进入发行包的持久目录
  `.scidiscovery/r5-e2e-private/<run-id>/`；
- `deliverables/r5-e2e/<run-id>/` 只保留冻结输入清单、可公开科学对象或摘要、量表、脱敏运行
  证明和最终报告；
- 报告记录私有目录的保留/清理策略及所引用证据摘要，但禁止复制 token、密钥、配置内容、内部
  身份和未脱敏绝对路径；
- release builder 与 secret scan 必须用负例证明私有 state、原始日志和 secret 不会进入 Git、
  wheel、sdist 或交付集合。

该边界同时满足“证据不能只放临时目录”和“敏感运行状态不能进入版本库/发布包”，没有削弱
R5-G 的复核性。

### 2.3 上位计划三重复杂度口径：已闭合

`OPERATION_SPEC_MINIMAL_REFACTOR_PLAN.zh-CN.md` 第 24.2 节已与详细计划同步：

1. 第一口径只统计 R0 冻结的六个通用 Python 路径，职责迁出后目标文件仍加入聚合，目标相对
   8765 净减至少 10%；
2. 第二口径统计整个 `src/scidiscovery/operations/`，不得高于 R5-0 基线；
3. 第三口径统计 `src/ + plugins/` 全部生产代码，core 到 plugin 的移动不算删除。

文本同时明确 `deploy/install.sh` 只作为部署表面单列增减，不进入第一口径的 Python 分母，但仍
接受独立审查。三种口径共同阻止通过搬文件、重命名、压行或把代码移入插件伪造复杂度下降。

### 2.4 R5-A1 与 R5-A2 的破坏性边界：已闭合

详细计划第 5 节已在 R5-A 内增加两个独立门：

- R5-A1 必须先完成完整设备参数纵切面、真实消费者迁移以及 core-only/TCAD clean-wheel 正负例，
  并由未参与实现的审查者确认能力对等和核心无参数泄漏；
- 只有 R5-A1 通过，才允许 R5-A2 删除旧 role/transform/Root 创建入口；删除后再次验证四个真实
  启动入口、旧调用失败、目录摘要和完整回归，并再次独立审查；
- 文本明确 R5-A1 未通过时严禁破坏性删除，R5-A2 未通过时不得进入 R5-B。

这实现了“先证明替代能力，再删除旧权威”，且只是阶段内放行门，没有新增产品状态机或运行时
实体。

## 3. 一致性与范围判断

详细计划、上位计划和索引均仍如实标明：首轮打回、第二轮有条件通过、四项已修订、第三轮审查
前生产实现未开始。该状态与本报告生成前的事实一致；本报告通过后应由上位状态权威记录 R5-0
获准开始，不应回写或改写前两轮历史报告。

四项修订没有改变 R5 的阶段顺序，也没有把 R5-G 扩成三领域 benchmark。部署摘要仍是短生命
周期证明，私有 E2E 目录不是新的控制面权威，R5-A 的两个门也不是新的产品阶段。因此未出现由
本轮修订引入的新矛盾或过度设计。

本轮严格未扩大发现范围；结论不预判 R5-0 或后续生产实现的正确性。

## 4. 验证边界

本轮只使用 7 GiB 地址空间上限下的串行只读检查核对上述三份方案文档与第二轮报告，没有运行
pytest、daemon、Codex Agent、审批 UI、clean-wheel 或 solver，也没有修改生产代码。

## 5. 最终结论

**通过**

允许开始且只开始 **R5-0**。R5-0 完成后必须先取得该阶段的独立书面审查通过，才允许进入
R5-A1；本结论不提前放行 R5-A1、R5-A2 或任何后续阶段。
