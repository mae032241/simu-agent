# A3 默认审查输入分离独立静态审查

结论：**冻结六文件静态 PASS，可交 root 串行定向验证。** 基线为 A2 `804f7a7`；范围为 formal_review/contracts/controller/native、test_formal_review 与[实施账](A3_DEFAULT_REVIEW_INPUT_SEPARATION_IMPLEMENTATION_20261017.zh-CN.md)。另核 root 持有的修复计划和 plans README 同步；未运行测试或项目代码。

## 默认输入与控制身份

- 原 `route_reason → question → instruction` 改为固定中立任务模板；原理由保存在 host request，原 requester seal 精确校验仍在。成功 review 路由只列确切 subject producer；build_job 的正式分支不复制父结论、其余附件、全 lineage 页、相邻审计或 implementation options。
- 不是只隐藏 public view：实际输入文件只由 globals 与 exact subject 生成；validate_job 核同一 materials/selected/minimal history，拒默认 history 和 parent conclusion 残留。controller retained `_check_job` 同步空 direct_refs，普通节点仍核原 parents。
- `subject=requester` 仍复制确切 artifact，而不复制其结论或无关附件；控制 requester 身份不依赖正文。原 return_route 未改，后继普通 A 仍绑定 requester 和正式 review，恢复普通科学输入语义。

## 跨边界资格未洗白

1. 清空 direct_refs 后，host 生成的 `selected_inputs(origin_step, origin_result_sha256, material)` 保留 producer 边；`qualification._inputs` 继续核原 producer seal/material membership，不靠同 hash 补源。未声明原始叶仍 unknown，受限来源仍按原规则传播。
2. `input_binding` 校验 request 当前合同、中立问题及 exact producer seal 路径/字节和材料 membership；全局字节、subject copy/hash/配额与一般输入验证继续。minimal history 仅保原 seal 元数据，原 history validator 仍验证该 source，不默认写论证文件。
3. 原 `authors(subject)` 对 selected、compiled slots 及 author_input 的贡献链未改；reviewer 只取实际自身 participants，未知/重叠仍不合格。`require_review` 继续核原 exact subject/current contract/receipt，不重编译或改换原输入身份。
4. 新默认输入合同明确标记，并把实际 contracts binder 源码纳入 review contract 身份；旧合同不自动重签/升级。普通 A 的 history/search/selection、四字段正式 schema、预算和 A role profile 不变；没有新角色、读取 API、曝光账或专属模型覆盖。

## 有限科学范围

global+subject 不等于完整科学支持集：artifact 可能需要同 producer 的其他文件或证据，本节点不自动递归收齐。public review 明确缺主张/证据保持 unknown，原 scope 要求 unsupported claims 使用 revise/blocked/inconclusive；控制层不能因删去上下文自动授予科学 pass。artifact 本身的主张保持原字节，程序不替作者重写结论。

这只是默认材料去锚定。任意 native 文件读取的曝光未完整观测，同权限仍可能读 host 原论证；不是盲评或访问隔离。身份独立 receipt 不证明观点独立或全部科学主张正确。

## 最小验证建议与可证伪范围

- **source 3 项**：新增 `test_review_default_packet_keeps_exact_source_without_requester_arguments`、`test_review_subject_from_requester_keeps_artifact_but_not_its_conclusion`，及原 `test_ordinary_a_and_pass_text_do_not_gain_formal_qualification`。能发现默认正文/附件残留、producer 绑定篡改未拒、同 requester 丢 subject 或 ordinary A 父正文误删。两个输入 fixture 使用控制事实 stand-in，不证明真实身份资格。
- **process 3 项**：原成功 review（含再次 controller.run）、作者重叠拒绝、未知身份续行。实际脚本 native launcher 检查 prompt/task/所有 inputs 中无显著推荐 marker、subject/global 仍在；能发现只改显示未改实际输入及原路由/身份退化。脚本 verdict/pass 只测试控制消费，不证明科学判断质量。
- **source 1 项跨界检查**：既有 `test_native_execution_inputs.py::test_public_compile_exact_review_and_existing_run_keep_native_original`，覆盖本次受影响的 compiled 输入贡献 → exact formal review → 原 gate/ledger → 同原包 run 链。不重跑其余迟批组或安装矩阵。

这些是交 root 的目标建议，不是已执行结果；如出现具体失败再修复/复审，未见风险不扩全量。

## 静态证据

独立阅读冻结差异、原来源/作者/编译输入/历史/profile 及回程接缝；限定代码和文档 `git diff --check` 无报错。作者 AST 结果见实施账。未 pytest/collect、项目 import、业务 CLI、模型、服务器、安装/build 或 solver；唯一写入为本报告。计划/README 已正确后置按需曝光和专属模型覆盖，不影响原 164 项历史范围。动态资格另记。
