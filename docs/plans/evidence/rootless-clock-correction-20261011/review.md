# 时钟修复独立审查

日期：2026-10-11。审查者：n_plan_review（未编写修复）。结论：**PASS，限最终修复源码与无模型入口验证**。

范围：base `19f3e9f`；最终四文件身份与 `/tmp/scid-n1-clock-slew-legacy-final/manifest.json` 一致。预算源码 SHA256 为 `88853b1dd1e27d1970f610642d3e54e211617ed987948b74600676ff4f0a09a4`，runtime 未变。

已核对：

- 新 active 模式有锚点区间仅按同 boot 的 BOOTTIME 消费；UTC 调速、回拨不会误停或退款。未扩大固定容忍阈值。跨 boot、负 BOOTTIME、账本序号／parent／settings 身份篡改仍拒绝。
- 旧 elapsed 模式继续按 UTC 执行原截止；已有 BOOTTIME 账本时保留原 UTC 负值及相对漂移拒绝规则。初稿删去该规则会造成旧模式退额，已在最终修复中闭合；100→120→110、BOOT 保持 120 的 snapshot／transition／amend 均拒绝且不追加。
- 现场只有一个 advance 事件；诊断 UTC 与 BOOTTIME 增量分别约 109.280575 秒、109.700350 秒。精确原生采样回放、新 active UTC 回拨、负 BOOTTIME、跨 boot、旧 elapsed 与链篡改回归已读：预算＋runtime 38 项通过，5.47 秒；diff 检查通过。
- 最终独立安装包 CLI 六节点、0 模型 smoke 通过；8 个 research_loop 安装模块与 wheel、现源码逐字节一致。wheel SHA256 为 `2319f0b3bec9f289542cc8e0ce660ea9b9887f1e6ed1cd82ecab4ab03ba439b8`。旧冻结包未覆盖。

限制：无锚点且无账本的旧 UTC elapsed 开放区间原本无法可靠检测相对回拨，本轮不迁移它；旧模式的原漂移拒绝仍可能因 UTC 校正而拒绝。跨机器重启的时钟修复不在本轮。未改真实失败实例、未跑模型，不证明真实 HWA、暂停恢复或科学质量；case02 保留失败并计入场数，case03 若使用修复版本须另冻结并注明版本不同，不自动补场。
