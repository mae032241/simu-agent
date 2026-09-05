# R5-M6A 直接实例管理实施证据

状态：首次独立审查打回后的修复与聚焦回归完成，等待全新独立复审

## 1. 本阶段边界

M6-A 只替换实例创建和会话选择的伪科学审批，不删除以下承重事实：

- `ResearchInstance`；
- `scheduler_sessions` 中唯一的会话到实例绑定；
- Artifact 语义修订；
- 科学 `current` 的比较并交换；
- 科学资格审批和外部执行授权。

## 2. 已完成改动

1. Root 删除 `instance_prepare`、`instance_status`、`instance_select`，未绑定的
   `instance_current` 现在是纯读，只返回短期本地管理链接。
2. 新增无数据库状态的 AES-GCM 加密认证实例管理能力；链接最长有效十五分钟，密文中不可
   直接恢复裸会话键。
3. loopback UI 新增独立的实例创建/选择页面；Host、Origin、表单类型、大小、签名和 CSRF
   均由固定代码检查。
4. 新增 `create_instance_and_bind_session` 与 `bind_session_by_name` 两个数据库原子命令；
   创建/选择和最终会话绑定在同一 `BEGIN IMMEDIATE` 事务内完成。
5. 删除创建提案、会话绑定请求、候选和决定应用代码；fresh DB 不再创建以下三张表：
   `scheduler_instance_proposals`、`scheduler_session_binding_requests`、
   `scheduler_session_binding_candidates`。
6. 实例管理不再创建 ApprovalRequest、HumanDecision、ReviewManifest 或提案 Artifact。
   ApprovalService 只保留科学资格与执行授权用途。
7. 调度提示改为：未绑定时把 `instance_current` 返回的精确本地管理链接交给用户，不得从聊天
   创建或选择实例。

## 3. 关键行为证据

- 未绑定查询前后 scheduler 数据库字节不变；
- UI 创建后，实例和会话绑定同时存在，Approval 与 Artifact 行数不增加；
- 第二会话选择已绑定实例时，唯一所有权在一个事务中转移，旧会话立即未绑定；
- 用相同会话键重建 Root facade 后可恢复 current；
- 篡改签名、错误 Origin、错误 CSRF、过期链接均失败关闭；
- 创建元数据冲突时事务回滚，会话不会留下半绑定；
- Root 工具目录不再包含三个实例写入口。

## 4. 已执行测试

```text
pytest -q \
  tests/operations/test_m6a_direct_instance_management.py \
  tests/operations/test_r4_approval_ui_renderer.py \
  tests/artifact_agent/test_platform_configuration.py
23 passed in 11.74s

pytest -q \
  tests/artifact_agent \
  tests/operations/test_l2_run_invariants.py \
  tests/operations/test_l3_review_and_human_policy.py \
  tests/operations/test_r4_execution_approval_identity.py \
  tests/operations/test_baseline_effect_lifecycle.py
71 passed in 49.58s
```

同时通过 Python 语法编译与 `git diff --check`。

## 5. 首次独立审查与返工

首次独立审查结论为 FAIL，指出：

1. 原签名载荷只是 Base64 编码，可在没有密钥时恢复 `session_key`；
2. 旧库的实例管理伪审批仍会出现在 pending 首页，并能从旧链接写入新的 HumanDecision。

返工后：

- capability 改为带随机 nonce 的 AES-GCM 密文，测试明确断言解码后的密文字节不包含会话键；
- 四类退役实例审批从 pending 列表中过滤；旧链接只显示只读历史，不渲染决定表单；POST
  决定返回冲突，Approval 状态、Decision 与 Artifact 均不变化；
- 第二次复审又发现“先取 100 条、再过滤旧 kind”会让旧记录挤掉真实待办；列表现改为固定
  100 行分页扫描，直到收满有效结果或数据库耗尽，并新增 100 条旧记录覆盖一条真实科学审批的
  负例；随后复审发现 OFFSET 会被扫描时的过期状态变化扰动，最终改为
  `(created_at, approval_id)` 稳定游标，状态刷新后只收录仍匹配查询状态的条目，并加入精确过期
  负控；
- 修复后聚焦测试为 `23 passed in 11.74s`，扩展回归为 `71 passed in 49.58s`。

## 6. 明确保留的问题

- 管理 CLI 仍属于显式本机管理员面；本阶段没有声称已解决 Local 原型缺少操作系统级工具隔离的
  `SEC-002`。
- 旧数据库中既有的实例创建/绑定审批只作为历史 Approval 读取；新 UI 决定路径不再应用它们，
  不会改变实例或会话事实。
- M6-B、M6-C、M6-D 尚未执行，本文件不放行 M7。
