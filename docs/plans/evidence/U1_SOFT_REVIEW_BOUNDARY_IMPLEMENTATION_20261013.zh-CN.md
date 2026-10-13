# U1：注册执行接口的软复核边界

状态：开发、无模型验收与独立审查PASS，随本节点提交；本轮未调用真实模型。

## 冻结边界

复用U0r唯一接受原件和所有实现共用入口。host从原阶段预算、原执行用量与收口预留派生复核投影；worker只读该投影，不能把可写的budget提示变成授权。投影可重建，不新增余额账本。没有node/search上限时只使用已有共享预算/收口规则，不发明机制额度。

接受新实验与发布复核请求用同一短锁排序；准备、领域调用和求解器不得在该短锁内执行。请求先发生则新实验不创建接受/外部作业；接受先发生则原作业可以完成。query/lookup/collect/cancel按原身份保持可用，不经过新提交门禁。总预算硬上限仍沿原规则。

同一W科学阶段的实验owner和复核anchor稳定，片段/原生attempt变化不重置预算、不令旧调用失去查询资格。U2再接正常片段，U3一次收敛科学协议及旧写入口退役；本节点不声称已完成所有旧实例写门控。

## 最小退出路径

1. 受管作业已接受后出现复核请求：作业正常完成和收集；后续新接受被拒且不留下伪调用。
2. 用并发屏障验证接受与请求两种先后；等待中的host发布不被长期solver锁阻塞。
3. 重启/同阶段attempt切换沿原anchor重新计算；token在途未知保留，时间用本机单调时钟，不从累计token推断上下文大小。
4. 原生publisher接线、只读目录动态更新、cov/local共用准入、真实安装入口均无模型验收；工具提示延迟与不支持能力如实报告。

## 无模型证据与修正过程

- production-01（8个生产文件）构建新wheel、隔离安装：`artifacts-u1-20261013/result/result.json` PASS；假原生H→W→A与重启不重放，模型请求0。
- 实际launcher/bwrap目录只读挂载：`artifacts-u1-20261013/u1-namespace-01-result.json`。首个受管cov夹具调用成功；host原子替换复核投影后，新调用被拒且调用数仍为1；原调用query成功并返回复核提示；worker写投影得到EROFS。
- 上述证据位于工作区`.trial/macro-role-installed-20261012/`，验证真实安装、隔离与注册调用链；领域后端为确定性夹具，不证明真实模型或TCAD资格。

- 首轮源码7文件：159通过、3失败、1不适用。两处注册夹具将源码egg-info误认作安装命令，一处旧fixture缺精确task原件；修正fixture并保留原安全断言。
- 独审修正三项真实生产缺陷：未知admission mode不可默认为允许；host在同一接受短锁内重采原clock/usage，防旧采样覆盖新复核；同attempt配置冲突先全部校验，拒绝时不改当前pointer。
- production-02安装回归：162通过、1不适用（77.37s），`artifacts-u1-02-20261013/u1-installed.log`；实际namespace验证也通过。
- 新增源码回归先47通过、1fixture失败、1不适用；未知用量fixture提前访问未封存前驱，改为合法H→W原件后单项通过，不改生产。
- production/source-03最终差量：36通过、1不适用（24.15s），`.trial/u1-source-03-20261013/batch-001/pytest.log`；此前soft-node安全负控已通过。变更只涉及配置拒绝顺序与对应负控，其余02通过证据保持适用。
- 唯一skip为payload原件测试的cov不适用分支；本地原件绑定及实际cov调用另有覆盖，不是安装门禁skip。

- production-03新wheel安装补充回归20通过（11.99s），`artifacts-u1-03-20261013/u1-added-installed.log`，模块SHA逐一核对安装来源。
- 同一新wheel的build_check及实际namespace准入/查询/只读负控全部PASS，模型请求0。
- wheel SHA256：`139090104436613a4bf101ee2e5591ea576a54c033494d24555849bd4b61e9a6`。

独立审查见[U1审查](U1_SOFT_REVIEW_BOUNDARY_REVIEW_20261013.md)。未运行真实模型、TCAD远端或全量平台矩阵；U2正常分片、U3科学路由与全旧写入口退役尚未交付。
