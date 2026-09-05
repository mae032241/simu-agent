# R5 E5 请求—物化断裂预修复独立审查

日期：2026-09-05

结论：**拟定方向合理，按本文收紧后的最小边界 PASS**  
方案阻断项：**0**  
生产修改边界：**仅 `plugins/curve_score/curve_score/figure_science_operations.py`**  
阶段含义：**只允许修复并重新审查；不代表 E5 通过。**

## 1. 独立根因判断

这不是 Transform 偶发错误，也不是应当放宽 shared support 科学约束的情况，而是同一 Operation 输出
合同在“Worker 可见规则”和“真实确定性消费者”之间没有闭合：

1. `FigureDigitizationRequest` 的 JSON Schema/Pydantic 模型只验证 shared support 的成员、区间、范围
   和重叠等结构关系；它无法仅凭 JSON 判断图像跟踪后是否真的存在端点和 donor 像素。
2. 当前 `REQUEST_PROMPT` 只说可以声明 shared occlusion，没有告诉 Worker 三项真实前提：donor 必须
   覆盖整个区间、covered 必须在区间两侧保留直接端点、shared 区间只能填 covered 的缺失像素，且
   两侧端点距离必须满足声明阈值。
3. Worker 可见语义合同把上下文规则描述为普通来源身份一致；实际
   `_validate_request_context` 也只执行 `recover_requested_image`。因此真实 Agent 产生的请求能够通过
   Schema、上下文校验并封存，却仍被紧邻的唯一确定性消费者
   `build_digitized_figure_bundle` 拒绝。
4. 现场错误 `shared support lacks covered-series endpoints` 正是上述隐藏的图像依赖约束，而不是来源
   哈希、Run 生命周期或调度顺序问题。

因此根因是 `ROLE-002/AUTH-003` 所要求的模型可见合同与提交/消费行为漂移；不应通过改请求数据、删
shared support、放宽端点要求或在调度器捕获异常来打补丁。

## 2. 最小且闭合的修复方案

拟定方案总体正确，但实现时必须按以下精确形式落地。

### 2.1 同一语义合同公开真实关键规则

继续使用现有 `FIGURE_REQUEST_SEMANTIC_CONTRACT`、现有
`curve.figure.request.source_binding` context rule 和现有 validator 引用；不增加 rule registry、错误码
或第二合同。合同与提示必须明确说明：

- shared 区间 `[left,right)` 的 visible donor 在每一列都有直接跟踪点；
- 每条 covered series 在 `left-1` 与 `right` 均有直接端点；
- covered 在 `[left,right)` 内没有直接点，shared support 只补缺失区间；
- donor/covered 两侧端点距离不超过 `max_endpoint_distance_px`；
- 任一条件无法从精确来源满足时，不得伪造区间或调松阈值；应修正声明，或在身份/标定本身无法闭合
  时返回合法的 `unresolved` 请求。

这些是跨输出与精确图像的语义规则，不应复制成新的 Pydantic 字段约束。

### 2.2 ready 请求复用唯一物化实现验证

`_validate_request_context` 应只做一次请求解析，并按状态分支：

- `ready`：直接以精确 `paper_source` 和该规范请求调用已有
  `build_digitized_figure_bundle`；该函数已经拥有恢复、跟踪、shared support、附件与验证报告的真实
  规则。成功结果可以丢弃，失败统一转换为已有 `SemanticRuleViolation`。
- `unresolved`：只调用已有 `recover_requested_image` 验证精确来源身份；不能调用要求 ready 的物化
  函数，也不能强迫未决请求伪造 digitization 字段。

ready 分支不要先单独 `recover_requested_image` 再调用 bundle builder，否则会对 PDF 重复恢复三次
（提交校验两次、正式 Transform 再一次）而没有增加约束。上述分支使提交校验和正式消费者共享同一
算法事实源，同时把当前额外执行压到必要下限。

完整 bundle 预构建确实会在请求提交时增加一次确定性计算，但在当前 Fig.4 小范围内，它是不用新增
第二套跟踪/预检实现即可保证“可封存请求即可物化”的最小方法。后续若有性能证据，再从同一 builder
内部抽取纯准备阶段；本轮不提前增加新 helper 或缓存状态。

## 3. 必需的最小测试

只补两个针对本缺陷的合同测试，不扩展图类型：

1. 复现本次错误形状：结构和来源身份均合法，但 shared 区间缺 covered 端点；必须由请求 Operation
   的 context validator 以现有 rule id 拒绝，而不是等到 materialize invoke 才首次发现。
2. 使用现有有效 shared-support fixture；同一个 context validator 必须通过，随后同一
   `build_digitized_figure_bundle` 正常产生结果，防止修复退化为全面禁止 shared support。

至少一个断言应经过编译后的请求 Operation 输出校验路径，确认 Worker 实际看到的语义合同含上述
规则、失败详情携带现有 context rule id。单独直接调用 Pydantic 模型不足以证明本次断裂闭合。

E5 随后重跑真实请求 Agent 与物化 Transform，才是安装态效果证据；本轮单元测试不应冒充真实 Agent
验收。

## 4. 明确禁止的扩大范围

本次无需且不得：

- 修改 `FigureDigitizationRequest` 的实体结构或 materializer 的科学端点规则；
- 新增预检 Operation、状态、错误码、注册表、缓存、数据库或恢复协议；
- 修改 Root preflight、Run 生命周期、Transform 通用调用器或 scheduler；
- 为旧的已封存无效请求增加兼容或原地改写；
- 扩展 marker、拟合段、自动遮挡推断、Hardened、UI 或全仓校验重构。

旧请求仍应保持不可变并在物化处失败；修复只保证新请求不能在同一已编译合同下带着隐藏物化缺陷
完成封存。

## 5. 33项约束与奥卡姆判断

- `AUTH-003`：OperationSpec 仍引用唯一 Schema、语义合同和 context validator；validator 再复用唯一
  物化实现，没有新增能力白名单。
- `ROLE-001/002`：Worker 继续选择科学图像、曲线和 shared support；控制层只验证其声明能由精确来源
  确定重放，不替 Worker 发明内容。dispatch、Worker 可见合同、submit 和消费者行为重新对齐。
- `DET-001/002`：端点与缺失像素由既有确定性程序复核；没有让程序替代身份选择或科学结论。
- `TOP-002`：新封存的 ready request 不再出现“上游校验通过、紧邻确定性消费者首次发现同一隐藏
  合同错误”的断裂。
- `EVD-001`：所有验证仍绑定精确 `paper_source` 与恢复图像身份。
- `RES-002`：没有增加重试状态或并发；测试和真实 E5 仍需串行低内存执行。

该方案增加的是几句模型可见规则和对已有纯确定性函数的一次复用调用，删除了隐藏规则造成的反复
试错；相较抽取新预检层或复制 shared-support 算法，它最符合奥卡姆原则。

## 6. 放行决定

按第 2、3 节边界实施后再进行独立代码复审。复审通过前不得重新部署或继续 E5；不得以手工修改本次
请求绕过这一合同缺陷。
