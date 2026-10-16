# 通用逆问题真实模型场

原始证据目录：仓库 `.trial/generic_inverse_live_20261016/`。

## 当前结果

真实框架 CLI 返回 `delivery_confirmed`，4 个节点 H/W/A/A 全部成功封存。没有重启、自动重试、追加预算或未知用量。实际交付包已独立无模型重放通过：全部交付对象 SHA 一致，三个输出逐字复现；监督耗时 0.094 秒，returncode=0，cleanup_complete=true。

- 独立授权预算：2,000,000 token / 1,200 秒。
- 实际观测 token：796,754（input 780,056 + output 16,698）。cached input 666,240 是 input 子集，不再次相加。
- 授权运行时间消耗：507.021 秒，waiting 为 0；剩余约 692.979 秒。
- H/W：gpt-6.1-sol high；A：gpt-5.6-sol high；default tier，无 fast。
- 运行包为 runtime-v2；源码核对口径为 236 个核心 Python 文件。该包在 0c435f8 加已冻结原 call 修复 diff 上构建，与随后提交 8ab844f 的核心字节相同；不是声称提交后重新构建。

## 执行与选择

W 通过真实默认 `local_execution:command` 仅接受并完成两次执行，共同 observation 保留精确输入、结果与原件。通用层登记两个同口径候选，A003 和 A004 均选择 operator ridge。

| 方法 | source validation latent MSE | public target stress latent MSE |
| --- | ---: | ---: |
| operator ridge | 0.001290131484667631 | 0.02788145683209644 |
| source linear | 0.0013139373292748334 | 0.041736076073297115 |

两种评价的排序一致。A 的科学限制原样保留：只支持公开有限 fixture 的判断；latent variance 迁移、零均值、已知准确 operator/noise 的假设违反尚未检验；训练样本不确定性尚未完整量化。未提供 candidate audit，不把未审计说成通过。

控制层选择并目录交付 `local-96fb3a043a108cedc86d420f56fd7136ce2d4082538bd91b20be66d55c3c3538`。单个 manifest 的六个对象哈希均吻合，包括 runnable `inputs/run.py`、`inputs/dataset.json` 和三个输出；重放命令为 `run.py --method operator_ridge`。这是本地目录交付，不代表外部服务提交。

## 证据与边界

- `final-result.json`：真实 CLI 结果、总用量、预算和冻结完整性。
- `scientific-delivery-summary.json`：逐节点用量及通用执行/候选/交付计数。
- `instance/native-evidence/`：四节点原生原件、seal 和 observations。
- `delivered/`：实际单一交付包。
- `preflight/result.json`：真实 native 的只读公开材料/写工作区/私有与凭据拒绝/网络拒绝，以及默认本地执行、查询和成果读取。
- `preflight/fullchain-result.json`：**scripted 零模型** H/W/A 与目录交付、字节复现门禁；不冒充本次真实模型结论。

旧失败预检和准备草案保留在独立历史目录，未覆盖。零模型夹具先因产物计数断言错误，再因 closeout 重复强读非 direct-parent 原件失败；后者的最小门禁改为 A003 实读六原件、closeout 消费冻结 comparison。实际模型场 A003 有七项 direct materials、A004 有三项，A004 对 W 的 result/method 原件实际读取成功。该差异不用于宣称任意历史材料路径都已全面验证。

本场为本地同步通用工具题，不是跨 TCAD 或异步执行验收；target stress 和标签全公开，无隐藏 reward。真实模型未读取旧实验、隐藏答案或 scripted native 的科学结论。

## 最终监督

两场共用监督进程树最终正常清理，509.143 秒，峰值 RSS 1,231,421,440 字节，无内存触发。总返回码 1 来自 cov 场失败，不代表本通用场失败。本场 controller returncode=0、delivery_confirmed。精确重放证据在本场 delivery-reproduction.json 与 replay-supervision/。
