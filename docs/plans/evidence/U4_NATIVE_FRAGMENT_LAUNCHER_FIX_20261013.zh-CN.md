# U4 启动前：真实启动器的片段输出接线

## 根因与范围

U2/U3的通用执行层已支持W片段，但cov验收启动器仍只接受首段输出目录。此前通用fake恢复和真实启动器首段分别验证，漏掉两者组合。本次仅补真实启动器new_context接缝；框架CLI仍是主入口，cov为注册执行实现。通用native校验与领域隔离脚本的职责归位按用户要求暂缓，不扩大本次改造。

输出必须是当前job最新已接受attempt的result.pending.json，并核验角色、workspace、home、原schema及原runner/child进程身份；终态、其他PID、旧attempt和任意子路径不能重放。2秒等待仅处理Popen到原child回执发布的短竞态，不等待模型，不持调度锁。same_session仍明确不支持。

## 无模型验收

- 源码parser：10通过，0.93s；`.trial/u4-launcher-source-01-20261013/batch-001/pytest.log`。
- wheel05解释器加载真实脚本：11通过，3.08s；`.trial/macro-role-installed-20261012/artifacts-u3-05-20261013/u4-launcher.log`。
- namespace用真实generic runner→launcher.main→bwrap，假native不调用模型。首片创建1次受管cov实验，第二片新上下文查询同一call；2个home/thread、同job/scope、仅1次accept、1个最终W封存、累计用量未重置。
- 核心安装模块未修改，因此复用已通过U3验收的wheel；启动脚本另按新提交冻结。不是仅用fake launcher绕过真实入口。

## 本场边界

新cov单场600万token／3600启用秒，gpt-6.1-sol high/default；启用new_context片段，output_repair=false，不调用人工worker-resume。未提供真实同线程恢复资格。模型科学行为、片段是否实际发生、复核触发及交付结果由U4真实场另报，不以本门禁代替效果验收。
