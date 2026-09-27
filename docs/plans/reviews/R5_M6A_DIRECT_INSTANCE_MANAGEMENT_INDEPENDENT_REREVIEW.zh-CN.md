# R5-M6A 直接实例管理独立复审

结论：**PASS**

放行范围：**只放行 M6-B**。本结论不放行 M6-C、M6-D、M7，也不替代整阶段独立审查。

## 1. 复审范围

本轮以 `404aeb14c6ebc4b08bac599db91eaee54c103f48` 上的当前工作树为审查对象。仓库同时存在大量其他未提交改动，因此没有把整个 `HEAD..working tree` 冒充为 M6-A 精确差异；本轮只追踪计划、实施证据以及以下 M6-A 生产路径和聚焦测试：

- `service/instance_management.py` 的短期管理 capability；
- `approval_ui/app.py`、`approval_ui/render.py` 的直接创建/选择与退役审批只读路径；
- `service/scheduler_bindings.py` 的实例创建、会话绑定、唯一 owner 和科学 current CAS；
- `interfaces/mcp_root.py`、`mcp_root_instance_routes.py` 及运行时/CLI 接线；
- `service/approvals.py` 对退役实例审批的待办过滤；
- `tests/operations/test_m6a_direct_instance_management.py` 及保留合同的聚焦回归。

## 2. 首次 FAIL 两项复核

### 2.1 capability 保密、认证和过期：已关闭

- capability 使用随机 96-bit nonce 和 AES-GCM；会话键只出现在经 AEAD 加密的 JSON 载荷中，URL 中只有 URL-safe Base64 编码的 `nonce || ciphertext || tag`。
- 密钥由至少 32 字节的本机 secret 经带版本域分隔的 SHA-256 派生，没有直接复用裸 secret 作为载荷或标识。
- 解封固定绑定 `scidiscovery.instance-management.v1` AAD；错误 secret、密文篡改和错误 tag 均失败关闭。
- 载荷含固定版本和绝对 `expires_at`；Root 实际签发使用 15 分钟默认寿命，验证在到期时拒绝。调用者不能经 Root 工具改变寿命。
- 聚焦测试同时验证密文字节不含裸会话键、篡改拒绝和到期拒绝；本轮额外负控确认错误 secret 与篡改 token 均被拒绝。

因此，无 secret 观察者不能从 token 恢复会话键或伪造经认证的管理载荷；token 仍按预期是短期 bearer capability，页面继续受 loopback Host、同源 Origin、表单类型/大小和 CSRF 检查约束。

### 2.2 旧实例伪审批不再成为待办且不能写决定：已关闭

- 旧实现实际出现的四个 kind：`instance_creation`、`research_instance_registration`、`session_binding`、`research_session_binding`，均从首页 pending 投影排除。
- 旧 `/review/<id>?token=...` 页面仍可读取不可变请求、manifest 和 subject，但 renderer 不生成决定表单。
- 即使直接重放旧 `/review/<id>/decision` POST，服务端也在调用 `record_ui_decision` 前按不可变 ApprovalRequest kind 返回 409；Approval 状态保持原值，`decision_ref` 仍为空，HumanDecision/Artifact 数量不增加。
- 旧 proposal、binding request、candidate 的决定应用路径已从 UI 和 Root 删除；历史表即使仍存在于旧库，也不再是生产写权威。

复审过程中曾发现两次待办过滤缺陷，均已在本轮返工并重新验证：

1. 初版先做 SQL `LIMIT 100` 再过滤退役 kind，100 条较新的旧 pending 会遮蔽较早的真实科学 pending。本轮一次性运行时负控稳定复现 `visible_count=0`。
2. 第一轮分页修复使用 `OFFSET`；扫描中到期迁移会缩短 pending 结果集，导致跳过下一条真实 pending，同时把刚过期项错误追加到 pending 返回值。本轮负控复现了“真实项仍 pending 但不可见”。

最终实现改为稳定的 `(created_at, approval_id)` keyset 分页，并在状态刷新后再次核对请求的 status；两个精确负控现已成为生产回归。退役历史不会占用 100 条真实待办额度，到期迁移也不会跳过更早的有效科学/执行审批。

## 3. 其余 M6-A 承重合同

- **原子创建/绑定**：`create_instance_and_bind_session` 和 `bind_session_by_name` 都在同一 `BEGIN IMMEDIATE` 事务内完成对象检查、创建/选择和最终绑定；元数据冲突时事务回滚，不留下半绑定会话。
- **唯一 session owner**：`scheduler_sessions.session_key` 是主键，`scheduler_sessions_one_owner(instance_id)` 是唯一索引；绑定转移先删除同一实例的其他 session owner，再 upsert 精确 session，且全程位于同一写事务。重启后从持久绑定恢复同一 current。
- **`instance_current` 纯读**：未绑定查询只读 `scheduler_sessions` 并无状态签发短期 capability；测试比较查询前后 scheduler 数据库字节完全一致。它只更新 facade 的进程内缓存，不创建 Proposal、Approval、Artifact 或绑定。
- **Root 写工具删除**：Root 目录不再暴露 `instance_prepare`、`instance_status`、`instance_select`；调度器只有 `instance_current` 返回的精确本地管理 URL。CLI 的 `instance-create` 仍是显式本机管理员命令，只创建未绑定实例，不给交互调度器增加绑定后门。
- **ResearchInstance、修订和 current CAS 保留**：实例表、语义 binding 的 `logical_name/revision/request_fingerprint`、修订唯一索引以及带 `expected_artifact_name` 的 scientific current compare-and-set 均保留；陈旧 expected ref 继续拒绝。
- **科学资格和执行授权保留**：精确 revision 的独立 review 准入仍失败关闭；普通探索仍不自动制造审批状态；Effect 仍要求精确 UI 决定，合同漂移、插件移除、错误 compiled identity 和 legacy 无 identity 的执行请求均不能启动。
- **复杂度**：M6-A 没有新增数据库表或决定收据；新状态仅为现有实例和会话绑定。新增 capability 是一个小型无状态 AEAD 值，直接管理页复用现有 loopback UI 安全边界；为兼容历史引入的唯一额外查询复杂度是有界 keyset 扫描，没有新注册表或第二审批状态机。该复杂度与必须同时“隐藏任意数量退役 pending”和“保留最多 100 条真实待办”的要求相称。

## 4. 本轮执行证据

当前最终工作树串行通过：

```text
pytest -q \
  tests/operations/test_m6a_direct_instance_management.py \
  tests/operations/test_r4_approval_ui_renderer.py \
  tests/artifact_agent/test_platform_configuration.py
23 passed in 11.31s

pytest -q \
  tests/operations/test_l2_run_invariants.py::test_root_current_is_explicit_unqualified_compare_and_set \
  tests/operations/test_l3_review_and_human_policy.py::test_review_gate_requires_a_passing_review_of_the_exact_revision \
  tests/operations/test_baseline_effect_lifecycle.py::test_installed_no_effect_execution_requires_exact_ui_decision \
  tests/operations/test_r4_execution_approval_identity.py
8 passed in 41.72s
```

另外通过：

- 错误 secret 与篡改 capability 的一次性负控，二者均拒绝；
- M6-A 相关 tracked 文件的 `git diff --check`；
- 新增 capability、Root route 和 M6-A 测试文件的 `python -m py_compile`。

未运行全量 pytest、安装 wheel、真实浏览器自动化或跨平台矩阵；M6-A 未改变插件装载和安装入口，聚焦 HTTP 测试走真实 loopback server，但不能替代 M7 的发行与真实浏览器验收。

## 5. 最终门禁

未发现仍可阻断 M6-A 的缺陷。两个首次 FAIL 项已经真正关闭，复审中新发现的 pending 过滤与状态迁移问题也已留下精确负控并在最终实现中关闭。

**最终判定：PASS；只允许进入 M6-B。**
