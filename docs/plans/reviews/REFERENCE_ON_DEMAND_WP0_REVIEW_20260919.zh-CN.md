# 按需取证 WP0 精确合同独立审查

结论：**PASS（WP0合同审查）**。本轮复核采用收到修订后的最终候选；四项已定位缺口均已在合同层关闭。R4方向不重审，WP1不受影响。PASS不表示实现、安装后端或并发验收已经完成。

候选：`REFERENCE_ON_DEMAND_WP0_CONTRACT_20260919.zh-CN.md`，最终SHA-256 `783c0e8b02aa92099f250ab574f2b0ca18b1b696cc69d96be275d7a714472e17`（初次候选为 `a0795941b58c2a1360f026d2c626b0c07e1100678fa6f6fe88ef6fae56cc84c3`）。静态核查当前源码；仅写本文件，未修改代码/计划、未测试、未调用科研MCP、未恢复Fig4。

## 本轮缺口及修订关闭

| 初次候选问题及真实代码依据 | 最终候选修订/判断 |
|---|---|
| `run_outputs.py:214`只将context_sources内的来源交给context_validator；catalog又只允许真实输入端口。仅扩Schema枚举会出现“能引用却拿不到字节”。 | 第3节明确operation_contract与run_outputs共同消费编译能力派生的合法工具来源集合，不伪造输入端口。**关闭**。 |
| `_evidence_manifest`目前父链只有inputs和生产records，而prior_analysis_sources要求每个binding Ref属于manifest父链。 | 第3节明确新manifest父链包括准确accesses Ref并去重，不改旧对象/旧manifest父链。**关闭**。 |
| source_key是科学键，不一定是原输入alias；现有analysis_source_claims/analysis_evidence_aliases已有映射语义。 | 第2节先经source_references映射科学键，直接alias/input_digests只在原manifest准确配对。**关闭**；未支持的自由文本/locator仍给缺口，不推测。 |
| 128次访问与ToolAttempt及恢复证明既有64次上限冲突。 | 第1节明确record_attempts=False，访问请求使用同控制账本的自身收据，不占计算attempt证明槽。**关闭**；需保持访问128次、生产attempt64次各自边界，不能混写两种证明。 |

## 非阻断实施注意

- 同Ref不同范围是不同提供事实，但来源别名应在明确作用域内稳定复用；不要机械地每页生成新来源。当前prior_analysis_sources对同Ref匹配多个当前别名会拒绝，故跨轮解析须按原根/别名作用域消歧，不能字典覆盖。加入“同Ref两范围→封存→下一轮解析”反例即可，无须新身份体系。
- 结构化source_key能通过原生产绑定精确认定时可导航；无法匹配且无source_references映射时应如实未解析。初版支持哪些locator规则以编译提取器声明为准；不要无声声称已支持现有全部引用格式，也不要扫描自由文本猜引用。至少以新calculation_ref证据路径和source_key不同于input_alias的报告各验一次。
- 关闭record_attempts后，reference_read_reserved/settled及accesses成为本能力的唯一访问事实；失败、取消和响应丢失也必须沿该路径计量，不触发“declared tool omitted outcome receipt”的计算attempt分支，不另外生成计算attempt。

## 已可实施的部分与非阻断约束

- **同库存储与并发：** run_tool_evidence已有(run_id,ordinal)主键及(run_id,evidence_key)唯一约束，run_activity在同一RunService数据库。短事务内查询恢复作用域、预留、去重检查、写访问记录和结算具备可实现基础。contract已正确要求全部记录分配ordinal、事务外IO、提交时复查生命周期。无需新状态机或全实例IO锁；事件预留ID/结算唯一性及同scope多连接反例属于实施验证。
- **生产/访问分离：** tool_evidence默认过滤生产记录、accesses独立集合、原Ref不重登记是合理最小方案。需覆盖所有当前按“每条记录均为产物”处理的调用者，尤其snapshot、恢复、计数、发布及completed_for_output；合同已列明此责任，未要求另建表。
- **两种后端：** HardenedWorkerMCPRouter继承LocalWorkerMCPRouter，非文件编辑工具走super调用，公共OperationToolContext/RunService入口可复用；无需重复读取实现。Hardened自身transport_guard必须保留。非文本物化入口必须在实际所选后端可用，不能仅返回服务端不可访问路径；以安装接口和图像/二进制小fixture核查，不能凭同handler认定已验证。
- **版本与预算：** reference策略必须加入catalog的worker_tool资源digest（目前仅含接口、capability、services、evidence_ports、network_access、record_attempts等）。内部根/manifest读取及响应总JSON预算要求合理；范围、材料成本、调用次数分别计量，不能把只返回索引当免费大原件读取。
- **职责与收益：** 不推断科学必要性、不要求全文已读、不继承资格；源字段和科学键解析是机械身份解析，不是新科学判断。token收益仍须完整任务配对测量，当前无实测结论。

最终候选已把必要合同落到明确消费者与存储边界，可以按合同实施WP2并接受定向实现审查；未发现需要再新增状态机、历史关系服务或全文阅读门的理由。记录字段、具体索引及函数组织由实现承担，已约定的权限、计量与原子性不得在编码时放松。
