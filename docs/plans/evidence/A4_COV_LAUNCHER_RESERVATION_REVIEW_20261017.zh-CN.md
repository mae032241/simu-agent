# A4 Cov 实际启动配置：独立审查

结论：**静态 PASS，可运行冻结的3个 source 实例。** 基线 `21410f9`；范围为仓内 Cov launcher、`cov_lineage.py`、`test_rootless_fragments.py`、ROOTLESS_CLI说明及本节点实施账。未改 Local、预算 owner、已接受调用或私有历史场。

## 实际配置链

`scripts/acceptance/rootless_cov_launcher.py` 的 load 校验 operator 字段，main 将 `engineering_reserve(s)` 真正传给 `cov_lineage.configure`，后者通过已有 `experiments.configure/freeze` 绑定 `engineering_check_reserve_seconds`。这不是只添加未被消费的说明字段。CovExecution 已有数值校验、能力摘要和原 accepted deadline 分配消费，无需新增执行协议。

新 launcher 副本默认15秒，显式0禁用；非0须有限且在(2,65)内，bool/NaN/inf拒绝。configure默认0且0省略字段，保留旧配置形状；旧reader允许可选键并复用现有类型校验。原65秒总额及共享额度不增加，旧 accepted/freeze冲突不被回填。

启动与 exp run 的 stderr 只报告请求上界：实验最多50秒、检查最多10秒及2秒反馈还受原任务余量裁剪；actual reserved/unavailable 仍来自 accepted 的 engineering_check。backend_file 没有对应能力时明确不承诺切分。没有增加 allocation 文件、余额、必需插件接口或额外检查 grant。

## 负控与检查范围

新增15/0两个实例走真实 configure/freeze/load、能力摘要和原 record配置；第三项拒绝非法窗口并核 unsupported channel 提示。若实际 forward/冻结遗漏会失败；它们不声称执行训练或采样检查。复用原小型 accepted/registry fixture，不创建安装环境或模拟模型服务。

独审发现新用例参数 initially 缺 `execution_registry` 注册；作者已一行显式导入该fixture后重新冻结，避免 fixture-not-found/宿主环境依赖。该最终增量已复核。没有要求重新跑A4进程矩阵，默认/旧accepted/unknown不重放仍以原A4证据范围解释。

只做文本/调用链/Git只读及限定diff空白检查，无诊断。未运行测试、收集、import、launcher、安装、模型或真实Cov；真实训练、检查时机及平台权限资格未由本节点证明。可由 root 唯一串行运行实施账的3个新增 source 实例，不需安装或全组重跑。

## root 定向执行证据

独立只读核对 `.trial/review_reserve_followup_20261017/cov-source/batch-001/pytest.log` 与 `resource.json`：3 passed，pytest0.67秒；监管0.974秒，returncode0，峰值58,359,808 bytes（55.656MiB），cleanup_complete=true、memory_stop_triggers=[]、received_signals=[]。3个实例均来自上述新增source目标，未安装/运行训练或模型。结果与本节点静态判断相符，可独立提交；采样不是硬内存保证，不能据此补授真实Cov训练/采样检查资格。测试由root唯一执行，审查者只核已有证据。
