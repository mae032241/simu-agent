# R0 早期隔离工程反馈独立代码复核

日期：2026-10-17。基线：HEAD `500b33d0ad0d6043c2093f4ca0ed7ec3779592aa`；评审对象是最终 index 中的 R0 专属差异及其预算修正，不是包含未提交 P1 的整个工作树。

结论：**静态代码评审 PASS，发现的一项预算阻断已修正，无剩余阻断。** 可按 R0 独立范围提交；不表示动态回归、隔离运行资格、安装或科学复跑资格已通过。

本评审者只读差异、指定代码与实施记录，没有执行 pytest、collect-only、测试 import、构建、安装、真实模型、SSH 或 solver。执行者/root 报告的 AST、内存语法与 patch 可应用性检查只作为静态记录，不写成动态结果。

## 精确范围与前置

R0 包含七个生产文件：`research_loop/{replay_check,experiments,native,cov_experiments,cov_delivery,cov_lineage,delivery}.py`，一个新测试文件 `tests/research_loop/test_early_replay.py`，以及实施/本独审记录。

复核了剥离 P1 的补丁与最终 staged diff。`experiments.py` 只新增框架 helper 身份、接受声明、dispatch/reconcile 接入和紧凑反馈；`native.py` 只新增所有 W 都能看到的指导，不局限于 managed local 分支。它们没有夹带 P1 的 operator configuration、public_capabilities、registered_implementation、prepare CLI、发现缓存等修改。所需 `AdapterCapability`、Records metadata/snapshot、receipt、observation、budget 和 namespace 原语已在 HEAD 存在。

P1、其两个 fixture 修改、P1 新测试，以及 TCAD 容量六源/新测试/证据均不在本次批准范围。测试分组迁移和 R0 主计划修订已另行提交，不因本报告扩大为这些 pending 生产节点的批准。

## 生产边界核对

| 边界 | 静态结论 |
| --- | --- |
| 共通可选能力 | 通用 sidecar 只消费既有 `AdapterCapability` 声明和可选方法，没有扩展 `MANAGED_METHODS`。无声明为 unsupported，旧 call 无绑定为 not_run；没有把 Cov 特例提升为所有执行器的前置，也没有重建审计状态机 |
| 行为身份 | 共通 `freeze` 自动把 `replay_check.py` 放入 code proofs，第三方适配器无需知道或手填框架 helper；Cov 的 domain leaf/launcher 也进入其已有 code_assets。没有依赖 pending P1 的包级身份实现 |
| W 在场的反馈 | 同步 dispatch 在确认原 terminal observation 后执行一次；显式 reconcile 复用相同接缝；query/public 只读。既有外部 Cov launcher 的命令仍进入 experiments CLI，`cov_lineage.run` 也委托 dispatch；Cov compact feedback 与通用 CLI 均投影工程结果 |
| 资格分离 | sidecar 不改 completed、原 metric、candidate identity、科学 verdict 或 A 的决定；不调用 audit/submit/promote。sample_replay_ok 仅声明样本路径；最小样本/shape/一般训练异常为 inconclusive，缺依赖仅限声明样本范围，不推导完整训练失败 |
| 原件与输入 | Cov 在原接受前经已有 snapshot 机制冻结 source、公开 runner/train/val/meta、protocol 与解释器二进制 proof；不猜测不同环境映射。早检只使用该 call 的快照，阶段硬链接核对 regular/size/inode，实际挂载字节在 leaf 逐块比对摘要；不是链接当前可变 harness 或原工作区 |
| 隔离 | replay 明确进入 audit 同类的 scratch 可写、输入/runtime 只读分支，避开真实 target 与 source_roots 挂载；无 network，用户 home 不作为 runtime mount；隔离失败不回退到普通 host 执行。只执行精确 source import、一次样本 train/predict，没有完整科学审计 |
| 幂等与中断 | intent 先落盘，绑定 accepted/completed 摘要与能力/截止；存在 intent 即不再次执行。缺 outcome 显示 unknown。能力/原件不可验证、cleanup 未确认均不能变成成功；不自动重放未知原调用 |
| 异常与原成果 | 普通工程检查异常成为 unknown，原成功 CLI 状态仍由原执行决定；不吞 BaseException 的中断语义。原件与已写回执保留，检查不会替代或删除成功候选 |
| 完整诊断 | stage 持久存在于原 call，保留完整 replay stdout/stderr/JSON 与部分记录。已确认 cleanup 后设只读；只有截止内完成 hash 的日志才带完整 proof，过期则保留文件并明确未 hash。小回包/public 只保留诊断预览并累计真实省略数，不把预览说成全文 |

安装库仍从相同审计 runtime 只读可见，没有逐文件冻结；本实现不提供完整软件环境身份。隔离规则静态一致不等于已在实际 W namespace、嵌套 namespace 或部署环境运行通过。

## 已解决的预算阻断

首轮实现先计算 seconds，随后完整复制/再校验公开 train/val，最后 `_call` 从启动当下重新授予 seconds。大文件或慢盘可在准备时用尽原剩余后仍继续执行，损害 W 当场获得反馈的机会。

最终实现将唯一绝对截止绑定 intent：`min(原 call/host 截止减反馈余量, 本次检查开始加声明上限)`。该值传入 adapter、stage 准备、runtime/protocol/input 分块 hash、`_call` 启动前和执行循环。终态后不再复制整份公共数据，不再重复验证整组 model/log 原件；复用已确认 observation 和原快照，校验小绑定后使用只读阶段输入。

准备到期为 not_run，不启动 leaf；已启动而未完成为 inconclusive/unknown，不重新给时间。清理后截止已过时不再启动完整 json.load；大诊断只在 leaf 原件保存，控制回包为小预览，省略数不丢失。新增的 preparation 到期负控要求生产 `_call` 不能被调用，直接对应此次故障。

10 秒和 2 秒是声明的诊断上限/准入余量，不是新授权或硬实时保证。接受前新增公开输入 hash/原快照复制仍属于原 native 任务墙钟开销，不受终态后诊断上限覆盖；同步单次 IO、调度、清理和回执写入不能由块间时钟检查强行中断。实施记录已明确这些限制，没有宣称新增内核资源域或保证清理后必剩两秒。

## 测试证据边界

五个定向用例已静态阅读，均未运行。主正负例通过生产 dispatch、公开 runner receipt、真实隔离/leaf 和实际 train 调用形成结果；没有由 fixture 直接写工程成功 JSON。它们分别针对训练期 helper 遗漏与同任务新调用修复、小样本不适配仍保留原成功、接受后当前文件变化与未知不重放、可选异常/原截止耗尽/local unsupported，以及准备耗尽后不得新启动。

模拟时钟和异常只用于相应边界负控；它们不证明实际超时、清理或完整跨进程恢复已经通过。真实 bwrap 可用性、软件依赖、资源开销、嵌套 worker 环境和代码运行结果仍未验证。没有增加安装或模型场作为本节点退出条件。

当前 R0 代码可独立于 P1 提交；后续只在执行条件与资源域明确后选择最小相关检查。不能把本次静态 PASS 写成已完成真实复跑、科学审计或 OOM 修复。
