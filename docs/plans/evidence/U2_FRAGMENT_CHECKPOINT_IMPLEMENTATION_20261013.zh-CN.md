# U2：W片段检查点与恢复

状态：开发与无模型验收、独立审查限定PASS；内部显式opt-in已交付，默认启用由U3完成。

## 边界

复用同一个科学job、受管调用owner与原生attempt链；正常片段不封存科学阶段，不消费A科学周期，不占用有限失败修复次数，但每片消耗同一预算与步骤额度。当前片原件在停止写入后留检查点，直接成果按原控制层归档，不递归复制祖先。缺失科学小结与未知用量保留为事实，不制造恢复授权。

控制层从检查点形成不超过4KB实际JSON的续接简报；同session和新上下文策略必须事先冻结，不静默回退。复核边界优先于W继续意图，不能因等待旧进程结束或片段切换取得新额度。

本节点仅以内部显式opt-in及冻结schema夹具验证完整运行接线；生产科学协议13不加半套新字段，不在CLI默认启用分片。U3统一当前协议、科学schema与路由之后才对外启用。模拟原生进程验证控制行为，不授予真实Codex session恢复资格。

## 验收过程

- 首次专用回归：16通过、4失败（19.11s），失败均为fixture对已有artifacts目录再次mkdir；改为exist_ok，原断言保留。
- 首次共享回归：162通过、2失败、1不适用（57.08s）；发现真实恢复回退：retained原件存在但job缺失时新增read直接抛异常。控制层改回native_outcome_unsealed、保留原件、不创建任务/不重放，不改旧fixture。
- 独审实施前发现等待旧writer退出期间可能越过软投入边界：现在新native接受前再读原U1复核事实，命中则不创建新attempt。控制结束原因单独绑定checkpoint/raw，不重写W的continue意图；第一片也纳入封存execution_ref。

- source03专用+controller：65通过、1失败（20.60s）；唯一失败是多字节brief夹具的原文超过既有64KB输出合同，缩为仍大于4KB的合法原文并显式断言<64KB后，单项通过。生产容量不放宽，超限仍拒绝capture并保留原件。
- 新wheel构建、安装模块SHA及假原生HAWA/restart检查PASS，`artifacts-u2-03-20261013/result/result.json`，model_requests=0。

- 最终安装版5文件：184通过、1不适用（72.51s），`artifacts-u2-03-20261013/u2-installed.log`；安装模块位置与SHA核对，包含完整20项片段测试与既有resume/controller/registered/live反馈。
- wheel SHA256：`85e8cfed6e95f0a2827cd3001006ac12d430179b2ce08e79828a0b987532c533`。

独立审查见[U2审查](U2_WORKER_FRAGMENTS_REVIEW_20261013.md)。所有模型执行均为夹具，真实原生同session恢复、TCAD远端和科学效果仍未验证。
