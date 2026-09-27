# 编译合同盘点与本轮切片

CONTRACT_INVENTORY.json 来自修改前实际编译目录：默认组合 45 项、含 figure 组合 50 项，以及 Root 和 lifecycle 原声明。它只记录运行声明与组件引用，不作为另一运行注册表。

| 边界 | 唯一来源与消费者 | 本轮处置 |
|---|---|---|
| 输入准入 | InputPortSpec/InputAdmissionSpec/InputValidationSpec → catalog、preflight/invoke | 保持单入口，诊断增加位置，不接入 submit |
| 工具参数 | WorkerToolDefinition.input_model → catalog/tooling → Root/Local/Hardened | C1 已统一 JSON 类型语义与静态投影，移除 facade 的 strict=False 副本；P1 增加安全详情 |
| 输出合同 | OutputPortSpec 资源与规则 → operation_contract → assignment/run_outputs | C1 已冻结静态基础合同，动态实例化只复制，不改共享对象；保留既有投影版本身份 |
| Root/lifecycle | RootTool 和 lifecycle.py 现有声明 → MCP | 使用相同参数解析及诊断规则；不转为科研 Operation |
| 评分失败 | 两个评分工具 → Run activity → 清单 → 分析 | 可信尝试、无计算记录时的受控快照、类型化内部 request 已接入，既有 computed 计算重放保持 |
| 恢复与案例 | 原收据/明确输入描述符 → 工具、上下文、重放 | 清单分别承担当前/历史证明，案例依据通过共用解析核对；失败续接与第三轮读取已正式提交验证，原字节权限不扩大 |
| 分析判断 | LayeredDiagnosisReport + 三种分析 Operation | 已移除全局强制传播与错误 source_key 枚举；决定性成功仍要求实际必需检查证据，预计算角色禁止新增计算 |

编译绑定和已列入口已核对；P2—P4 语义已按具体消费者做正负例与独立代码审查；不能用编译通过宣称所有科学判断正确。现有自定义模型与 SemanticRuleViolation 的消息由其组件负责静态、可公开的说明；框架不转发 ValidationError 的输入值、未知工程异常文本或任意字段键。

最终静态盘点见 FINAL_CONTRACT_INVENTORY.json，与原盘点分别保留。完整默认/figure 目录均已从安装 wheel 核对身份；变化范围及准确 agent_type 见 CONTRACT_IDENTITY_DELTA.json。实际测试通过与旧 Hardened 夹具限制、未运行的现场 P6 分别记录在 EXECUTION_RECORD.zh-CN.md，未将历史失败改写为成功。
