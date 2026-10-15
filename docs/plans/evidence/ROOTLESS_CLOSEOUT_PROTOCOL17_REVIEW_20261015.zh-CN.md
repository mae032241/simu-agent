# 协议17独立复审

审查对象：e255a08之上的本轮未提交修复。两位独立 gpt-6.1-sol/high 审查者只读审查，未参与实现、未运行模型或测试。

## 结论：PASS

- /root/framework_contract_review：禁用audit在intent之前拒绝新调用，既有accepted审计无条件计步及未知阻断；status使用相同事实显示unknown；模型能力和可诊断schema一致。显式selection走冻结比较，无policy直接授权。
- /root/framework_artifact_review：普通deliver不再绕过显式selection策略，prepare/binding均校验同一default/override；未配置策略维持3科学节点。封存原件及audit/promote/confirm隔离无新回归；未知提交不重放。submit/help仅stderr警示，原参数/权限/退出码保留。

前次发现的两个P1及状态P2已经修复。旧W scratch不可见本身是隔离边界；正常交付从受管call封存脚本和模型，不要求E复制或扩大挂载。普通shell直调原始CLI仍属明确软隔离能力范围；任意本地import依赖未递归捕获。

## 验证边界

源码定向测试和安装验收由实施者执行，审查者阅读实现及反例测试，不把静态复审声称为独立测试运行。最终源码回归161个不同用例通过、3项跳过；独立venv/wheel实际CLI/bwrap零模型全链21/21通过，228模块与源码SHA一致。安装验收selection policy关闭；显式策略由源码真实本地进程测试覆盖。未验证真实模型、隐藏reward或远端TCAD。

见 ROOTLESS_CLOSEOUT_PROTOCOL17_20261015.zh-CN.md 与 ROOTLESS_CLOSEOUT_PROTOCOL17_INSTALLED_20261015.json。
