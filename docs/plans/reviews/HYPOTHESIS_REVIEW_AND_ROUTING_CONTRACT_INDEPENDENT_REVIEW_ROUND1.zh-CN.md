# 假设审查与后续行动契约首轮独立审查

审查日期：2026-09-03  
候选：首次类型化路由实现，第二轮来源连续性与稳定假设键返工之前的工作树  
审查者权限：只读，未参与实现，未修改文件  
结论：**FAIL；阻断项 2**

## 1. 阻断项

### B1 证据修订没有冻结原 intake 的来源集合

`science.evidence.revise-from-critic.v1` 虽然绑定 intake→audit→foundation→portfolio→critic 父链，
但原 guard 没有比较 `source_material` 与 prior intake 的来源父集合。独立审查用“prior intake 继承旧
来源、修订只绑定无关新来源”的负例证明编译 preflight 仍可接受。这样会允许旧证据静默消失，后续
audit 只能审核替换后的来源。

必须要求原来源全集继续绑定；如需新增来源，应使用显式的新证据行动或独立端口，不能任意替换。

### B2 无进展指纹可被 hypothesis key 改名绕过

原问题指纹包含 `hypothesis_key`，但修订输出 validator 只冻结全局 objective，没有冻结假设键集合。
同一处置、相同未通过维度和相同科学问题只改写 key，指纹就会变化，因此可绕过一次
`revision_no_progress`。两次硬上限能防止无限循环，却不能满足“没有科学进展即停止”。

必须冻结有界修订前后的假设键集合，或引入不可变假设谱系；同时覆盖改名和重排测试。

## 2. 已确认正确

- critic 只拥有物理合理性、可证伪性和原则有限可区分性；实验设计拥有阈值、提取/归约和不确定性
  传播；
- `CriticReview v2`、`next_action_kind`、`accepts_actions`、Run 信号和 inventory 投影形成类型路由；
- 六种 disposition 有声明消费者或明确终止语义；
- 没有发现新增第二状态机、第二 Operation 注册表或 TCAD 领域词汇进入通用核心；
- 75 个聚焦测试及一个 clean-wheel 插件矩阵通过。源码 checkout 内重复 `egg-info` 导致的三个
  subprocess 失败，以及生产文件 184>159 的既有门，均与本轮两个语义阻断分别记录。

## 3. 未验证边界

- 尚无六种 disposition 从真实 Worker 提交、Run 持久化、inventory 到下一 Root preflight 的完整
  端到端矩阵；
- 新契约尚未部署，未运行真实 Fig.4 科学闭环；
- 实验输出中提取、插值和误差传播的实际表达仍主要依赖 prompt 与现有自由文本字段。

本报告只约束首轮候选。任何返工都是新候选，必须重新独立审查，不得继承本次已确认正确部分作为
自动 PASS。
