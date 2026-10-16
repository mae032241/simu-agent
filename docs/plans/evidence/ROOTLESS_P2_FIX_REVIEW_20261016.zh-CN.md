# 两项 P2 修复独立审查

结论：**PASS（限这两项 P2 修复）**。未发现应阻断这两项资格的缺陷。现有回归批次仍有七项基线 CLI 测试失败，不能声称整个 CLI 套件或完整运行链路已通过。

审查者未参与修复，只读检查仓库；仅在 `/tmp` 写入补测脚本、证据与本报告。未修改生产文件、未运行真实模型、未 commit/push。应用 `scid-cross-boundary-review` 与 `scid-change-scope-checks`。

## 受审对象与指纹

- 仓库：`/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`。
- 分支：`dev`；HEAD/base：`d7eb88a4920f0241137d3807615c9efefa4ddec0`。
- 受审未提交改动：`src/scidiscovery/research_loop/native.py`、`controller.py`、`tests/research_loop/test_role_profiles.py`、`test_closeout_protocol.py`，87 insertions / 13 deletions。
- `git diff --binary -- <上述四文件>` SHA-256：`e05873d89c22942975992566b62bdb66d34f8a8899ba7a28b69d58232e070d14`。
- `/tmp/scid-p2-implementation-20261016.patch` 与该 diff **逐字节一致**，同一 SHA-256。
- 原有未跟踪 `docs/plans/evidence/*` 不属本次受审变更，未修改。

文件 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| native.py | `575fcedebaa89a66df41dad8ab40485ff481e87b2ca6cdccccab90ac78d53b2c` |
| controller.py | `6af90a7e5392a320b2b5310a66f2433b1f772fb8e26164742130b0c368faa14f` |
| test_role_profiles.py | `80fa4f547deb6c8345be4bdc5c6b8bf47ebe525b244877b70cdf571be7b25b49` |
| test_closeout_protocol.py | `13c2a1ed30172404de1302fe6a9db044d778cce8eb41fa4574c87f7388de2ef0` |

## 配置传播与专用启动器兼容

`native.py:147-150` 在公共 argv 构造处只添加一次 `service_tier`，取值来自 `profiles.validate_intent` 已选出的冻结配置。raw Codex 分支 `:154-159` 删除原先重复配置；custom launcher 不再依赖显式 `role_profiles` 才收到 global tier。原有 job/intent 不新增 profile 绑定的兼容行为仍保留。

同 session resume 在 `native.py:179-186` 从同一个 fresh argv 收集 `-c` 配置，并放在 `resume` 子命令前；因此 tier 与 reasoning effort 一同传播。new_context 不走此重组，也直接保留公共 argv。profile 校验与原始 task/session/header 校验仍在提交前执行。

`test_role_profiles.py:108-141` 实际启动本地替身进程，覆盖角色覆盖项及无 role_profiles 的 global default/priority，读取 fresh/resume 两次实际 argv。`:144-171` 经 `controller.run` 覆盖 raw Codex 与 wrapper，检查 model、effort、tier 各准确出现一次，并检查 raw Codex 专属配置没有进入 wrapper。

专用 `scripts/acceptance/rootless_cov_launcher.py:289-303` 原已允许两种配置键并要求值匹配，不会把新增 global tier 当成未声明参数。独立补测进一步调用真实 `native_args` 与 accepted-attempt/session 校验：无 role_profiles，default/priority × fresh/same_session resume 共四种组合全部接受；每种再将 tier 改错均得到 `native_config_override_rejected`。补测保留在 `/tmp/scid-p2-independent-probe-20261016.py`，输出与资源记录位于 `/tmp/scid-p2-independent-probe-20261016/`。

## closeout 限制摘要与原件

`controller.py:627-634` 对已验证的最后科学结果调用现有 `contracts._whole_limitations`，先受 1024 UTF-8 字节限制，再取前四条整条限制；未截断作者单条文字，也未重写科学原件。`limitations_omitted_count = 原条数 - 实际显示条数` 同时计入字节与条数造成的省略。`limitations_ref` 明确指向同一 `scientific_output_ref` 的 `limitations` 字段。

`contracts.py:165-171` 按顺序保留能容纳的完整条目；超长条目不会阻止后面的较短 caveat。四条截取只会进一步缩小该数组。CLI 使用 `ensure_ascii=False` 输出，所用 UTF-8 测量与实际字符编码一致；1024 限制属于限制数组，未声称整个 closeout 响应有同一字节上限。

`last_science` 经 `contracts.validate` 读取得到；该函数验证 seal、原始输出与当前 execution record 的散列及内容。`execution.raw` 使用同一 record 解析路径，包含续跑原件定位。无原件时返回 `[]`、省略数 0、两个 ref 均 null。

`test_closeout_protocol.py:95-115` 经真实模块 CLI 的 closeout、status.closeout、重复 closeout、export-only 四种公共视图核对：空数组、单条、超过四条、多字节超长条目、引号/反斜线/换行、完整原件与字段定位，且原件不含新增的机械摘要字段。`:118-128` 覆盖尚无科学原件的 export-only。`pyproject.toml:28` 的已声明 `scid-research` 入口使用同一 `cli.main`；此处没有安装 wheel 后再执行 console script 的证据。

## 证据与失败判定

已审阅提供的 result.json、资源记录及 pytest.log：

| 证据目录 | 结果 | 对本次结论的作用 |
| --- | --- | --- |
| `/tmp/scid-p2-red-20261016` | 6 failed / 2 passed，16.25s | wrapper 无 role_profiles 两例缺 tier；closeout 四例缺 omission 字段或保留超长条目，负控命中目标缺陷 |
| `/tmp/scid-p2-green-20261016` | 87 passed / 8 failed / 5 deselected，143.88s | 四文件回归中配置与 closeout 目标测试通过；一项新增空原件 fixture 错误及七项旧 CLI 错误单独处理 |
| `/tmp/scid-p2-empty-fixed2-20261016` | 1 passed，0.26s | 新增空原件 fixture 改为合法 export-only policy 与足够预算后通过；生产修复未因该 fixture 调整 |
| `/tmp/scid-p2-baseline-tests-20261016` | 同七项 CLI 全失败，4.55s | 独立 HEAD 副本复现，定位既有测试债务 |
| `/tmp/scid-p2-raw-home-20261016` | 2 passed，0.88s | raw Codex inherited home/config 相关回归通过；名称含 live，但使用本地替身，不是实际模型调用 |
| `/tmp/scid-p2-independent-probe-20261016` | 四正例及四反例全部通过，监督耗时 0.751s | 独立补齐专用 launcher 无角色配置的 global tier fresh/resume 兼容证据 |

独立运行 `git diff --check` 通过。补测经 `scripts.run_tests.serial_lock` 与 `run_one` 包装执行 `python -B /tmp/scid-p2-independent-probe-20261016.py`，使用仓库默认资源配置，tree RSS 高水位 40,583,168 bytes，无资源触发，cleanup_complete=true。未绕过串行锁。

七项 CLI 基线失败不能只因“基线也红”而忽略。检查表明：`test_native_cli.py:48-51` 旧替身对 `job['final_response']` 的字段判断没有生成当前 schema 需要的完整结果；实际 run/continue 在 `invalid_fields` 处停下。单独的 `:102-112` 枚举测试也缺当前必填 `implementation_selection` 等字段。后续三项读取 node 003 的 FileNotFound 是前序未建完整链路的结果。基线副本的 native.py、controller.py、test_native_cli.py 已逐字节比对 `git show d7eb88a:<path>`，三者均一致。

这项债务削弱普通 H→W→A、pause/continue、完整 status 只读及后继材料完整性测试的现有证明，必须保留在总体回归结论中；若主任务要求这些能力或“全套回归通过”，它就是剩余 gate。本次两项资格具有直接独立证据：配置测试真实执行 fresh/resume 并检查 argv；closeout 测试真实执行所有受影响公共视图且读取原件。因此七项旧测试失败**不阻断这两项 P2 的局部验收**。

## 剩余限制

- 未做真实模型、实际 OpenAI 服务 tier 接受性或所有第三方 launcher 的验证；custom launcher 必须支持现有 Codex 配置参数协议。仓库内专用 rootless launcher 已检查并补测。
- 未运行完整 pytest、科学控制 bench、已安装 wheel 或实际 console script；本次变更不涉及打包、schema、科学结论、预算授权、外部提交或 lifecycle 状态转换，已有直接回归足以支持局部判断。不能外推完整系统资格。
- 原有七项 CLI 测试夹具债务尚未修复；本报告不把失败批次标记为整体通过。
