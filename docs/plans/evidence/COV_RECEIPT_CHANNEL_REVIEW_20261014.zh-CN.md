# Cov日志与机器回执通道独立复核

## 最终结论

**PASS，限定独立回执通道及本次零LLM工程资格。** 权威生产为 `/tmp/scid-cov-receipt-production-03.json` 五个文件，测试最终为 fixtures06/tests04，公共runner探针为 smoke01；实际源码SHA全部匹配。安装门禁10个文件的唯一用例合计 **133P/1不适用skip**，来自131项既有通过及两个修复项的补跑，不称一个批次或全仓绿色。审查者只读生产/公开接口，仅修改本报告，未运行测试、构建或模型。

32个实际安装模块已逐项核对：安装字节＝记录SHA＝当前源码。fresh wheel SHA：`2f778e3c361ae32e58bb437f6bdd83f2300becfce8d249806e2af9ef03d52f99`。

## 通过边界

公共runner允许训练/预测输出普通日志，最终将实际rec写入ledger后打印。旧代码整段stdout解析混淆了日志与机器回执；rc0不构成科学身份，未知原件不重放的要求保留。

- Cov窄stdlib shim仅在冻结CLI/runner原路径、SHA及确切AST派发/最终输出点下，限定原main code object、同module globals和精确行，取得实际rec对象。候选自己的print或JSON形状日志不会成为回执；全局builtins.print、公共文件、训练和评分不改。对本次已验证cmd_run，shim直接调用原runner.main并恢复runner导入路径；额外未实现argv变体明确拒绝，不承诺任意CLI兼容。
- 单call `receipt.json` 原子、独占发布，绑定version/call_id/accepted_sha256/source_sha256/row；生成编码与core accepted编码一致。`_receipt/_completed`共同使用此通道，不解析stdout、不猜最后日志或ledger行、不以rc0兜底；仍核确切ledger、source/model、终态、cleanup和transport。缺失/错绑定不授known身份，封存后篡改仍hard integrity。
- stdout/stderr保留为日志与证明。成功上下文实际需要七个基本证明＋model＋completed；lineage有界上限8→9避免静默丢候选。源码沿原32MiB上限流式hash并核size，代码/回执仍有256000B边界。
- generic LocalExecution不引入Cov逻辑，科学schema/协议不变；backend_file只供显式配置的独立生产通道，真实profile失败没有隐式fake或stdout fallback。旧失败scene未恢复、重写或回填资格。

## 独审与实跑发现

独审要求补同module globals守卫、避免256KB错误收紧合法源码、明确拒未模拟flags；production02已完成。实跑发现新增receipt/stderr使候选上下文需要9个proof，旧上限令观察不可用；该边界已修。production03再将receipt读取中的相对import改为绝对import，覆盖observer真实 `-I /abs/cov_lineage.py` 入口。

两项最终夹具修正不降低判据：错误parent测试先同步receipt accepted哈希及completion proofs，使transport自洽后确认科学parent/artifact校验仍拒；原件篡改测试先给只读文件写权限，再保留query/collect hard integrity与不重执行断言。独立receipt篡改、缺失、错run/call/hash、重复包、噪声日志、known failure及大于256KB合法源码负控均覆盖。

## 证据与限制

安装路径相对外层 `.trial/macro-role-installed-20261012/`：

| 证据 | 结果 |
| --- | --- |
| `artifacts-cov-receipt-02-20261014/result/result.json` | fresh wheel/basic实际CLI PASS，H→A→W→A及restart，0模型API |
| `artifacts-cov-receipt-02-20261014/breadth-context.log`及result JSON | 131P/2夹具F/1skip，79.28s；包括namespace、普通local与delivery回归 |
| `artifacts-cov-receipt-final-20261014/breadth-context.log`及result JSON | 两个变更文件23P，8.49s；复用同一安装版本，returncode0，32模块绑定，0模型API |

真实冻结公共runner探针：外层 `.trial/cov-receipt-public-smoke-01-20261014/instance/receipt-probe-result.json`。P/Q各一次common dispatch取得known_success/run-1与run-2，日志866/865B含候选假JSON；独立receipt、W封存、两候选机制归属、9个context proofs及重复验证只读均通过，五个公共输入文件SHA前后不变。该探针没有实际A；A接线由独立fake-native namespace覆盖，不混称真实公共runner/A完整链。

保留source01的96P/7F、初次安装observer相对导入失败、installed02两夹具失败及最终补跑记录。以上没有真实LLM行为、科学筛选质量、隐藏评分、目标达标、token节省或任意恶意native程序隔离资格；普通日志仍受既有传输容量/时间边界约束。
