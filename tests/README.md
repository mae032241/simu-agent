# 测试分层与运行

测试按需要证明的边界划分。默认 `pytest` 仅选择源码层，`-m` 不会越过层选择；安装、进程、大文件和在线平台必须显式选层。资源敏感环境应始终使用下面的串行入口。

| 层 | 选择参数 | 覆盖范围 |
| --- | --- | --- |
| 源码 | `--lane source` | 业务规则、合同、资格、审批、恢复、非法输入；允许小型本地命令，例如 `bash -n`。 |
| 安装 | `--lane installed` | wheel 资源、依赖解析、真实 entry point、解释器隔离、一个代表性安装后完成链；不重跑源码业务矩阵。 |
| 进程 | `--lane process` | 真实 daemon、Unix socket、跨进程重启和子进程生命周期。 |
| 大输入 | `--lane stress` | 大文件、资源边界；按具体节点单独运行。 |
| 在线平台 | `--lane live` | 需要真实平台或外部服务；选层不提供凭据或授权。 |

## 串行资源入口

从仓库根目录运行；输出目录必须不存在。日志和结果建议放在 `/tmp`：

```bash
python scripts/run_tests.py --lane source --per-file --output /tmp/scid-source
python scripts/run_tests.py --lane source --output /tmp/scid-source-focused tests/operations/test_r3_catalog_authority.py
python scripts/run_tests.py --lane installed --output /tmp/scid-installed
python scripts/run_tests.py --lane process --per-file --output /tmp/scid-process
python scripts/run_tests.py --lane installed --collect-only --output /tmp/scid-installed-collect
```

`--per-file` 逐文件启动新的 pytest 进程，避免全套运行长期保留模块和 catalog；失败或资源止损立即停止，不自动加额或重试。其他层文件全部被排除时允许 pytest 返回 5，但不会将收集错误视为通过。安装层不接受此选项，以保持一次 session 内的 wheel 复用。精确 `文件::测试名` 也可作为目标。

资源设置来自 [scripts/test_resources.json](../scripts/test_resources.json)，可用 `--config PATH` 提供完整配置或显式覆盖部分 `limits`：

- 每进程地址空间硬上限 2,000,000,000 B；整棵进程树 RSS 采样止损 1,500,000,000 B。
- 系统可用内存至少 8 GiB、下降不超过 2 GB；Dirty 不超过 128 MiB。
- 每批 300 秒；数值库线程固定为 1；输出日志预算 8 MiB。
- 同一用户的所有此类测试共享 `/tmp/scid-tests-UID.lock`，拒绝并行；pytest 也拒绝 xdist 多 worker。
- 主日志流式写入并严格截到上限；安装子命令日志落盘，由监督器采样总量止损，可能有一个采样周期的超量，不会全量读入内存。
- 正常退出、超时、信号和监督异常均清理子进程组及已观测的后代。每批临时环境、pip 暂存目录随后删除，保留日志及 `result.json`。

这不是 cgroup 聚合硬隔离：`RLIMIT_AS` 是每进程上限，RSS/系统内存/脏页都是采样保护；瞬间分配和在两次采样间脱离父进程组的未知后代仍有限制。不要据此承诺绝不 OOM。当前 Linux 环境未发现可用的 `memory.max` 控制文件。

CI 使用单独的 [test_resources_ci.json](../scripts/test_resources_ci.json)，只将可用内存门槛显式设为 2 GiB，适配内存小于 8 GiB 的托管 runner；其他上限不变。源码、安装、进程层在每个 job 内顺序执行。不同 Python 版本的 CI job 属于独立主机。

## 标记与安装 fixture

使用 `installed_probe` / `installed_environments` 的测试通过 fixture 依赖闭包自动归入安装层。其他自行构建或安装的测试使用 `@pytest.mark.installed`；真实生命周期使用 `@pytest.mark.process_e2e`；大输入和在线平台分别使用 `stress`、`live_platform`。复合测试选最高成本层：live → stress → installed → process → source。新测试应将收集阶段保持为声明，不在模块顶层启动进程或构建。

`pytest --test-lane installed --collect-only` 可仅收集；真正运行重型层必须经过资源入口。不要将无界 subprocess、网络或安装伪装成普通源码测试。

当前安装证据证明从暂存源码直接构建并安装 wheel。发布入口
`scripts/build_git_release.py` 生成 Git 源码目录及规范化源码 tar.gz，
`deploy/install.sh` 从源码目录安装；该 tar.gz 不是 Python sdist。
当前发布文档没有声明 Python sdist 为交付入口，测试也不覆盖
`sdist → 解包 → wheel → 安装`。不能用现有 wheel 或 Git 源码发布结果声称
这条路径已经通过；若将来支持 sdist 交付，需要单独补充受限验证。

安装 fixture 按需构建并缓存 wheel：

- 从已声明的源码/资源根暂存，排除 build、dist、egg-info 和字节码。
- 解释器使用链接，环境不 bootstrap pip；宿主 pip（22.3+，支持 `--python`）向隔离环境离线安装。
- 运行依赖先按已安装 distribution 的 RECORD 复制到 session 缓存，各环境使用 hardlink；不能 hardlink 时复制。不会向宿主安装目录写入。
- 环境保持 `system_site_packages=False`，既验证核心包路径也验证 Pillow 路径确实属于隔离环境。
- 同时只保留一个安装环境。测试按环境连续组织，避免来回切换重装；多个不同环境的业务矩阵应回到源码层。

历史 R3 精确节点脚本和配置已经被此入口替代。旧计划中的命令是当时的验收记录，不是当前可执行测试清单。运行验证结果由每次 `result.json` 和日志证明，本文不宣称全套已通过。
