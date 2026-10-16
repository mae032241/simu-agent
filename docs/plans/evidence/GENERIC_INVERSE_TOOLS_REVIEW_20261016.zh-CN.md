# 通用逆问题工具链独立审查（2026-10-16）

结论：**有限工程 PASS**。最终源码验收与隔离 wheel 安装验收支持：通用任务可使用默认 `local_execution:command` 完成真实执行、指标及输出读回、失败留档、原件归档和复现。未发现此范围内的剩余阻断缺陷。本结论不表示科学任务完成，也不表示通用候选选择、shortlist、独立外审或所选方案交付已闭环。

## 精确范围与审查方法

审查基线为 `dev` 的 `e748d2a48eeeac5781ec51f635213274627b4364`，对象为新增的 `tests/fixtures/generic_inverse/{objective.md,generate.py,run.py,native.py,README.md}` 与 `tests/research_loop/test_generic_inverse_tools.py`。本轮行为改动没有修改框架源码。`docs/plans/REMAINING_FRAMEWORK_BUGS_20261016.zh-CN.md` 由根代理维护，不属于本报告的待测行为。

独立审查者未编写被审行为，按 `scid-cross-boundary-review`、`scid-change-scope-checks` 只读检查实现与执行原始证据；未重复启动验收负载、未调用模型、未提交或推送。审查后仅写本报告与 `/tmp/scid-generic-inverse-independent-review-20261016.md`。

最终执行文件 SHA256：

| 文件 | SHA256 |
| --- | --- |
| objective.md | `585f208206826e490e40a0239da0fdf7f07625ffd7702de1b39d7297ac8d2822` |
| generate.py | `a9c6d3f2df90f20a5de36a8a8f29ff69acf99e0eeb0ca51257aef4bc97383564` |
| run.py | `561da5593ebc918baa73ced1df53b6092a092cb7ef37e380b0febeae2bca7fff` |
| native.py | `490e84fa2e18ac0853462dfaa66d03f9903bbd9c9137433394a123db449db4df` |
| test_generic_inverse_tools.py | `6bf45de5c131d706c0ca98c0c33ecc1cb2fa87b3dd3a3ede9827b9d2cb9a53cb` |

## 数学与科学口径

生成器构造八维独立零均值高斯潜变量，观测为 `y = diag(a)x + Gaussian noise`。训练/源验证/公开目标压力集分别为 128/64/64 行；源条件衰减与噪声为 0.12/0.025，目标条件为 0.48/0.10。标签、生成程序及 seed 20261016 全部公开，没有隐藏 reward 或目标测试集。

`source_linear` 的每维斜率为训练集 `sum(x*y)/sum(y*y)`；`operator_ridge` 仅用源训练标签估计潜变量二阶矩 `v`，然后使用公开的对应条件算子与噪声计算 `a*v/(a*a*v+noise_variance)`。在声明的零均值高斯模型下，这与线性后验均值形式一致。验证/压力集标签仅进入 MSE 计算，没有进入参数估计或预测权重。MSE 分母为样本数乘维数，指标显式声明 evaluation_key、min 方向与单位，输出禁止非有限 JSON 数值。

最终 objective 只描述科学问题、可用信息、约束、决策与选定可跑方案的交付完成条件；故障注入及 scripted 验收限制放在 README/native 中。当前 scripted A 仅机械读回、比较测量值，不完成 objective 中要求的科学选择与交付。

## 跨边界核对

检查了 prepare/run → native 配置 → experiments 冻结与接受 → LocalExecution → history 归档与校验 → A 输入挂载 → controller export-only。LocalExecution 真实调用 `subprocess.Popen` 执行已接受的输入快照，收集通用 version-1 结果；未使用 cov 执行器、cov 科学 helper 或模拟执行结果。

第三次真实进程在产出结果前非零退出，记录为 `known_failed`、result missing、空指标。成功执行后原 Worker 输入被故意修改；复现读取同 instance 的内容寻址归档原件，输出仍逐字节一致，因此确实区分了归档原件和可变工作文件。A 按返回的 next_page 遍历索引，读回两组成功产物并生成明确标记 scripted、not_a_candidate_selection 的比较。controller 再次 run 及 export-only 未重放既有调用。

## 实际验证

源码执行者使用 serial_lock 与资源监督运行：

```text
python -m pytest -q --tb=short -p no:cacheprovider
  --basetemp /tmp/generic-inverse-source-complete-20261016/data
  tests/research_loop/test_generic_inverse_tools.py
```

独立读取最终 pytest.log、resource.json、acceptance-evidence.json：**1 passed in 4.88s**；监督 elapsed 5.168s、exit 0、cleanup_complete true，观察进程树 RSS 峰值 238952448 bytes，无内存停止触发。

安装版从当前源码离线构建 fresh wheel，在隔离 venv 中执行。单独测试目录只复制新 test、execution_fixtures.py 和 generic_inverse fixture，不复制 src 或 conftest；清除 PYTHONPATH，以 `python -I -m pytest`、空 pytest.ini 与 `-o pythonpath=` 运行。独立读取安装身份、驱动、日志和结果：**1 passed in 4.38s**；监督 elapsed 5.224s、exit 0、cleanup_complete true、RSS 峰值 257630208 bytes，无内存停止触发。离线构建/安装 elapsed 2.89s、exit 0、cleanup_complete true。安装身份显示 core 来自 venv site-packages，239 个包源文件逐字节比较无 mismatch；上述执行文件 hash 与源码轮相同。真实已安装 `scid-research`、`scid-experiment` 入口的 help 亦通过。

两轮均记录 `models_called=0`、`scientific_reasoning=false`、默认 local、关闭 search、H/W/A scripted 传输、两次成功和一次失败；所有列出的原件与输出均 archived。两次成功执行均从归档重建并得到字节一致输出。export-only 返回 `exported_unsubmitted`、`goal_completion=not_asserted`，未创建外部 delivery intent。

| 机制 | 源验证 latent MSE | 公开目标压力 latent MSE |
| --- | ---: | ---: |
| source_linear | 0.0013139373292748334 | 0.041736076073297115 |
| operator_ridge | 0.001290131484667631 | 0.02788145683209644 |

本公开 fixture 的两组排名一致，operator_ridge 的 MSE 均较低。这是确定性公开测量，不是隐藏泛化资格或模型作出的科学选择。

审查者执行 `git diff --check` 通过；新增文件直接逐一阅读。未运行全套测试：本轮没有框架源码改动，定向源码与安装检查已覆盖所声称的工程行为。

最终再次核对验收方归档的 `GENERIC_INVERSE_TOOL_ACCEPTANCE_20261016.{json,zh-CN.md}` 与 README：指标、资源状态、安装身份及能力缺口与已读原始证据一致；README 已限定同实例归档复现。执行文件 hash 保持上表值，可以冻结本范围。

## 已修正问题与剩余范围

初稿存在科学 objective 混入故障停止规则、未报告排名、config 字段假设错误、10s 声称与实际 60s 配置不符的问题，均已修正。最初错误假设重复 experiment run 幂等也已移除；新的 run 会接受新执行，query/lookup/collect 才是只读恢复。首轮 A 因仅读第一页而漏掉第三条失败记录，最终按 next_page 遍历后通过。这些是 fixture/验收脚本问题，没有据此认定核心框架缺陷。

仍未证明的范围：

- 复现从 export-only 后同 instance retained archive 读取；未证明独立 export 包或迁移复现。
- scripted H/W/A 不证明真实模型理解、提出新机制、科学取舍、通用候选绑定/选择、shortlist、独立外审与所选方案交付。
- 公开压力标签不支持隐藏 reward、未观察分布或现实世界泛化结论。
- fixture 不在 core wheel 内，安装测试是显式复制 fixture；未验证发行包对任务材料的收录，也未覆盖其他平台矩阵。
- 未运行 live platform、真实 solver 或浏览器流；本轮声明不涉及这些能力。

完整本地原始证据保留于 `/tmp/generic-inverse-source-complete-20261016` 与 `/tmp/generic-inverse-installed-20261016`；临时路径不构成持久发布产物。
