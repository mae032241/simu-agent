# F3 安装入口收口

独立安装资格评审PASS。唯一安装测试使用新构建core和三个领域插件wheel、无system-site-packages的隔离venv与新实例，验证当前按需指南、复制读取器、旧reader3合同、冒名和越界拒绝。

旧测试仍读取context.guides，checks-07在该处失败；改为沿start_here公开指针真实读取worker-guides后，checks-08新增拒绝断言查错诊断流失败；修正为stdout且保留非零退出与内容不泄露断言，checks-09通过（pytest6.83秒、runner7.288秒，清理完成、无资源停止）。生产零改，测试15增4删，最终SHA `709575de7a910185d4caf020a1288c7c3481f0d2ed33aeb155930a6f92ab16ef`。

07捕获的HEAD为529830c；08/09未单独捕获运行HEAD，收口HEAD b9c0317不作为运行版本证据。精确测试补丁及每轮pip日志的4个wheel摘要保存在外层 `.trial/hwa_revision_20261010/f3/` installed报告与构建清单，12项摘要独立核对通过。临时环境已删除，不能作为F4可运行候选。

F3源码与本项安装资格完成。全量回归、原生slot回收、真实helper行为、用量完整性及科研效果仍未验证。F4准备路线已静态评审：新持久候选、公开cov题目冻结、无模型preflight；仅已授权scidiscovery组2000万token/90分钟，不启动native_goal或role_canary，不恢复旧o4。
