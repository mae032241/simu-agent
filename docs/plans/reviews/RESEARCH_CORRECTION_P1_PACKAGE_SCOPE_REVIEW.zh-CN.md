# P1 单 case 包装失败的范围审查

日期：2026-09-08。有界结论：**这是新增包装正控揭示的既有缺陷，不是 P1 引入的回归；当前证据不足以要求立即扩大 13 文件范围。** 该缺陷也不能被“Fig.4 是多 case”一句话排除。应保留失败证据，并用当前 declared-source.v2、每个计划 case 均有实际 deck-scoped binding 的路径完成真实 Root package 正控。正控未完成前，不能宣布 P1 包装链已验证。

本报告只判断此调用链的归因和必要范围，不是 P1 全实现 PASS；未修改计划或生产文件，未运行 pytest、wheel、solver 或真实 MCP。

## 1. 精确证据与归因

候选日志 [p1-package-pytest.txt](../evidence/research-correction-continuation/p1-package-pytest.txt) 的 SHA256 为 `e37242cb2672aafb05a24bd22ecea830a07f13383a3f5ed1178040e62cbb52ed`：新增用例经过 author/review 提交，package preflight 接纳，在 invoke 的确定性执行中报 `missing_control_binding: planned case has no declared source anchor`。

[p1-package-original-verified-pytest.txt](../evidence/research-correction-continuation/p1-package-original-verified-pytest.txt) 的 SHA256 为 `25cb4d3a1eeaebc50e0116346ef7ef7d485fee3ff7ca0be41ff1d0cd8ec11733`。实施者以冻结 P1 前模块执行同一个新增 package 断言，得到同一堆栈和错误；日志核验的 plugin.py 摘要 `485410d461f04ebc702803576acf23ef823ad1396bc053446e4928abba672041`、project_packager.py 摘要 `92bd0b1aa807c68812d1c96b82080be090d43afeb707aae7564b0582dab4a547` 均与已冻结源码清单一致。本审查读取该日志，没有自行重跑。

同时独立复算两个实际故障文件，均与 [源码基线](../evidence/research-correction-continuation/source-baseline-2026-09-08.json) 完全相同：

| 文件 | SHA256 |
| --- | --- |
| `plugins/tcad_artifact/tcad_artifact/transform_adapter.py` | `9050ff406bb833019dd887c231e8e063abde55174f56f15bacc176eb8aebeb8c` |
| `plugins/tcad_artifact/tcad_artifact/project_materializer.py` | `5cdbc87c4701f790b94d01a433ba8a6f70a4c1ff381b0511856632268c35699f` |

P1 的三个 TCAD 文件和 test_l4 正在修改，本报告不把它们的活动工作树认定为完整冻结候选。基线复现加上述源码归因已足以排除“此 missing anchor 是 P1 负面审查放宽引入”的判断。

## 2. 具体调用链及适用范围

1. `test_l4_local_tcad.py:143` 的 `_portfolio` 是无 comparison_contract 的单 case 工程烟测；`:1268` 的测试原本验证 SProcess declaration、preflight 和 initialization。新增 review→package 断言位于读取时的 `:1313`—`:1344`。
2. `project_materializer.py:323` 要求每个计划 case 都有原始 declaration anchor；`:404` 开始生成 case_parameter_bindings，但 `:407` 遇到没有 comparison_contract 的 proposal 即跳过。因此作者可凭有效 anchor 物化、提交项目，正式项目中的 case_parameter_bindings 却为空。
3. `transform_adapter.py:138` 的 declared-source.v2 重物化分支在 `:156`—`:176` **仅从 case_parameter_bindings 恢复 case_anchors**；没有其他原 declaration anchor 来源。工程单 case 的 anchors 因而变成空列表。
4. package 调用 `materialize_deck_project` 后，后者在 `:339` 检出计划 case 无 anchor，并在 `:402` 抛出错误。这发生在独立审查已通过后的确定性重物化阶段，与 P1 的负面报告条件拆分不同。

缺陷的准确适用条件是“某个计划 case 没有可从 case_parameter_bindings 恢复的 anchor”，不只是单 case。科学多 case 若所有变量仅属于 analysis/diagnosis/scoring 等非 deck 范围，同样可能触发：过滤规则位于 `project_packager.py:1401`，materializer 在 `:409`—`:417` 只为 deck-scoped 变量的 case expectations 生成绑定。

反之，若每个计划 case 都有至少一个此类绑定，当前算法可以为每个 case 恢复 anchor，因此不会因为这里的空集合而必然失败。但后续还有精确重物化比较（`transform_adapter.py:195`）和包装门禁，**不能仅凭集合覆盖推断 package 已完成**。本次未检查 Fig.4 的最新实际科学计划内容，不能将上述条件宣称为该案例已经满足或不满足。

## 3. 最小处置及必须保留的正负控

**目前不扩生产范围。** 保留候选及冻结基线同错的证据，恢复原工程单 case 用例的原测试职责，或另行明确记录该已知缺陷；不能把这个失败抹掉后声称工程单 case 已可包装。

包装正控应采用有科学意义且具有完整 case binding 的当前 declared-source.v2 工程 fixture，经实际 Root operation_invoke 到 reviewed_package 完成，读回产物并核对确切 project/review/capability/plan 关系。可在当前已有 test_l4 范围构造工程验证 fixture，不向真实研究计划增加无意义控制量来迁就测试，也不篡改生产 profile、手写 materialization_report 或注入假 anchor。

**现有 SDevice author→review 正例不能直接替代。** 读取时的 `_project`（`test_l4_local_tcad.py:238`）没有 materialization_report；package 在 `transform_adapter.py:127` 明确要求该报告。仅把用例名称或 solver_kind 换成 SDevice 不证明可包装。若另有完整、当前、真实可包装的 SDevice 产物，执行到底可证明共享审查/包装边界；但不能单凭它证明 Fig.4 所需的 SProcess v2 重物化链。

继续保留以下原验收义务：

- 相同实现缺陷伪造 pass 的提交仍被拒绝；有据负面报告可以封存。
- 非通过项目/报告尝试 package，在真实 preflight/invoke 被原资格门禁拒绝；不得让输入身份或 review subject 错配获得通过。
- 当前正常项目必须真的完成 package invoke，不能只断言 preflight admissible、author/review completed，或用预先组装 ReviewedDeckPackage 跳过该 Transform。

如果完整 binding 的当前必需 SProcess 正控也无法完成，或科学 Agent 实际选定的 Fig.4 本轮计划确实含无法恢复 anchor 的必要 case，则**必须停止宣称本项完成，按已批准计划的范围变更规则补充具体最小修订并独立复审**。那时这是本次目标需要处理的真实路径阻断，即使它早于 P1 存在，也不能以“既有问题”为由略过。当前这个单 case 反例本身尚不足以作此扩大决定。

## 4. 本次检查

只读核对候选/基线失败日志、两个故障模块摘要、单 case fixture、materializer→package 数据传递及直接相关门禁；没有运行任何测试或外部执行。按已读跨边界与最小化技能，结论限定为：**保留既有缺陷证据，先完成当前受支持且贴近必需链的真实包装正控；当前无需立即修改计划外生产代码，也不能提前给包装实现 PASS。**
