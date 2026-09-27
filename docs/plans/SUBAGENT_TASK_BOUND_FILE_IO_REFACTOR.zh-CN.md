# Subagent 任务绑定读写机制重构

## 目标

Alpha 阶段采用“本地原生只读、MCP 受控写入”的边界：Worker MCP 在
`worker_materialize_assignment` 后返回当前任务的明确本地路径，subagent 只用
Codex/Claude 原生读取和检索能力查看这些路径；所有文件变更由当前 worker
session 绑定的 MCP 接口执行。

## 已实现

- 公共 Worker 工具不再暴露通用的 assignment/input/table/profile 内容读取接口；
  旧接口只保留为不可发现的兼容路由。
- materialize 结果和 `assignment.json.file_access` 明确声明本地只读路径及
  `scidiscovery.worker-file-edit.v1` 写协议。
- PDF 提取只返回可复用的本地只读 excerpt 路径和大小，不再把长文本塞进 MCP
  tool result；subagent 随后用原生文件能力读取和检索。
- 冻结网页证据返回与已登记 response 字节一致的本地只读路径，不再在 MCP 结果中
  回传正文。
- `worker_file_apply_patch` 对一个任务相对文本文件应用标准 unified diff；每个
  hunk 必须与当前文件上下文和行数完全一致，否则原文件不变。
- `worker_file_json_patch` 对现有 JSON 文件提供路径级原子 `test/add/replace/remove`；
  用当前内容摘要或至少一个 `test` 防止陈旧写入，不再依赖重复文本上下文，也禁止
  root replace、move/copy 和通配路径。
- `output/result.json` 使用稳定的两空格缩进、多行工作格式；控制面在首次 create、
  后续 patch 和最终 validation 三处拒绝超过 24576 bytes 的 JSON 物理行，避免把
  生成型对象变成无法局部修订的单行文本，同时不改写数字字面量。
- `worker_file_write_begin/chunk/commit` 的 `operation=create` 只允许目标尚不存在
  的新文件；对已有文件会直接拒绝，不能用全文替换规避增量审查。
- 超过单次 tool-call 长度的 unified diff 可用同一分块接口的
  `operation=patch` 上传并原子应用；短 diff 直接使用
  `worker_file_apply_patch`。两条 patch 路径采用同一上下文匹配规则。
- patch 优先匹配声明位置；若前序修改只造成行号漂移，则仅在完整旧上下文于当前
  文件中唯一出现时自动重定位。找不到或出现多处候选分别返回
  `context_not_found`/`context_ambiguous`，绝不猜测。拒绝诊断有界返回当前目标
  SHA、声明行和首个 expected/current 差异行，或最多 16 个歧义候选行；诊断总长
  不超过 2048 bytes，便于像原生 apply-patch 一样直接重读局部并重建小 hunk。
- revision author 的 assignment 明示 180 秒首次变更边界：在该时间内完成一个最小
  合理 patch 并 checkpoint，或对 unchanged workspace 做 fail-closed checkpoint；
  禁止先在模型内规划覆盖多个问题的大补丁，再把首次写入拖到绝对截止前。
- `worker_file_move` 和 `worker_file_delete` 只允许可选 deck 文件或已声明
  collection item。
- author 只能写 `deck/project.json`、`deck/handoff.json`、`deck/files/**`；其他
  worker 只能写 `output/result.json` 及任务声明的 bundle/collection 路径。
- Codex role permission 已撤销 `ses_*/deck/**` 和 `ses_*/output/**` 原生写规则，
  workspace root 仅用于本地只读。
- author、reviewer 和公共 worker prompt 均要求局部修订优先使用 apply patch，
  禁止以全文替换冒充局部修订。
- 安装打包会剔除源码树中的旧 `build/` 产物；Codex/Claude 配置生成会删除仅由
  SciDiscovery 管理且已退出角色清单的 agent 文件，避免退休的 reviser 被重新识别，
  同时保留用户自建 agent。

## 验证标准

- 超过单次 tool-call 长度的文件可通过多个 chunk 原子提交。
- 已有文件不能通过 `create` 全文覆盖；超长 unified diff 可分块应用。
- patch 上下文不匹配时拒绝且目标文件字节不变。
- JSON patch 任一路径、test 或内容摘要不匹配时整批拒绝且目标文件字节不变；成功时
  一次原子提交所有离散字段，并返回新的内容摘要。
- 大型 minified JSON 在首次发布前被明确拒绝；同内容的 pretty JSON 可用短 hunk
  修改一个字段，且未修改字段的原始数字字面量保持不变。
- patch 拒绝返回有界、可操作的当前版本和差异位置，不回传整个文件。
- revision author 在 materialize 后 180 秒内出现首个 patch 或 checkpoint。
- 每次成功 patch 后必须重新原生读取目标；rejected patch 计入任务 performance，
  禁止原样重试旧 diff。
- 非 author 不能写 deck，author 不能写 output，路径逃逸和 symlink 被拒绝。
- 二进制 collection item 可经 base64 分块写入并安全 move/delete。
- validate/finalize 仍只处理当前 session 的完整受控文件树。

## 暂不解决

- 原生读取不是强隔离的 task-private mount；当前依靠 materialize 返回的明确路径、
  worker 指令和不可写边界降低误读概率。严格的 per-process read namespace 属于 P1。
- 兼容路由暂时保留旧的 MCP 内容读取和 primary-result upload 工具，供旧任务恢复；
  新生成的 agent 配置不会暴露它们。稳定迁移一版后可以删除。
