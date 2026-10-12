# T5 单场 cov：H 节点超时，真实 HWA 验收未通过

状态：授权的一场已终止，未重跑、未扩额、未从未资格的原生续接入口恢复。[独立终态核查](ROOTLESS_T5_TERMINAL_REVIEW_20261012.md)已完成：事实核查通过，真实验收未通过。

## 冻结条件与结果

- 候选 `f8427dfe69319e2cac0ecf6b7033da409172159f`；安装 wheel `224c76eef9cd84615c16473d23bf3db65edc181b0970ee26a1c00387dd65fc29`。
- 仅框架组；gpt-6.1-sol/high/default；6,000,000 observed tokens / 3,600 active秒 / 24步。H单节点500,000 token / 420秒。预算与收口预留见原[冻结预检](ROOTLESS_T5_COV_SINGLE_CASE_20261012.md)。
- 启动前80项文件哈希一致，独审通过。运行驱动结束时再次校验冻结输入无变化。
- 实际约422.191秒停止：`native_stopped`，H001 `node_slice_time_limit`，进程返回-15。停止原因是H节点时间上限，非全局时间上限；最终token未知，不据部分回执推断精确剩余token。
- 0个已封存科学节点、0次正式exp run；W/A/E未启动。H工作目录保留诊断脚本与7,662B的scientific_direction.md，但未成为完成的科学节点，不能代替封存结论。
- 无submitted.json、无正式提交模型。因此没有隐藏reward可评分；不报告虚假的0分，也不从H的诊断代码另造候选评分。

## 用量范围

控制层仅收到原生结束回合的用量时才累计。本次被时间上限中断前没有turn.completed，故`unknown_steps=[1]`；显示observed_tokens=0是缺回执，不能解释为没花token。

事后按native thread.started精确匹配原生session_meta，最后一次token_count为217,492 total：209,783 input，其中173,440 cached，7,709 output。未缓存输入36,343；未缓存输入+输出44,052。该回执时间06:57:49.918Z，早于中断，末尾在途调用的用量仍未知。它不被写回控制预算，也不作为完整账单。

## 验收判定

工程及科学真实验收均未通过：完整H→W→A、跨节点继承、自适应选择和预算收口在本场均未观测。之前源码/安装/公开无模型门禁仍保留各自范围，不可替代真实通过。

本场首先证明冻结H节点时长未能容纳其实际行为。原生初始提示明确给出500k/420s，预算不是不可见。H运行了OMP、Ridge和合成漂移诊断，扩展到了实验筛选；两次诊断命令均成功，最后脚本自记约0.67秒，不能把耗时归结为求解器计算慢。

H生成了方向稿之后仍未返回最终科学JSON。控制层按420秒上限停止，没有足够证据指向封存器拒绝合法提交；未出现附件清单、哈希或打包工作转嫁给模型。真正暴露的是H职责扩展、模型推理/工具往返与硬节点上限之间不匹配。重复读了两个内容相同的7778B目标入口，属可改进冗余；不能仅凭此认定主要耗时原因。

下一修订应先使H聚焦定性的竞争机制与最小判别设计，将拟合/筛选实现交给W，并优先返回可派发的科学决策；同时基于本场校准节点时长和协作式收尾，不只是增加总token。中断用量和实际原生续接能力尚未资格，不能假造原线程恢复。真实场重跑需另行明确授权，不以自动重试消耗预算。

## 原始证据

外层 `.trial/rootless-t5-cov-20261012/`：frozen-manifest.json、qualification.json、controller-result.json、final-result.json、terminal-evidence.json、postmortem-native-usage.json，以及instance/native-evidence/001、原生精确session和未封存工作目录。所有失败原件保留。

独立评估脚本 `.trial/t5-official-score-20261012/score.py`只准备、未运行；无提交即不启动隐藏评分。

独立根因核查：[H节点失败分析](ROOTLESS_T5_FAILURE_ANALYSIS_20261012.md)。报告明确区分观察事实与职责/预算配置的解释，没有把本场科学草稿判为已封存结论。
