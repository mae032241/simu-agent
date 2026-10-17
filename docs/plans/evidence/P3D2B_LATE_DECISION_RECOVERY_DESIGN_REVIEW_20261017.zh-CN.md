# P3d2-b 迟批恢复独立设计评审

结论：**补强后设计 PASS，可先独立提交设计；实现须分块冻结再审。** 阅读对象为 `P3D2B_LATE_DECISION_RECOVERY_DESIGN_20261017.zh-CN.md`，对照已提交 d1/d2a 与现有 execution_recovery/history/search 消费方式。本轮未运行项目、测试/收集、CLI、构建、安装或任何真实执行。

## 已解决的必须修改项

1. **不能从当前缺文件推出从未 prepare。** 现设计在原 native 全 attempt 终态/cleanup 后，由原 authority writer 捕获完整 allocation/request/accepted 集合及明确 unprepared 事实，原 seal 绑定 pending-set ref。缺归属、半写、cleanup 未确认或历史 seal 无正向 receipt 都不给恢复资格，也不能事后补猜。跨 boot 不用当前 PID 缺失代替原事实。
2. **不能只在 terminal 时让迟到 accepted 出现。** 复用唯一 execution_recovery owner/目录/prefix，追加 resume_intent→accepted/status→terminal/not_submitted 的原件 ref 链；由一个纯 call_view 供 history/lineage/search/新调用准入/clock 消费。旧零 accepted 的封存节点可在派生 copy 添加实际 accepted，pending 立即可见且计一次；旧 A 仍按当时冻结 prefix 验证，不能回写旧科学判断。旧 resolved 只解 verified terminal，不能把 pending key 当解除 unknown。
3. **等待批准不能被自己的派发 intent 阻断。** 无有效决定或 renewal 时只保存请求 successor/有限请求操作 receipt，不写可能派发的 resume_intent、不形成 unknown 派发计费。有效 exact 决定与当前权限/机会/资源/剩余都通过后，才在首次 prepare 前发布 resume_intent；此后中断按可能派发处理，不借 fresh lease 重放。

## 权限、预算与最小性

- 产品入口为显式 `execution-resume`，不是 UI 批准即执行、不是重开旧 W。原 call/subject/source/interface/target/科学机制不变；原 seal/result/job 不改。有效决定复用，真正过期或 policy/grant 变化才走原 request/decision 协议的 supersedes 链，重试不续 TTL，不搜 latest pass。
- 新有限 max-seconds 是当前 host 控制操作窗口，不是新的 solver grant；request TTL、remote job wall、collection window分别解释。原 ledger 是唯一余额 owner，reserve 窗口复用同 reservation，authority 重绑不退款再占，不改累计消耗。已有 accepted 的 query/cancel/retire 不等于新提交；显式维护窗口不延长 solver 额度或重写旧窗口。
- 新事件只能引用原 admission、Records accepted/query、统一 verify_observation/verify_retirement 事实；call_view 不拥有科学结论、远端状态或余额。只在事实变化时追加，重复读取幂等，没有新队列、worker、重试循环、机会库或第二预算账。
- 原 mechanism 在 allocation 冻结，恢复用现有 breadth/search 规则重新核同机会；resume_intent 未 accepted 不虚计机会，实际 accepted 后只计一次且不得冲突新 call。实际 validator/helper 自动纳 freeze 代码身份，不依赖插件作者手列。

这些是实现审查约束，不是已存在的能力。新链是现有 recovery owner 必要的原件投影扩展；若实现另建可变调度状态、按事件名字自证成功、改旧 prefix 或用 JSON allow/resume 注入权限，应退回设计而非顺手扩协议。

## 仍未验收

无代码通过结论；跨 boot/掉电、实际 UI 迟批、真实 native/TCAD、资源事件与旧 clock/search 交错均未动态验证。后续只写能保护上述真实失败模式的最小负控，不安装、不运行。历史无正向 pending receipt 的实例保持 unavailable；不能为迁移完成补造原件。
