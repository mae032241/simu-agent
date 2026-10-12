# T3：原生角色短指导与 cov wrapper 兼容

状态：源码、分批定向验证、安装与真实公开执行隔离门禁及[独立审查](ROOTLESS_T3_REVIEW_20261012.md)通过。零科研模型调用；科学自适应与效率仍待T5。

## 1. 域中立的科学指导

`guidance.DEFAULT` 为 H/W/A/E 四个短段，合计1511 UTF-8 bytes；`guidance.policy` 强校验四角色、非空文本及总计≤2048B。通用默认文本不假定存在 cov 的 `exp` 工具。

- H 保留范围内的自由探索，优先最小判别观察，机制只声明本轮增量；不将完整预排活动锁成固定批次。
- W 在冻结 H 范围和原剩余预算内选择新建、改进或回退既有父方案；读取结果后选择下一有用观察。小批次仍需科学目的；unknown 查询确切状态而不重放，known failure 的修复仍受原额度约束。
- A 判断全局贡献、适用范围和盲区，分开科学负结论与工程失败、代理最高与推荐及实际提交事实。
- E 回答原请求者的有界证据问题，不把缺原件变成授权或扩展搜索。

prepare 将实际字符串复制冻结到 settings；新 job 只冻结当前角色的 literal，science-view 仅读 job 的该字符串。retained job 使用自身已冻结 literal，旧 job 缺字段不补。科学协议8、required 输出字段、T2 布局 marker 及原 ROLE_INSTRUCTIONS 常量不变；不宣称此前所有 native prompt 已完全冻结。

领域用法通过 prepare 的 `role_guidance` override 添加，仍计入全角色2KB上限，由适配器/launcher设置，作者不填机械字段。T5 cov 的具体命令可追加到 W literal；core 不硬编码 cov 命令。T4后续复用此 literal 接缝，不隐式修改旧 job 文本。

## 2. cov 实际接口兼容

已反查原公开 `exp_cli.py`：run 的 script 可省略，默认 `EXP_DEFAULT_SCRIPT`。wrapper 的 run 同样允许省略 `--script`，使用 launcher 冻结的绝对 env 目标；显式 script 优先。缺少绝对默认值时 unresolved，未接受调用；不按文件名或最近修改时间猜脚本。原 accepted/source snapshot、同调用 stdout/row、model/terminal 校验及 node lock 不变。

已反查原 `runner.py`：rec 的 metric 为公开 meta 的命名字符串；成功 rec 的 val_score/val_acc 为同一公开验证分数（val_acc 是 legacy 名称），并有 wall_seconds；失败有原 error。wrapper 只从本调用已校验的 row original 返回这些存在且有界的事实，以及冻结 evaluation_key；不虚构缺失字段、不读全台账猜本次结果，不授审计或目标最优资格。lineage-status 是同档案的只读有界反馈，不重执行。

v2 observer 补齐原公开 `submitted.json/submitted_model.pkl` 观察，避免替换旧 observer 时静默丢掉原 exp submit 事实。actual 与 current 分开：无明确 current 来源仍 None；submitted artifact 保原 bytes/evidence，只有候选已观察且与该候选 managed call 的冻结 model SHA/size 相符才绑定 candidate ID。路径/模型失配保 candidate=null、coverage partial；submitted record 缺 artifact 保 actual unknown/partial。没有 host unpickle、audit、submit 或隐藏读源。

公开 actual 观察不是外部 confirmed；`leakage_flag=False`、proxy ok 或缺 audit 都不变成 qualified。后续 T4 没有冻结 delivery 原件时仍需报告 confirmation unknown。

## 3. 最小门禁及退出项

新增 `test_scientific_guidance.py` 验证四角色 literal/旧 job 原件不变/总量与非法参数；真实 module CLI 的默认 script、显式 override、缺默认拒绝及原 row 数值反馈；只读 status；公开 actual exact/mismatch/missing、封存 artifact 与资格不推断。

分批门禁：外层 `.trial/t3-source-20261012-01/batch-001/pytest.log` 90 passed、1 failed，30.93s。唯一失败是通用 tiny backend 原 row 没有 metric，夹具却强索取；生产保持缺字段就不生成。修订后 test 同时验证缺 metric 不虚构，并以已有含 metric 的同调用原 row 作正控。该文件复验12 passed、1.58s，日志外层 `.trial/t3-source-20261012-02/batch-001/pytest.log`。不能称一次全套通过。

安装与 namespace 证据均由父级执行：

| 门禁 | 结果与精确证据 |
| --- | --- |
| fresh installed | 18模块 source/wheel/install逐字节一致；9项实际 CLI 检查通过。外层 `.trial/t3-installed-20261012/artifacts/result/result.json` SHA256 `ebb8575022a670408704795dcb9afa9c5011075ad64607391af3f4591c6baf97`；wheel SHA256 `fb517c29ae5bf87f58248195839047579c1968e0daf8c3fd2a372348776dbc2c` |
| 实际 namespace/原 public harness | 两次 constant-zero 合法原 public exp run、0LLM请求。精确默认script与父分支，原模型路径绑定，host配置只读，私有canary/控制目录不在namespace。外层 `.trial/t3-native-gate-20261012/result-01/result.json` SHA256 `7e96ad3e0bd98cd0acea5054914f7e389244d15b710b302a77dc430f63f5fd50` |

namespace门禁使用 fake model transport；没有实际 Codex 权限或模型科学选择行为资格。两次常量模型调用只验证传输、权限及原harness回执，不证明科学自适应或效果提升。

代码已独审通过并提交 `ac8e3fc`。指导如何使用观测不是科研收益证明；没有本节点真实科研成本/效果比较，T5 单场验收另行冻结。

独立审查已完成，报告见 [T3 review](ROOTLESS_T3_REVIEW_20261012.md)。
