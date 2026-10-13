# Rootless launcher fresh-context片段独立审查

状态：**PASS，限定为冻结的 new_context rootless 启动接缝及无模型机械验收**。最终权威为 `/tmp/scid-u4-launcher-03.json` 三文件；独审读取实际源码、测试和父代理运行证据并核对三文件 SHA 全部 MATCH。独审不编写生产/测试，不运行 tests/build/Git/真实模型，仅维护本记录。

## 本次范围

父确认本场仅new_context，output_repair=False；same_session/resume在此rootless实现显式unsupported，不以通用fake runner的resume结果称此launcher或真实Codex恢复已资格。通用resume policy本场只用于冻结launcher/turn-scoped合同，是当前fragment准备依赖，不授真实resume能力。

独审发现实际rootless native_args仍拒resume、且仅允许origin输出目录，U2/U3通用假native片段通过不能替代这个生产入口。最小修仅launcher脚本与必要测试，不新建执行/预算状态账本或放宽原profile权限。

上述缺口是本次修复前状态。最终实现将 fresh exec 输出绑定到原 accepted attempt；用户最新要求先测试此最小修复。通用 native attempt/argv 校验仍位于 cov 启动脚本，其与领域环境配置的职责归位作为后续架构事项，本次未实施，也不以此 PASS 声称已完成通用 launcher 整理。

## 必要接缝合同

- 输出必须exact最新accepted native attempt的result.pending.json；不接受任意filename/子目录、旧attempt或另job。job/workspace/role与冻结原件匹配，schema使用origin的冻结current schema。
- nativehome为该accepted intent的execution.home；new_context仅允许fragment与已冻结new_context策略，不默许same_session失败后轮换或重发。
- 既有outcome拒绝重复launch；缺outcome的原native执行unknown不作新的fresh grant。保原runner/native process owner与唯一dispatch，不能仅凭最新intent字样判断恢复可重提。
- 真实launcher namespace无模型验收须经过实际main/prepare_home/outer/bwrap，不接受只绕过入口调用fake runner。普通fresh origin流程保原profile参数及权限。

## 最终源码与语义结论

`accepted_attempt` 复用原 `execution.records/home/identity`、`continuation.validate_task` 与 `runtime.process_matches`。最新 record 的输出、原 job digest、角色、workspace、native home 和 origin schema 必须匹配。已存在 outcome 或 pending 输出拒绝重新 launch；runner PID 必须为当前 launcher 的父进程，原 native-process PID 必须为当前 launcher。本次两秒等待仅覆盖 Popen 后 exact child receipt 的发布窗口，位于准入锁外，不等待模型。

`main` 在准备 home、材料和 namespace 前完成上述校验；随后沿原 cov 配置和隔离挂载执行。默认故障路径在 `output_repair=False` 时不自动调用 same_session 修复；显式 `resume` 被拒绝，无 fresh 重发回退。缺 outcome 的另 PID unknown 不能因 intent 为最新而获重提资格。

最终三文件 SHA256：

| 文件 | SHA256 |
| --- | --- |
| scripts/acceptance/rootless_cov_launcher.py | `88b6a2ae0d15620c3848cc567c5f4305f041e1742ac7abc3f17447cb823134f4` |
| tests/research_loop/test_rootless_fragments.py | `9a72cbcf8cfc1b85adb336a61f543048614bbc05ea578e85f4cb92fe8ba7dd0b` |
| tests/research_loop/test_rootless_fragment_namespace.py | `28af37a272b296ebddfe72b465c6d9a4a36270fbf8c27b92872161b89042e0e1` |

## 运行证据与边界

- 父代理源码 parser 门禁：10 PASS，0.93s，[日志](../../../../../.trial/u4-launcher-source-01-20261013/batch-001/pytest.log)。覆盖 exact new_context、旧 attempt、任意子目录/文件名、错误 home/role/job、另 PID unknown、终态重提及 resume 拒绝；负控验证拒绝前后文件原字节不变。
- 父代理 wheel05 安装门禁：11 PASS，3.08s，无 skip。[运行日志](../../../../../.trial/macro-role-installed-20261012/artifacts-u3-05-20261013/u4-launcher.log)及[结果原件](../../../../../.trial/macro-role-installed-20261012/artifacts-u3-05-20261013/u4-launcher-result.json)记录 returncode=0、安装模块路径/SHA 与 model_requests=0。使用已资格 wheel05，SHA256 `f71d793a28fc942d41432c3e8c45eeed190790fdc74524c5ce0cbe67547eeab9`；该补丁修改独立脚本，无包内生产模块变更。
- 真实 namespace 用 `native.execute_native → launcher.main → prepare_home/outer → bwrap` 执行两个 synthetic native contexts。首片经实际注册 cov CLI 提交一次，二片查询同一原 call；断言同 job、同 stage scope、不同 native attempt/home/thread、累计 usage=2、只一个 accepted experiment、最终 stage seal。入口后的 fake native 从真实 `-C` argv 获取 workspace，不依赖已由 namespace 清除的 host 环境变量。
- 首次 fixture 将被 clearenv 清除的 THIN_HWA_WORKSPACE 当作 native 输入，且 session 字符串需真实换行；修正仅在 namespace 测试，launcher/parser 冻结字节未变。这些试验错误不计入生产能力结论。

无剩余本场生产阻断。最终 PASS 仅为本次 new_context namespace 机械接缝，不授真实 LLM、真实 same-session 恢复、TCAD 或科学效果资格；不声称 shell 软隔离防恶意绕行，也不将本次 synthetic session 当作真实 Codex 恢复证据。
