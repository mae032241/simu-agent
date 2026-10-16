# 独立线性逆问题通用工具验收

受测核心提交 `e748d2a`，仅新增独立任务 fixture、一个定向测试及本报告。未修改生产控制面、模型 schema、cov adapter 或旧试跑材料；未调用模型、网络 solver、增加预算、commit 或 push。

科学题目在 `tests/fixtures/generic_inverse/objective.md`：8 维对角逆问题，固定种子 20261016，128 条源训练、64 条公开源验证、64 条**公开目标压力集**。目标条件衰减和噪声同时增强，所有标签均公开，无隐藏 reward。两机制是仅源训练拟合的逐坐标线性逆映射，以及使用公开算子/噪声和源训练先验方差的 ridge。目标标签只用于测量，不用于拟合。

| 机制 | 源验证 latent MSE（越小越好） | 公开目标压力 latent MSE（越小越好） |
| --- | --- | --- |
| source_linear | 0.0013139373292748334 | 0.041736076073297115 |
| operator_ridge | 0.001290131484667631 | 0.02788145683209644 |

两口径下 ridge 均较低；这是脚本记录的公开比较事实，不是模型科学推理或对隐藏分布的结论。目标条件的 gap 为后续改变逆算子、正则化或噪声假设提供可测问题。

## 已通过的范围

真实 research CLI prepare 默认冻结 `experiment_mode=local`；未显式选择该 mode。search 明确禁用以隔离执行测试。真实 controller 驱动脚本化 H→W→A，W 通过标准 experiment CLI 与 `local_execution:command` 启动两个成功进程及一个显式失败进程，单脚本秒级。已有 version 1 结果格式携带指标、evaluation_key、min 方向和成果标签。

- 精确数据、脚本、objective 和 argv 被快照；执行后改变 Worker 原目录不改变封存输入与成果。
- A 跟随实验索引 `next_page` 读完两页、三条记录，从正式挂载成果读取两方案预测和机制身份。失败保持 `known_failed`，结果为 `missing`，无伪造指标。
- 对原 call 的 query、lookup、collect 正常；controller 重读不新增调用或改变调用原件。新的 experiment run 是一次新调用，不声称它按脚本内容幂等。
- closeout 返回 `exported_unsubmitted`，`goal_completion=not_asserted`，无外部交付 intent。随后从**同一实例 retained archive**重建两个实验目录，两次复现的全部成果逐字节相同；未生成或声称独立可搬运 export bundle。

## 检查与安装证据

使用仓库 `scripts/run_tests.py` 的 serial_lock 与 run_one 默认资源阈值；完整驱动、日志、原件及身份记录在机器记录标明的 `/tmp/generic-inverse-*` 目录。

实际执行命令（驱动内部持有 serial_lock 并调用 run_one）：

```text
python /tmp/generic_inverse_source_complete_supervise.py
python /tmp/generic_inverse_installed_supervise.py
```

源码目标命令为 `python -m pytest -q --tb=short -p no:cacheprovider --basetemp /tmp/generic-inverse-source-complete-20261016/data tests/research_loop/test_generic_inverse_tools.py`。安装目标命令为 `/tmp/generic-inverse-installed-20261016/venv/bin/python -I -m pytest -q --tb=short -c /tmp/generic-inverse-installed-20261016/test-copy/pytest.ini -o pythonpath= -p no:cacheprovider --basetemp /tmp/generic-inverse-installed-20261016/data /tmp/generic-inverse-installed-20261016/test-copy/tests/research_loop/test_generic_inverse_tools.py`；两者均由监督驱动启动，未裸跑 pytest。

| 检查 | 结果 |
| --- | --- |
| 源码新定向用例 | 1 passed，4.88s；监督 5.168s |
| 冻结核心离线 wheel 构建/安装 | 2.890s，exit 0 |
| 新隔离 venv、安装版相同用例 | 1 passed，4.38s；监督 5.224s |

安装用例仅复制新 test、execution_fixtures 和任务 fixture，测试树无 src 与项目 conftest；`python -I` 加空 pythonpath，实际读取 wheel，真实 console 入口 help 也通过。包文件与构建源逐字节核对，原始数量、wheel SHA、sys.path、插件 entry points 见 [机器记录](GENERIC_INVERSE_TOOL_ACCEPTANCE_20261016.json)。三项监督均 cleanup_complete=true、无内存触发。未运行全套、真实模型或远程 solver。

早期两次用例编写失败分别来自重复 run 的错误幂等假设，以及遗漏两条一页的索引分页；均已修测试驱动，无生产代码修补。安装构建成功后曾因监督输出字典重复 phase 参数而显示失败；保留已写 build/resource.json，只续跑 check，未重复构建。上述预备尝试不计入最终通过证据。

fixture 放在现有发布 builder 已包含的 `tests/` 树中，测试不依赖未发布 scripts 资产；它不在核心 wheel 内。本轮没有重建完整 release archive，也没有修改 release allowlist。

## 尚未完成的科学闭环

本轮 PASS 仅覆盖**执行—结果—成果交接**。当前通用机制没有候选身份、通用短名单/选择、外部审计与选定方案交付闭环；sealed observation 的 candidates 仍为空，mechanism_binding 为 null。A 的 comparison.json 明确 scripted、not_a_candidate_selection。科研 objective 要求选定可运行方案、论证局限并交付复现成果，该完整目标尚未完成；export-only 不授予科学完成资格。不能用工程脚本比较冒充框架选择能力，也不能借 cov 适配器绕过这一缺口。
