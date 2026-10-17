# TCAD 完整传输容量补修独立静态复核

日期：2026-10-17。对照 HEAD `500b33d0ad0d6043c2093f4ca0ed7ec3779592aa` 与待提交容量差异。结论：**静态评审 PASS，已修正一项阻断，未发现剩余阻断。** 不等于动态验收通过。

范围仅限 `plugin_runtime/collection.py` 与 TCAD 的 `command_adapter.py`、`project_packager.py`、`remote_runner_py36.py`、`ssh_transport.py`、`transport_logs.py`，以及新 `test_tcad_full_transport_records.py` 和容量补修证据。为核对生产链，另读了未修改的 `transform_adapter.py`、`operation_transforms.py`、`result_analysis.py` 与 debug collection 的相关消费者。P1 和 R0 的实现、测试及批准均不在本结论范围。

未运行 pytest、collect-only、构建、安装、真实 SSH、模型或 solver；未 import 测试模块。只进行了差异、文本和生产调用链静态阅读。本文未把历史失落日志中的执行报告当作最终工作树动态结果。

## 已修正阻断

`TCADRuntimeManifest.error` 原仍限制 8192 字符，但它不是始终有界的 summary：runner 在 `remote_runner_py36.py:653` 截取采集错误摘要后，`:687`–`:689` 可因诊断文件数量/日志触及显式 policy 再追加错误，`:700`–`:711` 将全文写入原生 manifest。其总 JSON 可以仍在管理员 `max_manifest_bytes` 内，而 typed manifest 在 transform/operation admission/result analysis 中提前拒绝，导致已收齐的失败记录无法形成 fail attestation。

现已只取消该完整原生 error 字段的机械长度上限；新测试 `:219` 使用 8192 字符前缀加诊断失败后缀，`:223`–`:228` 保留 fail、全文和原 manifest 字节不变断言。该测试本轮未运行。

`RuntimeAttestation.rationale` 的 4096 上限保留合理：实际 producer `project_packager.py:1827`–`:1830` 始终生成固定短 scope 说明；逐项失败理由在 `RuntimeContractCheck.rationale`，其机械上限已取消。没有据关键词机械删除全部字符串契约限制。

## 链路核对结果

| 检查 | 静态判断 |
| --- | --- |
| 完整协议/诊断传输 | `run_bounded` 默认保留 stdout/stderr 全文；command adapter 额外 8 MiB 拒绝、SSH `_run` 固定 quota、RPC header/request 与 runner request 机械限制被移除。显式 `max_output_bytes` 仍拒绝超限 stdout、按原约定保留 stderr excerpt；timeout/idle/context stop 和进程回收分支未被删除 |
| 传输身份与类型 | command response 的 schema_version/operation/ok/payload 类型检查仍在；SSH `_require_ok`、下载体长度/校验 trailer、descriptor hash/size、runner request envelope 与操作分派保留。不是把大响应无条件当成功 |
| 路径与原件 | command collected outputs 仍在 result root 内、lstat 拒绝链接/非普通文件并分块核 hash/size；runner archive 下载仍验证 root、O_NOFOLLOW、类型、大小/摘要。取消集合数量上限没有删除这些逐项校验 |
| 日志身份 | `preserve_log` 仍用内容摘要命名、排斥链接目录/文件及冲突；复用已有日志时用 size+分块摘要核对，避免额外整份 read_bytes。日志初次输入 raw 仍是完整 bytes，不能声称日志采集全链路流式 |
| manifest→attestation | `TCADRuntimeManifest` 保留严格类型、output_class、非负 size、hash 格式、安全相对路径与名称/路径唯一性。transform 仍读取完整 manifest；operation transform `:35`–`:45` 核对完整 output 数量、顺序和每件 bytes/hash，再进入正式 attestation。checks、missing outputs 与三个计数不再有固定集合容量上限 |
| 失败判定 | `attest_runtime_contract` 仍检查 terminal、每个 supplied payload、expected output、undeclared outputs 和 runtime assertion，最后据任一 fail 生成 fail；模型层仍验证 verdict 与 checks 一致。未声明输出与长原生错误的失败理由可完整序列化，不把工程失败转成 pass。collection_errors 全文留在原 manifest，不要求 scope 摘要复制每项原件 |
| 显式政策 | runner `max_manifest_bytes`、`max_transfer_bytes`，job output/storage/wall/cpu/memory，以及 collection 总/单文件/idle deadline 保留；debug collection 仍显式传自己的响应额度。未改变原授权或管理员额度 |

## 测试与风险边界

新测试的完整字节/大 descriptor/header/request、8193 项 attestation checks、末项 payload 篡改、路径/唯一性与显式 quota/timeout 负控能对应具体截断和误判故障；大输入标为 stress，真实本地生命周期标为 process，微小路径/日志身份检查不再携带大 fixture。stand-in 只证明本地协议路径，不证明真实远端可用。

JSON 请求/响应、manifest 模型、attestation 集合和 `run_bounded` 的 bytes 返回仍需完整内存，某些路径存在多个同时存活的表示。本补丁取消历史机械容量限制，没有实现流式 JSON 或内核资源域，也没有证明 OOM 已解决。外部测试监督仍只是采样；恢复动态执行前仍受事故记录约束。

未复核所有 TCAD 科学 schema、数值模型或全部既有错误分支；本次没有审查安装产物、远端 Python 3.6 实际运行、许可证、真实 solver、平台或全量测试。原容量证据末节已注明重启丢失 `/tmp` 日志、历史用例计数不代表精简后的测试已运行，与本结论一致。

本容量节点可在 R0 收口后按其独立文件范围处理；不能凭本报告把 P1/R0 差异夹带提交，也不能把静态 PASS 写成源码/安装/solver 动态通过。
