# U0r 注册实验执行接口独立审查

状态：**U0r 独立审查通过**。最终十六文件冻结、源码95项/安装94项（各1项不适用skip）、真实namespace入口及源码/安装交付回归各8项均已核证据；首轮三项组合缺口已闭合，没有剩余合同阻断。资格是可注册通用执行合同与cov、普通local两个实现的无模型机械验收，不包含TCAD远端执行、真实模型续接、U1预算软门禁或科研效果。

## 范围与独立性

基线为 U0 提交 `b624902`。独审者未参与 U0r 源码或测试实现，仅修改本报告；只读源码、测试、设计和父级验收日志，没有运行测试、构建、模型或 Git 写操作，没有读取隐藏评分。

审查生产首冻结 `/tmp/scid-u0r-production-freeze.json` 的十一文件，逐项 SHA 全部匹配。范围包括纯执行合同提取、旧 Bridge 重导出、公共 records/薄 CLI、local 与 cov 实现、反馈与配置冻结、真实 namespace wrapper 和 wheel entry points。完整首轮冻结如下，后续修订必须新绑定：

| 文件 | SHA256 |
| --- | --- |
| `src/scidiscovery/operations/execution.py` | `cd418cf77838ab23293138a96bc31661553d17930cae3be394bc61bd7ad3193f` |
| `src/scidiscovery/artifact_agent/execution_bridge.py` | `ac6198a60878ca3bd8ef94e1622ff9d93b30cad1884e9b4d43087e4b644e3866` |
| `src/scidiscovery/research_loop/experiments.py` | `f217cca735af32c1601e9d35fcdf62c59a20d04534f102b84cf5da1cebc5967a` |
| `src/scidiscovery/research_loop/local_experiments.py` | `9cf5b35218a55605f3b5b65a0b840423eac7d666ef19e250c583c758c162de9e` |
| `src/scidiscovery/research_loop/cov_experiments.py` | `cc4c4670a711ce30951f9651bc6bdf5023fb865135f38b729e610f86ad4bf55d` |
| `src/scidiscovery/research_loop/cov_lineage.py` | `d958cc8cdc3cb34cb7a963c244df5f33f1d840f714eb322386dca00c1efcb545` |
| `src/scidiscovery/research_loop/feedback.py` | `b0ccf19f8fd66bb306d424c3c09e3a90eb1609e9ab9bd879cbbbacc0e14e0e31` |
| `src/scidiscovery/research_loop/controller.py` | `9c1a760a7fd2afb59899f7ff6a6de278cbc703170895a0453c373647c883e2a8` |
| `src/scidiscovery/research_loop/contracts.py` | `88792472e0f70175691786e79385a50187c52e36de5489a9218cb7edc055f456` |
| `scripts/acceptance/rootless_cov_launcher.py` | `fb9a6160a54a8b8440f3cb5662169ac9e12596f5b7b070d20ed88dda698e12c3` |
| `pyproject.toml` | `c16d858a00153dd97a99e5fdd0a893443aece4091c22eaa548d44154dca40dc2` |

## 首轮历史发现与根因（第二冻结已修复）

1. **Transport 终态掩盖未知原件与执行身份。** `experiments._dispatch_descriptor` 仅以 `Records.state` 判定旧调用是否允许后续新接受；该 state 先看 terminal.returncode/cleanup/transport，而没有先纳入 completed.status=unknown。cov 无法建立精确公开回执时虽产出 unknown completion，下一调用仍可能被允许。终态优先也使 completed 缺失时的半写 process/PID失配被当成 known_success。修复应沿唯一公共原件 owner 保留未知状态与原接受身份；不能将 process exit0 直接当精确结果成立。
2. **Local 实际执行文件与冻结字节不一致。** `Records.accept` 归档 source.py，但 local 的 accepted.command 仍以可写原 payload.local_path 为参数；local completion 仅核归档 source 的 proof，没有证明实际执行的是同一字节。原文件在准备与运行之间改变时，可归档A、执行B并返回 known_success。应使实现执行冻结准备字节，或保留同等实际源完整性检查；不能以新的文件hash重解释旧证据。
3. **中性接口丢失外部身份映射。** 首版 core 忽略 `adapter.submit` 返回的 external_run_id，并把控制 call_id 传给标注 external_run_id 的 result/status/collect；公共 state 又假定全部作业都有 Linux PID 与本地 returncode。两个本地实现能够掩盖该假设，非本地注册实现不能在同合同下接入。U0r不必实现TCAD，但必须明确 ManagedInterface 参数是受控call_id、由实现在同原件中维护外部映射，或保留外部绑定并消费实现规范化状态；不允许新增另一账本，也不宣称两个本地实现已证明远端生命周期。

已直接向实施者与父级给出上述位置及最小修复方向。稳定调用名的实际合同已澄清：每次显式正常run代表新意图，由控制生成新call_id；幂等保证作用于同acceptedID的submit/lookup，已有unknown会阻止后续新run。旧设计中“同手填name自动返回原调用”的表述撤回，本轮不要求新增模型填写的name接口。

## 第二冻结复核

`/tmp/scid-u0r-production-02.json`十一生产文件与`/tmp/scid-u0r-source-02.json`十五生产/测试文件已逐项核 SHA 全部匹配。相比首冻结，仅纯接口、公共生命周期、local和cov实现四个生产文件改变，其余生产绑定不变：

| 修订文件 | SHA256 |
| --- | --- |
| `src/scidiscovery/operations/execution.py` | `3acf11d24bce98b404d8c29d8052c0fc82811ef739cbb00dfb7fd96d682d36e3` |
| `src/scidiscovery/research_loop/experiments.py` | `9a2a28e5c9d5758db81dd539afb4f0892f7c800ebb6d55f35fed7468ef3b9068` |
| `src/scidiscovery/research_loop/local_experiments.py` | `794082218c65d47d0c7730d06f933204b0f4221ef9b3e539e26b72884e523a0c` |
| `src/scidiscovery/research_loop/cov_experiments.py` | `7fd4b5cc5d86c54838050a8f129d81aeaebc8d5e05bef9cd075fb4a35b140874` |
| `tests/research_loop/execution_fixtures.py` | `b568ca89d31f13f97afa9ffadc3421ecb0ab2be70014912f76b9833caedfe97b` |
| `tests/research_loop/test_registered_experiments.py` | `8079bb455454a61722cdaf7c9e795229c0bc025305da049a64259cbc44c1fa54` |
| `tests/research_loop/test_cov_lineage.py` | `0cdbec135b70c6e77fb54fe9bc592d2dcabfc4c196d9dd3f0a62815ad37f282b` |
| `tests/research_loop/test_live_feedback.py` | `1a78308fb00ead067932c5c198e295b08f1a3f4140430dbb9c1ecb0f954540a2` |

三项根因逐行核对如下：

- 公共Records只认canonical completion及exact call/scope，Linux PID、returncode与transport证明移回Local实现。缺completion不以旧terminal填成功；unknown completion保持unknown，公共新run通过adapter的中性状态阻止未知或在途重提。cov fallback继续使用既有四原件proof集合，不扩大领域资产预览资格。
- 普通local实际argv使用控制归档source.py，真实barrier夹具在进程启动后、解释器读脚本前将原源A改B，要求stdout仍为A。`__file__`现指向归档位置，cwd另行配置；其他import、环境和依赖没有因此被冻结，不能宣称完整执行环境复现。cov保原科学CLI路径语义，并在执行前/精确回执核原源字节。
- 公共owner在同call新增submission.json保存submit返回external_run_id；Managed的status_details/result参数明确为control call_id，collect_original/cancel_original负责原外部映射。lookup只恢复该绑定，不重新submit。非local不同ID注册CLI夹具没有process/terminal文件，仍可query/collect/lookup，证明core不再要求Linux进程模型；它是合同比对，不是TCAD远端验收。

新增localhost反馈夹具通过host配置与CLI读取，无history_observer、无领域metric也能观测，且重复读不写科学或预算原件。各项测试源码、最终执行通过和安装绑定已核。

## 已核对的结构

- `scidiscovery.execution_interfaces` 是独立薄 CLI 发现 surface，复用轻量 RuntimePluginFactory/RuntimePluginContribution；`scidiscovery.plugins` 不增项，旧 daemon 的全installed-factory mandatory config集合不扩大。
- 只选择匹配 entry point，不调用 `compile_installed_catalog`，不启动 MCP、ArtifactService、ApprovalService 或 SQLite ExecutionService。普通 local 与 cov 位于注册实现中，core 不 import cov或解释cov results。生命周期 flags 与旧 `capabilities()->tuple[AdapterCapability,...]` 分开，缺声明为false，不以方法存在推断权限。
- 原 Bridge 仅重导出提取的纯接口类型，服务流程未改。薄循环的模型 native/continuation seam 与实验执行器分开。
- 公共 `Records` 在 `experiments.py` 拥有 accepted/process/terminal/completed 原件，沿原 calls 目录；没有另建账本。cov 原执行循环已替换为通用 dispatch，local 实现拥有唯一实际 subprocess transport，cov复用并解释领域回执。
- 真实 `rootless_cov_launcher` 的 exp run/query/collect/cancel 包装器已指向注册 CLI；host configure 冻结注册配置并向namespace只读挂载，实际 Popen 保持在原W namespace 中，不移到无限制host。
- 接受短锁只提交metadata，准备/源码扫描在锁外，执行lease可覆盖作业；U1 review/budget算法仍未实现，不授予软准入资格。
- live metadata 与 final asset qualification分开；cov最终路径仍以 `_completed`默认完整校验，普通local最终校验由completion proofs负责。第2项修复是其实际执行内容绑定的必要补全。

## 已观察验收与限制

独审者实际读取外层 `.trial/u0r-source-01-20261013/batch-001/pytest.log`：**8 failed / 82 passed / 43.85s**。失败覆盖 process半写/PID失配被错误终态覆盖、畸形parent投影未硬拒，以及cov unknown fallback的新process/stderr proofs不在旧轻量白名单。实施者已获父级授权解冻修复；首轮绿色部分不能替代完整修后门禁。

第二实现夹具用普通local命令观察无领域metric的生命周期；unknown恢复以删除终态/完成原件模拟未确认状态，lookup-loss以删除submission绑定验证原ID重建，不应描述为真实远端提交回包丢失或原生resume资格。最终安装必须验证实际entry point发现和console，不能以source metadata helper或fixture对象装配代表注册完成。

## 最终冻结与通过证据

最终 `/tmp/scid-u0r-source-03.json` **十六文件**逐项 SHA 全部匹配；生产十一项与第二冻结完全一致，没有最后生产改动。最后新增测试delta仅为`test_cov_delivery_lineage.py`导入源码发现fixture，确保独立运行不依赖其他测试的registration缓存：SHA256为`129742067e13a372e82d6b8d078bb222c88473083476068729d09238a4afbf14`。该测试在安装环境使用wheel真实entrypoints，没有新增source-only fallback到生产。

独审者实际读到以下父级执行结果，没有自行运行验收：

- 外层 `.trial/u0r-source-02-20261013/result.json`：source lane passed、退出0、cleanup_complete，无资源停止；`batch-001/pytest.log`：**95 passed / 1 skipped / 47.00s**，覆盖注册接口、live反馈、cov原件、nativeCLI与旧runtime plugin配置。skip为cov参数下不适用的普通local冻结源测试。
- 外层 `.trial/macro-role-installed-20261012/artifacts-u0r-20261013/u0r-installed.log`：**94 passed / 1 skipped / 40.40s**；`u0r-installed-result.json`退出0、model_requests=0，八个关键模块来自site-packages且各自SHA与审查源码一致，包括纯接口、旧Bridge、公共driver、local、cov与反馈。普通local/cov注册发现和真实console通过；不同externalID夹具只证明注册合同，不是远端验证。
- 同目录`result/result.json`：fresh wheel **`687342ce4b07c7d11dcc3696053d122c6e3badc0926fcd8311a25cf3817da32f`**；26个research-loop模块绑定，真实安装CLI无模型H→A→W→A、no_replay、route_context_preserved均通过，model_requests=0。
- 同目录`u0r-namespace-02-result.json`/`.log`：父级实际launcher的prepare_home/outer/bwrap→exp wrapper→注册CLI→cov fixture与lineage-status，两个命令退出0、stderr空，真实返回known_success与唯一同call计数，model_requests=0。独审者另读取外层`u0r_namespace.py`和`run_u0r_namespace.py`，确认直接调用所审launcher的prepare_home与outer，bwrap argv来自outer，使用fresh venv的隔离Python、清除source PYTHONPATH并受父级serial lock管理；只有公开backend fixture来自测试目录。首namespace夹具误用默认`/opt`run alias被原身份校验拒绝；修订夹具对齐实际EXP_RUN_DIR，生产未改。此项证明namespace发布入口与注册接线，不证明完整native模型启动、模型权限遵循或真实科研模型遵循。
- 同目录`u0r-delivery-check.log`：安装封存→交付actual leaf关联回归 **8 passed / 3.84s**。
- 外层 `.trial/u0r-delivery-source-20261013/result.json`：退出0、cleanup_complete；`batch-001/pytest.log`：独立源码交付回归 **8 passed / 3.33s**。只补发现fixture的最后delta已经单独覆盖，无需重建未改变的production wheel。

最终观察、执行身份、字节资格、注册入口与封存/交付路径共同支持本范围通过。没有用首轮失败、基线行为或模拟恢复扩大资格；后继U1/U2/U3及真实远端能力分别验收。

本轮只审 U0r：不运行科研模型、不启动U4、不要求实现U1预算或U2/U3。TCAD仅审核接入合同，任意未受管shell保持覆盖未知；不声称恶意绕行隔离、远端恢复或科学效果。
