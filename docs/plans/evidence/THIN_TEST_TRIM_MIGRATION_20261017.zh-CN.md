# 薄层测试精简迁移静态记录

日期：2026-10-17。依据独审 `THIN_TEST_REUSE_REVIEW_20261017.zh-CN.md`，仅修改下述五个测试文件。未改生产代码、根 conftest、安装消费者或 research_loop fixture；未提交。此记录供独立静态评审，**不构成测试通过或生产能力验收**。

## 已跟踪测试的迁移

| 文件 | 精简与保留保护 |
| --- | --- |
| `tests/research_loop/test_composed_execution_results.py` | 去掉 `SCID_COMPOSED_INSTALLED` 换解释器入口。opaque 的 observer×private 9 行收为 4 行，仍含无私有结果、native/local-like 两种私有形状，以及 observer 缺失/空/失败；显式非法协议 6 行收为 2 行，保留两种形状及失败 observer 的组合负控。无候选推断、诊断、原调用 reconcile、无 collect、身份篡改及旧封存不改写断言保留。整个模块明确 `process_e2e`。 |
| `tests/research_loop/test_registered_experiments.py` | 公共生命周期 fixture 由 local/cov 双跑收为 local；删除宿主 `shutil.which('scid-experiment')` 自动选择，固定当前解释器的 module 入口。成功/失败、running 可见性、unknown 不重发、lost reply 原绑定恢复、冻结脚本、模块隔离及 opaque 外部身份检查均保留；cov 的 receipt/parent 差异由原 `test_cov_lineage.py` owning 检查保留，本轮未改该文件。实际 CLI/进程用例标 `process_e2e`，两个直接契约负控保留 source。源码入口证据不代表已安装 console 可用。 |
| `tests/research_loop/test_local_managed.py` | 删除四个独立重复 dispatch，见下表；其余成功事实、结果负控、unknown、owner/watchdog/cleanup 及归档导出保护保留。进程用例标 `process_e2e`；输出 metadata 容量和 33 MiB 流式快照标 `stress`；纯 prepare 模式矩阵留 source。 |

### 四个被删除用例的有效保护去向

| 删除用例 | 保留方式 |
| --- | --- |
| `test_full_input_inventory_is_not_limited_by_legacy_capacity_constant` | 移除无运行时读取的 `MAX_INPUT_BYTES` monkeypatch；首个 snapshot/argv 用例改为明确检查 `run.py` 和 `inputs/value.txt` 在快照中。真正超旧资产容量且禁止整文件 `read_bytes` 的 33 MiB 用例保留。 |
| `test_empty_input_directories_do_not_hit_an_arbitrary_inventory_cap` | 移除无效 `MAX_SCAN_ENTRIES` monkeypatch；在首个 snapshot 用例加入一个空输入目录，仍须成功。没有声称一个空目录跨越旧 1024 项阈值。 |
| `test_r2_empty_output_directories_do_not_erase_known_execution` | missing-result 参数行实际创建空 artifacts 子目录，仍检查进程成功、missing、outputs 为空，并明确 `completed.json` 已存在。 |
| `test_r1_input_scan_excludes_prior_artifacts_subtree` | 首个 snapshot 用例实际写入 `artifacts/prior.txt`，断言 accepted.snapshot_files 无 `artifacts/` 项、原 prior 内容不变、结果没有写回输入树。这比原来仅造空目录后断言成功更直接。 |

## 新 P1 与容量测试的单独处理

以下两文件在本轮开始时已是未跟踪的新测试，依赖同工作树尚未提交的对应生产补修；本次只精简其形状，不能将其证明归到旧 HEAD。可随各自生产节点收口，不要求加入先行的已跟踪测试迁移提交。

| 文件 | 本次精简 |
| --- | --- |
| `tests/research_loop/test_execution_configuration.py`（新 P1） | 去掉 `SCID_EXECUTION_INSTALLED`；remote 保留一条真实 CLI→native→experiments 接线与重复 run 幂等链；composed 改为较小的 operator freeze→dispatch→原调用 query 接口验收。大 public schema 从 H/W/A 链移为独立 `stress` freeze→describe，仍检查完整字段、字节数及 descriptor hash。宿主字段用独立字面列表列出 8 项，直接调用验证器，另留 1 个 CLI 拒绝且实例未创建。包 modify/add/delete/symlink 全集直接验证 operator 冻结身份和 accepted 使用的身份验证器；一个 modify 代表保留 query/reconcile/run 三个 CLI 动作，原件不变且 calls 仍为 1。去掉 `len(code)==3`。默认 local cwd 改为 prepare→W host configure→真实 CLI 单脚本，调用 cwd 故意设为脚本子目录，相对 workspace 原件和 cwd proof 必须成功。提前构造工厂、非法 binding/config 的 Popen 禁止哨兵、外部模式冲突等保留。 |
| `tests/operations/test_tcad_full_transport_records.py`（新容量补修） | stdout/stderr 和完整日志由 9 MiB 收为旧 8 MiB 界限再加 1 字节，完整重复 bytes 比较改为长度/末尾/逐字节计数；日志用流式实际/预期 SHA-256，不再 read_bytes 大副本。descriptor 数和 runner 记录数按小 record 的编码长度计算刚超过相应旧界限，避免再构造完整模型 dump 列表。descriptor 篡改/越界与日志幂等/同长度篡改改为小输入。SSH 本地 stand-in 的响应保留超 8 MiB，发送小请求；runner 请求保留超 1 MiB；transport CLI 请求从 2 MiB 收为 1 MiB+1，独立读取边界与显式 quota 保护保留。完整 attestation 由 9000 收为 8191 outputs（8193 checks，跨旧 8192 checks），仍保留末项字节篡改使 verdict 翻转；collection_errors 为 4097。重复名/路径/escape 用 2 项，undeclared rationale 用 64 项（仍断言 >4096 及所有名称），terminal_error 从零 outputs 起建并保留 8192 字符全文检查。6 个容量场景标 `stress`，quota/timeout 标 `process_e2e`，小负控留 source；名称明确本地 stand-in，未声称真实 SSH/solver。 |

## 静态核对与边界

- 五文件及保留的 `NATIVE`/`LONG_NATIVE` 字符串通过 Python AST 解析；没有 import 测试或生产模块。
- 已跟踪三文件的 `git diff --check` 无空白错误；五文件的 AST/空白检查均完成。
- 静态搜索确认五文件中无两个 `SCID_*_INSTALLED` 分支、无两个无效容量常量 monkeypatch、无 `shutil.which` console 自动选择或固定 code 文件数量断言。
- 只按 AST 字面参数行与原 fixture 参数计数（**不是 pytest collection，包含原 skip 行**）：composed 21→12，local 27→23，registered 17→10；新 P1 24→26（直接负控增加，完整进程链减少），新 TCAD 12→13（大输入负控拆为小输入）。总计 101→84。当前五文件为 source 33、process_e2e 42、stress 9；这只是本范围标注，未审计其余 suite 的隐含进程。
- 主要重复进程路径：宿主字段 prepare CLI 8→1；包变化 query/reconcile/run 12→3、其前置真实 dispatch 4→1；P1 内 H/W/A 链 3→1（另保留单脚本 cwd 的 CLI）；composed 私有结果/observer 完整封存场景 15→6。没有测量运行时间、RSS 或内核资源域，不能据静态计数声称资源事故已解决。
- 未执行 pytest、collect-only、build、install、环境创建、模型、SSH 或 solver；运行时正确性、实际 wheel/console、资源使用及完整 suite 结果均未验证。等待独立静态评审后由后续授权的受控检查验证。
