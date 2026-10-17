# P2 跨 boot 维护与暂停续钟：独立静态复审

结论：当前冻结实现静态 PASS；未运行测试、项目导入、服务器、安装或模型/solver。
这不是实际机器重启、SSH 或远端服务资格验收。

追读 `budget.py`、`execution_resume.py`、`execution_authority.py`，并核真实
CLI → controller 原 writer → maintain → 原 factory/adapter 路径及三个定向测试。

- query/cancel/collect 必须已有 accepted，绑定原 scope/attempt/配置、permit HMAC、
  target、prepared 和 external ID；新有限窗口只授控制 IO，不创建 call、prepare/submit
  或续科学秒。HostServices 明确拒绝新身份和 dispatch；原 observation 完整保存。
- maintenance 回程不写普通 inactive 科学 clock。已验证 terminal 的原 resource settlement
  合法，不能误称新 grant；若跨 boot 原 ledger 暂不可追加，保 reservation 与诊断。
- active 且 paused 的 exact 冷 checkpoint 才可原 ledger 追加 clock 桥；原 head/start、
  ceilings、消耗、资源 grant/reservation/revision 不改。跨 boot 暂停间隔标 unmeasured，
  不伪算零秒；elapsed、waiting/advance、过期 head 或缺 transition 拒绝。
- 首次桥核当前 exclusive owner；历史桥只核 immutable transition，第二次恢复不使
  第一桥失效。通用 `_duration` 的跨 boot 拒绝仍保留。

已核三个新 source 用例的证伪范围：clock/resource 交错与两桥、非法桥、真实 DI transport
原调用跨 boot query/cancel/collect/no-fresh。预算 owner 的 test transition 是可信 DI，
不以此自证外部 owner fencing；实际外锚由 P4 独立路径验收。

最终范围按 root 裁定只有上述三种 maintenance。retire 保留既有入口，本节点没有新增
跨 boot retirement/退款能力，不将设计早稿的四动作列为已实现。
