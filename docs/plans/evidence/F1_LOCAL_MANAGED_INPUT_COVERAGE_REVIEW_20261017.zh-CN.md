# F1 Local 受管输入覆盖：独立审查

结论：**有限 PASS**。独立静态审查5生产 owner、1新增测试及设计/实施账；root两项最小目标已实际通过。未编辑这些生产/测试文件，未运行测试、项目import、安装、模型、业务CLI或Git。

## 实际链与保护

- `local_experiments.py:37-57`、`:375`：实际registered factory提供可选来源能力、完整实现assets和可信frozen interface；不是操作者JSON自报来源。
- `experiments.py:297-299`、`:928-942`：新能力确实属于冻结public_capabilities；dispatch将当前完整descriptor与冻结同key成员比较，才接受规范合同/adapter视图进入原accepted。未加入必需managed方法或新服务；无该能力仍可普通执行，但没有隐含来源覆盖。
- `execution_inputs.py:179-321`：全快照逐件核规范名字、entry、原job/config/native-intent/accepted绑定、保留字节。先按exact原件或job读副本找global/producer来源；当前W显式experiments/<name> authoring才可归自身。外部路径未知，错producer/遗漏清单/改保留字节拒绝；后续作者源正文编辑不覆盖已保留快照。readonly只读这些原事实和code proof，不构造/调用adapter。
- `history.py:326-396`：沿原共同执行校验，仅known_success/known_failed可新发表complete；unknown/not_submitted不可升级。新Local分支消费原accepted合同，原native/compiler分支保留；旧marker/合同缺失仍保守，不回填旧provenance。
- `formal_review.py:155-184`：仅实际producer input加入已有作者递归，即使未selected也不能漏掉其作者；不把所有父结论视作作者，也不让当前W authoring自递归。资格读取与来源覆盖校验没有互相调用当前执行准入。

qualification的全job来源边与restricted/unknown支配规则未改。complete只去除“额外来源无法解释”的附加unknown，不直接赋source clear；作者已知不等于准许执行。显式W authoring与native compiler沿同一可信Worker软边界，并非追踪任意copy/shell/库/argv读取。

## 实际失败与最终验收

首批 `.trial/p_completion_20261017/local-input-source/batch-001/pytest.log` 为1 setup error，0.65秒。fixture prepare默认冻结65秒配置，configure却另传5秒和cwd，生产正确拒绝；静态审查初轮也未发现该fixture不一致。仅测试改为prepare与configure使用同一显式Python/5秒配置，由host补cwd；生产未放宽。原记录保留，不称环境问题。

已核三批原pytest.log与resource.json：

| 目录（同上前缀） | 结果 | 监督耗时 | 峰值RSS |
| --- | --- | --- | --- |
| local-input-source | 1 setup error | 0.856秒 | 62,525,440 B |
| local-input-source-recheck | 1 passed | 1.18秒 | 60,444,672 B |
| local-input-process | 1 passed | 1.978秒 | 62,627,840 B |

合计2独立目标、3次测试尝试；监督4.014秒，最大62,627,840 B，三批cleanup_complete=true、memory_stop_triggers/received_signals为空，未启用address-space硬限制。不是最终HEAD全套回归或安装验证。

source目标以实际注册/配置/accept、无执行注入证明未知执行/无合同/外部输入不获complete，缺冻结能力拒绝。process目标运行两个微型Python脚本，再经共同终态、W封存、精确被审材料和正式review；同时核未selected producer作者贡献、错来源/快照篡改拒绝。native身份与review科学内容为合成fixture，只证明控制消费，不是模型科学质量或真实平台独立性。

## 未覆盖

不声明opaque或外部observer来源闭合、任意外读隔离、离线/可迁移归档资格、旧实例兼容升级或全部F1完成。保留live原路径、原code及已有输入依赖与重复只读hash成本，不承诺硬实时。无新增预算、执行授权、退款或未知调用重放。当前未发现应阻止此节点提交的剩余问题；无需扩大测试矩阵。
