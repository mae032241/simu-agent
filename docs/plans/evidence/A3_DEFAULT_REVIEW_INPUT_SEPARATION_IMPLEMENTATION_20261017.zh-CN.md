# A3 正式审查默认输入分离：实施账

状态：**独立静态审查 PASS；root 串行定向测试7项通过。** 基线为 root 已提交的 A2 `804f7a7`；依据[修复计划 §5](../THIN_AUTHORITY_REVIEW_REMEDIATION_20261017.zh-CN.md)。未修改 root 持有的计划或 README。此次不新增角色、任务注册、读取 CLI、曝光账、专属模型配置或权限隔离。

## 实际接线

1. `formal_review.request_route` 成功路由固定中立问题，按原目标/约束检验确切 artifact 的主张、反证、证据缺口和限制。请求方原 `route_reason` 保存在 host request 的 `requester_rationale`，控制原件继续引用原 requester seal；它不再成为 reviewer question/instruction。不可用审查的 A2 failure_key/有限补正与普通替代路由保留。
2. 正式审查的直接材料单独绑定：默认只复制全局原目标/约束和 exact subject，不复制 requester/producer conclusion，不默认挂载全 lineage 页、推荐、其余附件或相邻审计。确切 subject 自身所载主张仍是原字节，不由控制层语义改写；必要证据不足应保留限制/blocked/inconclusive，不能由模板替代科学判断。
3. exact subject 继续经原 `selected_inputs` 形状保 `origin_step/origin_result_sha256/material`，并保 producer seal 元数据。原 `qualification._inputs` 据此建立 producer 边和精确 material membership，来源限制没有因清空 direct_refs 消失；没有按相同 hash 近似补源。minimal history 只保该 seal 元数据，不写默认论证文件。
4. `formal_review.validate_job`、`contracts._validate_inputs` 与 `controller._check_job` 共同核同一绑定；保留原请求/目标/全局判据身份，拒 default history/结论残留。controller retained-route 重放按正式审查的空 direct_refs 验证，普通节点仍核原 parents 结论。普通 A、review return 到普通 A、原 search/selection/history 和 A profile 不变。
5. `native` 沿原专用审查 prompt，明确先证据、原 requester 论证非默认输入以及暴露观测限制。作者/辅助参与者及 compiled slot/author_input 贡献、reviewer 实际 participant、exact subject 的 `require_review` 身份规则未更改，不重新编译被审对象。

## root 裁定的支持边界

- 交付是**默认输入去锚定**，不是盲评或访问隔离。host 原 requester 审计引用保留，不自动再投递到材料包；按需普通文件读取可能暴露其说明，但框架没有完整观测或独立曝光账，状态不能声称“未暴露”。没有新读取工具或权限保证。
- 本轮沿用已有 A `role_profiles`；不同模型不自动授独立资格，同模型也不自动取消。专属审查模型覆盖和受控按需披露/曝光观测后置，由 root 同步计划。
- subject 与 requester 相同时仍保确切 artifact，去掉的是结论/未选附件；同作者不因默认材料变化获得独立资格。相应 source 用例是 host-bound request fixture，不冒称当前普通选择可以选择尚未封存的自有 artifact。
- 没有修改旧冻结工作、旧原件或旧结论。不同输入合同不能借同名任务静默重新封存；原 contract 实现身份包含实际 `contracts` binder，旧合同不自动升级为本轮资格。

## 精确文件与最小负控

| 文件 | 修改 |
| --- | --- |
| `src/scidiscovery/research_loop/formal_review.py` | 中立 question/host rationale、exact subject input binding、严格验证/public scope；冻结实际 binder 代码。 |
| `src/scidiscovery/research_loop/contracts.py` | 正式 review 专用材料/metadata history 分支；原 global/大小/原件校验继续；普通节点不改变。 |
| `src/scidiscovery/research_loop/controller.py` | `_check_job` 正式 review 空 direct_refs 的唯一必要重放接缝。 |
| `src/scidiscovery/research_loop/native.py` | 专用正式审查 prompt 明示默认分离与非盲评边界。 |
| `tests/research_loop/test_formal_review.py` | 原无模型 native launcher 在 requester summary/result/route_reason 放强倾向 marker，核实际审查 prompt/task/inputs 不包含它；保原实际 identity/作者重叠/unknown/require_review/二次 controller.run 保护。加两个小 source 用例核 exact producer 边篡改及 subject=requester 仅 artifact；普通 A 仍拿到父结论。 |

仅以标准库 AST 解析5个 Python 文件及嵌入式 launcher，逐行尾空白检查通过；未使用 Git 命令，未执行项目 import、测试/collect、构建/安装、CLI、模型或服务器。

root 后续最小 source 目标：新增两个输入边界用例及原 ordinary A 用例；最小 process 目标：原成功正式审查（含第二次 run）、原作者重叠和原未知身份用例。A2 不可用路由原保护仍保留，是否复测由 root 根据剩余风险唯一串行决定。静态审查不证明观点独立、访问隔离、真实模型或 solver 资格。

## 实际验证

独审见 [A3审查](A3_DEFAULT_REVIEW_INPUT_SEPARATION_REVIEW_20261017.zh-CN.md)。root使用既有资源监督器与base Python，唯一串行执行：

- source：本文件所列两个输入负例、ordinary A不授资格，以及 `test_native_execution_inputs.py::test_public_compile_exact_review_and_existing_run_keep_native_original`，4 passed，监督5.642秒。
- process：正式审查成功及重放、同作者拒绝、未知身份可合法改道三项，3 passed，监督8.165秒。
- 日志：`.trial/authority_remediation_20261017/a3-source`、`a3-process`；峰值143745024字节（约137.1 MiB），无内存止损、清理完成。未安装、未跑真实模型/solver/远端作业；不证明科学观点独立或生产隔离。
