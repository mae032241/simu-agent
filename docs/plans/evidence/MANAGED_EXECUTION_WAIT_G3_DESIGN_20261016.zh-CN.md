# Managed execution 等待/恢复最小设计（2026-10-16）

基线 `92c29ab`；本文件为实施设计，不是验收或独审结论。

## 新节点

native turn 结束与 managed call 终态分离。只有原 accepted、host interface、submission external ID 一致，且声明 query 的 adapter 明确返回 running，才能在 seal 前保留原 attempt checkpoint 并进入 waiting。accepted/submitted/unknown 或身份缺失不作为 running。控制不编写 W 科学结果。

现有 run 控制进程在原节点按固定间隔轮询同 call，尊重 pause/停止和原有限全局时间授权。共同终态继续使用 execution-observation.json；collect=false 不调用 collect。终态后使用既有合格 same-session launcher/session/header、原 workspace、累积预算以及有限 continuation 授权，持久化一次 wake intent 后启动。重启读原 waiting/wake intent；已接受但提交不确定的 native wake 不再启动。无合格续接能力保留 checkpoint 并报告 unavailable。

waiting 用现有控制时钟新增 waiting phase 记录真实执行等待时间：不增加 advance_seconds、LLM token 或 dispatch；计入有限全局 seconds 消耗。wake native turn 仍计原节点累计预算、token 和 dispatch。控制进程退出后未确认终态的时间保守计入 waiting，不重置 deadline。

## 已 sealed unknown

新增显式 execution-recover 控制入口。对同一 call 校验/冻结共同终态，并在现有 host-history 中追加绑定旧 seal、旧 unknown row、原 accepted 与新终态原件的恢复事实。原 seal、科学判断、机会次数、grant 和原 slice 均不变。

每个新 job 显式冻结所消费恢复事实的精确前缀；旧 job 缺该字段按空前缀读取。search 只对前缀内对应 call 解除 unknown；lineage 同时挂载该恢复事实与成果，后继 A/W 自行判断。恢复不隐式更新已准备 job 的输入，也不使旧结论变为 screened。旧 job 需要新科学节点才能消费追加事实。

## 文件责任

逻辑集中于 managed_wait 与 execution_recovery；只对既有 contracts seal、native/controller/runtime、continuation/execution chain、budget clock、history/search/lineage、CLI 接入必要调用。tests 使用真实 CLI 的 scripted 原生 launcher 和 registered async fixture，source 与 installed 均不调用模型/solver。框架 same-session 流程不等于真实 Codex session 唤醒资格。
