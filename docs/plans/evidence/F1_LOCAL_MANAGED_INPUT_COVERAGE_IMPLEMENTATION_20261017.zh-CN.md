# F1 Local 受管输入覆盖实施账

状态：实现已冻结，独立静态审查通过；root 串行 source/process 两个增量目标均通过。首次 source 验收在 fixture setup 拒绝，未执行目标主体，修复后重跑通过。依据 [Local 设计](F1_LOCAL_MANAGED_INPUT_COVERAGE_DESIGN_20261017.zh-CN.md)，复用已提交 native F1 的 coverage marker、source edges 与作者递归，不新增来源图、预算、授权或执行服务。

## 精确范围

五份生产文件均在 `src/scidiscovery/research_loop/`：

- `local_experiments.py`：实际 adapter 声明可选 `managed_input_sources` 能力；factory 复用可信 `frozen_execution_interface`，接受时生成一次输入视图；实际 helper 纳入既有 code_assets。
- `experiments.py`：freeze 保留该能力；dispatch 要求实际能力与原 frozen public capability 一致，再将完整合同及视图写入原 accepted。操作者 JSON 不可提供该视图或 host interface。
- `execution_inputs.py`：对照原 job/config/native-intent、快照清单、保留字节、已有 global/producer edges；只在当前 job 显式 `experiments/<name>` 包内把剩余新文件归当前 W。只读核合同须与 accepted.interface 中唯一同 key/schema/hash/size 能力匹配，且不构造或调用 adapter。
- `history.py`：仅共同验证的 `known_success/known_failed` 可捕获 complete；同 marker 只读重核原件，unknown/not_submitted、无合同及外部未知输入不升级。
- `formal_review.py`：仅 authors 消费已验证实际输入贡献，将未 selected 的实际 direct producer 加入原 selected/compiled 递归；不遍历全部祖先，不改 review 选择或路由。

新增 `tests/research_loop/test_local_input_sources.py`，并更新上述设计；本实施账共八份作者文件（独审报告另列）。`qualification.py`、P4/P5、通用 Local 执行/期限/提交协议均未修改。

## 最小验收目标

source：`tests/research_loop/test_local_input_sources.py::test_local_source_contract_unknown_originals_and_unknown_execution_do_not_upgrade`。真实 registry/factory/config/accepted 路径，替换 `_execute` 为无操作而不启动进程；核 unknown 行不能 complete、旧无合同保持未知、剥除 frozen 能力拒绝、外部目录不能归当前作者。

process：`tests/research_loop/test_local_input_sources.py::test_public_local_inputs_authoring_and_unselected_contributors_reach_exact_review`。显式 `process_e2e`；仅两个 tiny Python 进程，无模型、solver、安装或网络。分别执行 exact H 输入副本与 W authoring 包，经共同 terminal→W seal→exact formal subject→独立 review；核未 selected 的实际 producer 作者贡献、后续作者源编辑不改变保留字节。同链拒绝错 producer、遗漏快照、篡改 retained input，原 provenance 字节不变。native participants 来自 fixture 的合成身份，不代表真实平台作者身份验收。

静态检查：六份 Python 使用 stdlib `ast.parse`，并检查尾随空白；未 import 项目、未执行测试或业务。本次不重复安装或旧全量 suite。

首次 root source 批次 `.trial/p_completion_20261017/local-input-source/batch-001/pytest.log` 在 setup 报 `Host execution configuration differs from the frozen operator selection`：fixture prepare 使用默认 operator 配置，后续 configure 却请求 Python/5 秒并显式 cwd。生产准确拒绝。修复仅将同一 Python/5 秒配置先交 `prepare(execution_config=...)` 冻结，再原样交 configure，由既有 host 规则补 cwd；不放宽生产校验。root 提供首次监督摘要为 0.856 秒、peak 62,525,440 B；修复经静态 AST 与独审后交 root 重跑。此前 runner 重复 `--lane` 被 argparse 拒绝，无测试启动。

已只读核 root 后续两批 `batch-001/{pytest.log,resource.json}`：

| 批次（位于 `.trial/p_completion_20261017/`） | 结果 | pytest / 监督耗时 | 进程树 RSS 高水位 |
| --- | --- | --- | --- |
| `local-input-source-recheck` | 1 passed | 0.88 / 1.18 秒 | 60,444,672 B |
| `local-input-process` | 1 passed | 1.78 / 1.978 秒 | 62,627,840 B |

两批均 exit 0、cleanup_complete=true、memory_stop_triggers=[]、received_signals=[]；未启用 address-space limit。本节点共 2 个 unique 增量目标通过，不是全量回归、安装验收或真实平台作者身份验证。作者仅核日志及更新本页，没有重测。

## 合同与限制

这是框架声明输入的软边界：显式 authoring 包内新 script/helper 由当前 W 已封存 participants 负责，全部 job restriction 仍由原 qualification 输入边保守继承。作者可确定不等于来源 clear；本节点未降低 unknown/restricted 的现有判定。不能证明任意 shell、库、argv 或恶意同 UID 外读；不完整/旧合同与 opaque 保持 unknown。继承并实际声明同能力的 adapter 按自身冻结合同处理，不按 executor 字符串授资格。

历史只消费归档视图和 exact refs，不重新生成输入事实，不重签/回填旧 proof，也不新增 host key 依赖。保留现有 live 原件、外部 code 与绝对路径依赖；不承诺离线归档资格读取或迁移。保留文件、job/source/compiler 等只读身份核验可能重复流式 hash/读取；没有新持久索引、机械容量上限或硬实时 IO 保证。

本页仅声明上述两个增量目标通过，不宣称任意外源闭合或全 F1 完成。
