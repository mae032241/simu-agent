# B2 独立审查（2026-10-16）

最终复审结论：**PASS，限本次发布依赖闭包修复**。初审的 P1/P2 已由精确三文件修订与实际生成树证据关闭；没有剩余 B2 阻断。此前 14 项 broader history/guidance 失败继续保留，六组 collection 成功不表示完整 suite 执行通过。

以下为初审记录，描述旧补丁 `1a2e2508…` 及旧生成树；失败证据完整保留，当前状态以文末“最终复审”部分为准。

初审结论：**阻断 / 不通过**。精确两文件补丁确实修复多项发布遗漏，但新增发布脚本仍缺传递依赖；持久生成树的精确消费者已实际失败。B1/B3 的既有局部 PASS 不受此结论改变。

## Findings

### P1：新发布的权限探针缺 canary.py，真实生成树消费者必然失败

- 最紧位置：`scripts/build_git_release.py:89` 新增 `scripts/probe_covshift_permissions.py`，但 TOOLS 没有其 `scripts/acceptance/fixtures/covshift_permissions/canary.py` 依赖；使用点为 `scripts/probe_covshift_permissions.py:106`。
- 路径：已发布 `tests/operations/test_codex_permission_profiles.py::test_host_preflight_uses_only_synthetic_inputs_and_arg0_runtime` → `prepare()` → `shutil.copyfile()`。canary.py 存在于原仓库，最终发布树与 manifest 中均不存在。
- 影响：新增发布的权限预检无法准备 synthetic canary；生成树测试仍然不自足。17 项映射内文件全部被正确复制，但该映射遗漏了脚本的传递文件依赖。
- 独立实际负控：在 `/tmp/scid-b2-final-release-20261016/release` 作为 cwd，用**生成树自身** `python -B scripts/run_tests.py --lane source --output /tmp/scid-b2-independent-canary-20261016 tests/operations/test_codex_permission_profiles.py::test_host_preflight_uses_only_synthetic_inputs_and_arg0_runtime` 运行。结果 **1 failed in 0.12s**，FileNotFoundError 精确指向生成树内缺失 canary.py。外层资源监督 0.679s、RSS 56,012,800、cleanup true、无 memory trigger；serial_lock 已释放。
- 证据：`/tmp/scid-b2-independent-canary-20261016/{result.json,batch-001/pytest.log,batch-001/resource.json}`。
- 修复方向：复制该准确 synthetic fixture，增加独立 required 断言，并在生成树门禁执行上述精确消费者。仅 collection 无法发现函数体内的这次缺文件。

### P2：新发布 CLI 合同含两个未发布的文档链接

- 发布入口 `scripts/build_git_release.py:55` 新增 docs/ROOTLESS_CLI.zh-CN.md；该文档 310–311 行的真实“设计 / 验收记录”链接分别指向 `docs/plans/evidence/ROOTLESS_WORKER_RESUME_DESIGN_20261012.zh-CN.md` 和 `docs/plans/evidence/ROOTLESS_N6C_WORKER_RESUME_20261012.zh-CN.md`，最终发布树不含目标。
- 影响：读者从 README 进入新 CLI 合同后，无法打开其用来说明当前恢复能力与验证范围的引用。当前链接检查列表没有加入新发布文档，故 gate6 未检查这两条链接。
- 这两条是正文引用，不是该文档 artifacts/history 示例路径。无需因此盲目发布整个归档；可为发布文档改写为完整自含的说明，或显式出版允许的必要参考，并针对真实链接验证。
- 静态证据：`/tmp/scid-b2-independent-static-20261016.json`。

## 精确范围与指纹

- 仓库 `/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2`；base / HEAD 为 `70afb76004b0532e5cd26f9bfd93529660785853`。
- 审查文件仅 `scripts/build_git_release.py`、`tests/artifact_agent/test_deploy_scripts.py`。
- `git diff -- <这两文件>` 与 `/tmp/scid-b2-fix-20261016.patch` 的 SHA256 均为 `1a2e2508153b8bd07aefaac4e80cca3785e7bbb53c6d49a22bd8527425fae896`，与委派绑定一致；`git diff --check` 通过。
- 应用 scid-cross-boundary-review / scid-change-scope-checks；沿 builder allowlist → text/mode normalization → scanner → manifest/archive → generated-tree pytest → isolated wheel consumer 追踪。只读审查，无 repo 修改、commit、push、模型或 solver 调用。

## 已核对的有效证据

- 17 个映射依赖都在持久生成树与 manifest；完整 manifest 836 个条目逐项 SHA256 校验通过（加 manifest 共 837 文件）。manifest SHA256 `9b10dda24d8b33a08f53b4116f04625bde3176e4e35feaa34a3c886de13ced75`；archive SHA256 `557565aed62af450d78a308469732617d1ff3d34cc993f9e9a2ce8e74907c9c1`，与 summary 一致。
- `/tmp/scid-b2-release-gate6-20261016`：outer installed gate 1 passed，50.262s、RSS 303,968,256、cleanup true。六组 collection：main source 3888/4180、installed 21/4180、process 269/4180；research source 1167/1172、installed 0/1172、process 5/1172。source 精确消费者 72 passed；offline wheel 消费者 3 passed。
- `check_release` 的 `cwd=output` 正确；外层 run_tests 清除 PYTHONPATH 等覆盖，生成树 pyproject 使用相对源路径；安装 fixture 从其自身 `__file__.parents[2]`（生成树）构建环境，清除 PYTHONPATH、禁用户包、断言包/Pillow 位于隔离 venv 内。未发现用原仓库 overlay 冒充生成树的情况。

## 对门禁调整的判断

- **分两组收集合理**：main 与 research 各含同名 `test_review_admission`，且存在 sibling imports；分别用新进程完整收集而不删除任一文件，解决导入命名碰撞，不降低选中集合。
- **空 installed research lane 合理**：当前 source/process 已覆盖该组 1172 个测试，installed 确为全部 deselected；pytest 标准 collection error 退出码是 2，不会被仅允许 collection 的 exit 5 分支接受。实际日志没有 error。`'deselected'` 文本判断较简，但本次已观察的空组是合法空 lane，未见掩盖错误。
- **heading anchor 扩展合理**：实际受影响锚点仅为 INSTALL.md `legacy-uncertain-submissions` 与中文对应标题；ASCII/中文简单 heading 的当前规则正确，其余锚点仍由显式 id 检验。该小规则不是完整 GFM slug 实现，但本次实有链接没有依赖其不支持的重复标题、emoji 或内联 HTML。
- **gate5 缩到精确消费者本身可接受**：保留的 gate5 有 82 passed / 14 failed；13 项旧 history 渲染 / old projection fixture、1 项 guidance 默认文本 2342 bytes 与旧 <=2048 断言失配。B2 未改 history/guidance 生产语义，缩小 smoke 不等于证明这些失败已解决。summary 已保留失败与局限，不能声称全套 green。
- **最终范围仍不足以批准闭包**：gate6 的 72 个执行场景没有覆盖 probe 的 `prepare()` 函数；collection 成功不证明函数体所需资产存在。本审查实际复现的 P1 是与本次发布闭包直接相关的缺陷，不属于 gate5 的旧 fixture 问题，必须补齐后重审。

本报告不要求全量执行所有测试、实时 Codex 或真实外部科学实验；需要针对上述新增发布依赖修复后，在实际生成树执行其消费者并重新核对精确 diff / manifest。


## 最终复审：PASS（2026-10-16，修订 2）

### 当前精确绑定

- B1/B3 已先行提交；当前 base / HEAD 为 `3d2cc897608eac00689e3fe61c50351d0b59ddb8`。
- B2 最终三个文件：`scripts/build_git_release.py`、`tests/artifact_agent/test_deploy_scripts.py`、`docs/ROOTLESS_CLI.zh-CN.md`。
- 当前三文件 `git diff` 与 `/tmp/scid-b2-fix2-20261016.patch` SHA256 精确一致：`e1935e40fcaf66a0ecc4bb0284dca020176f2e7218c95f303320a9065587eda0`（11017 bytes）。`git diff --check` 通过。

### 初审问题关闭

- **P1 已关闭**：TOOLS 与测试独立 required 清单均新增准确 `scripts/acceptance/fixtures/covshift_permissions/canary.py`，且 generated-tree source smoke 新增实际调用 prepare() 的 `test_host_preflight_uses_only_synthetic_inputs_and_arg0_runtime`。修复只出版原有 synthetic fixture，没有修改其权限断言或消费者实现。
- 原失败 `/tmp/scid-b2-independent-canary-20261016` 保留；修后持久生成树自身 run_tests 的同一精确消费者 `/tmp/scid-b2-final-canary2-20261016` 为 **1 passed in 0.07s**，监督 0.379s、RSS 53,944,320、cleanup true。此实测关闭函数体传递依赖缺口。
- **P2 已关闭**：CLI 末尾两条未发布的历史参考链接被改为自含说明，明确 fake/installed 只验证本地输运与拒绝路径，并保留“实际 Codex 同线程有效性、增量用量与权限尚未验证”“零模型检查不能授予实际 native 恢复资格”与保留原 attempt 失败/限制的要求。没有借修链接扩张科学或 native 恢复资格。
- 文档链接检查加入新发布 CLI 文档；先剔除 fenced / inline code，再检查正文相对链接，避免把 artifacts/history 代码示例误当发布依赖。独立在最终生成文档重算后没有残留的真实内部引用；先前失效的两条引用已消除。其余五份文档仍执行同一正文链接与锚点检查。

### 最终生成树与证据

- `/tmp/scid-b2-release-gate7-20261016` outer installed gate **1 passed in 53.85s**；监督 54.222s、RSS 301,715,456、cleanup true。source 精确消费者 **73 passed in 3.58s**；offline wheel 消费者 **3 passed in 9.72s**。
- 六组收集仍完整执行：main source 3888/4180、installed 21/4180、process 269/4180；research source 1167/1172、installed 全部 1172 deselected、process 5/1172。这证明相应收集路径完成，**不证明 5352 项测试全部执行通过**。合法空 installed research lane 的前述判断不变。
- 最终持久树 `/tmp/scid-b2-final-release2-20261016/release`：审查者独立逐项校验 **837 个 manifest 条目全部 SHA256 正确**（加 manifest 共 838 文件）。三个改动文件及 canary 资产同时与当前源文本规范化结果、tar.gz 成员逐字节一致。
- manifest SHA256：`2b1f3eace0b4f415dbee26dd63abb3fc612693b8ca35bb849c06501b4270992d`；archive SHA256：`e07b874f66ba3603621d9684dd8ace086670242b745cd21a0ff8f7eddb815718`。
- 独立静态复核结果：`/tmp/scid-b2-independent-final-static-20261016.json`；执行者汇总 `/tmp/scid-b2-summary2-20261016.json` 与观察到的日志、产物一致。

### 最终资格范围

本次精确发布闭包修复可通过，未发现新的阻断。保留 gate5 的 14 项旧 history/guidance 失败记录及初审负控，未将它们改写为成功。没有重复已充分通过的大门禁、调用模型、运行真实 native resume、solver 或浏览器；本结论不外推这些资格。审查者始终未修改 repo、commit 或 push。
