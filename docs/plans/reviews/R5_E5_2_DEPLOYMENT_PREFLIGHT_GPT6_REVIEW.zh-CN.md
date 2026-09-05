# R5 E5.2：部署前发行探针 GPT-6 独立审查

日期：2026-09-05

结论：**PASS**。blocker **0** / high **0** / medium **0** / low **2**。未发现阻断当前正式安装入口的 E5.2 问题；两项 low 均为证据措辞补充，不要求修改生产代码或增加部署门槛。

审查对象为 [部署前发行探针](../evidence/R5_E5_2_DEPLOYMENT_PREFLIGHT.zh-CN.md)、唯一开发仓库 `123/scidiscovery-e5.2` 的 `refactor/m7-pre-e5.2` 分支，以及 `/tmp/scid-e52-release.IL4IEC`。实际核对提交为 `3bb23f87ab59b445fbc8a4e5eb5c27c5f4bf22a4`。审查开始时仅该证据文档未跟踪，无已跟踪文件修改；不能以此追认历史工作树状态，但下述逐文件核对独立证明了归档 payload 的提交来源。

## 1. 非阻断发现

### L1：区分构建归档与 dry-run 后的临时目录

位置：证据第 2、3 节；`scripts/build_git_release.py:242`、`:255`、`:320`。

构建器打印的 `tracked source files: 240` 实际包含 239 个 payload 文件和生成的 `MANIFEST.sha256` 自身，不是 240 个来自 Git 的源文件。归档恰有这 240 个普通文件；审查开始前，解开的 `release/` 目录已另有 51 个 `__pycache__/*.pyc`，均不在归档和 MANIFEST 中。原 dry-run 导入源码会产生此类缓存，`sha256sum -c` 仅核对列出的文件，不能单独证明运行后目录没有额外项。

影响仅在证据解释。239 个受控 payload 未改变，正式安装的 `install_packages()` 还会清除暂存源码中的 `__pycache__`，不影响本次入口放行。最小建议措辞：

> 构建归档含 239 个受控 payload 文件及 MANIFEST 自身，共 240 个文件；MANIFEST 校验通过。dry-run 后临时源码目录另有 Python 字节码缓存，未进入归档，不代表生产包或状态发生变化。

### L2：平台 dry-run 尚未覆盖四插件的安装发现

位置：证据第 3 节；`deploy/install.sh:323`、`:410`；`src/scidiscovery/operations/catalog.py:808`。

`preview()` 通过当前基础 Python 的已安装 entry points 编译 catalog。本机 `/home/da/miniconda3/bin/python3` 在同一发行源码路径下发现的 `scidiscovery.plugins` entry points 为 **0**，catalog 的 Operation 数及 runtime plugin 数均为 **0**。因此四插件选择确实经过依赖校验，三个服务模板及基础平台预览也确实执行，但本次 `deployment preview: pass` 不证明四插件已被安装发现，或其完整 Operation 配置已生成。

这不是当前安装入口故障：真实 `install` 分支另行构建所选包并执行 `installed package probe`；本次授权范围明确不含真实安装。最小建议措辞：

> 本次验证覆盖四插件声明依赖、发行源码导入、服务模板及基础平台 dry-run；当前基础 Python 无已安装插件入口，四插件的安装发现与完整 Operation 配置尚未由本探针验证。

## 2. 发行来源与 MANIFEST

以提交内 `scripts/build_git_release.py` 的 `ROOT_FILES`、`SOURCE_TREES`、`DOCUMENTS`、`TOOLS` 和排除规则计算受控集合，并逐项读取该提交的 Git blob。按构建器既有规则规范化文本后，独立核对结果如下：

- 受控集合与 MANIFEST 的 **239** 个唯一 payload 路径完全相等，无缺失或额外源文件。
- 每个规范化 Git blob 的 SHA-256 均与 MANIFEST、发行目录中的对应文件一致。
- `sha256sum -c --quiet MANIFEST.sha256` 退出 **0**。
- `release.tar.gz` 恰有 **240** 个普通文件，其每个文件的内容与发行目录相同；无 `.git`、字节码缓存、软链接、硬链接或越界归档路径。归档所有者与时间已按构建器规范化。
- 没有重新构建、清理或修改现有发行物。L1 所述目录缓存被单独记录，没有被当作受控 payload。

现有发行物指纹：

```text
release.tar.gz
a8208575c6badc0400fb6c1132df762e29c700fa92b7902ac28d0eddc8c1a2b3
MANIFEST.sha256
10915cd5fe533259f92d1f831eabf2caa5b5575f9047ddfd25a71f19666a4582
```

这里的可信来源结论依赖提交内容、MANIFEST 和归档三者的实际比对，不将同目录 MANIFEST 单独视为来源认证。

## 3. 四插件依赖

所选包均在归档中，声明版本满足依赖链：

| 插件 | 发行版本 | 本地依赖核对 |
| --- | --- | --- |
| `curve_score` | `0.2.1` | `scidiscovery>=0.1.0`，发行 core 为 `0.1.0` |
| `curve_figure_evidence` | `0.1.0` | core；`curve_score>=0.2.1` |
| `tcad_artifact` | `0.1.0` | core；`curve_score>=0.2.1` |
| `ingaas_fig4` | `0.2.0` | core；`tcad-artifact>=0.1.0` |

另按各 `pyproject.toml` 的完整 requirements 核对基础 Python：`cryptography=43.0.3`、`Pillow=12.1.1`、`jsonschema=4.26.0`、`pydantic=2.11.5` 均满足约束；Python 为 `3.12`，不触发 `tomli` 的条件依赖。正式 dry-run 还验证了 `setuptools=75.1.0`、pip 可用，以及 `pdftotext`、`pdfimages`、`pdftoppm` 和 `systemd-analyze` 的存在。

负对照同样调用发行目录的 `deploy/reinstall.sh --dry-run`：去掉 `curve_score` 时，以 `plugin curve_figure_evidence requires local plugin curve_score` 拒绝；去掉 `tcad_artifact` 时，以 `plugin ingaas_fig4 requires local plugin tcad_artifact` 拒绝。两次均退出 **1**，均在服务渲染前终止。

## 4. 正式入口、写入边界与宿主告警

独立复核执行发行目录内真实 `deploy/reinstall.sh --dry-run`，未替换脚本或模拟命令。环境设为 `SCID_PLATFORM=codex`、`SCID_WORKER_BACKEND=local` 及完整四插件选择，基础 Python 为 `/home/da/miniconda3/bin/python3`；工作区使用探针目录的 `workspace/`，安装、状态、TCAD 状态、配置和备份根分别指向同目录下的 `install/`、`state/`、`tcad-state/`、`config/`、`backup/`，TCAD command config 为空。复核额外设置 `PYTHONDONTWRITEBYTECODE=1`，避免增加现有缓存。

以 `strace -f` 串行观察子进程执行与文件变更调用，耗时 **6.37 秒**，退出 **0**。观察到的实际路径为：

```text
release/deploy/reinstall.sh --dry-run
  -> env ... release/deploy/install.sh --dry-run
  -> require_sources / validate_source / validate_base_python
  -> render_units / systemd-analyze verify / initialize_platform(dry_run=True)
```

`deploy/reinstall.sh:86` 直接委托正式安装器；`deploy/install.sh:1063` 选择 dry-run 分支。`src/scidiscovery/platforms/common.py:78` 将平台文件写入和删除限制在 `not dry_run` 分支。

系统调用记录中的文件变更仅涉及 `/tmp` 下三个服务模板的创建、重命名、清理，systemd 校验器自身临时目录的创建与清理，以及 `/dev/null`。没有执行 `sudo`、`pip install` 或 `systemctl`，没有生产包、状态库、服务文件或平台配置写入。复核前后探针目录路径集合相同，工作区仍为空，五个隔离目标根均未创建。没有读取生产状态库。

实际复现的宿主告警为：

```text
netplan-ovs-cleanup.service: Failed to open /run/systemd/system/netplan-ovs-cleanup.service: Permission denied
/lib/systemd/system/snapd.service:23: Unknown key name 'RestartMode' in section 'Service', ignoring.
```

校验命令的三个显式输入均是临时目录中的 SciDiscovery 服务文件；上述告警分别指向宿主 `/run/systemd/system` 与 `/lib/systemd/system` 的单元。`systemd-analyze verify` 及安装器均成功返回，未报告本次三个模板错误。因此原证据将告警界定为宿主单元问题、不当作服务已启动的证明，判断正确；本审查不要求修改宿主单元。

## 5. 检查范围与未验证项

使用跨边界审查和变更范围检查技能，将检查收敛到现有发行构建器、插件依赖、正式 wrapper、安装器预览与平台写入分支；全部串行，无新增测试或生产改动。逐文件来源检查、归档检查、requirements 检查、正式 dry-run、两个预期拒绝对照及 `git diff --check` 均符合预期。初次“目录仅含 payload”检查识别出 L1 的 51 个既有缓存；随后通过归档独立核对确定其不属于发行内容，没有隐去该差异。

未运行全量测试、安装包构建、实际部署、服务启动、状态迁移、事务回退或科学 E2E，因为本次仅审查既有部署前探针，实际入口复核与来源检查已覆盖当前审查目标。原证据的 **48,140 KiB** 为原探针记录，本审查未将它外推为 Codex 进程树或 WSL 系统级内存结论。

本 PASS 仅放行当前发行构建与正式安装器预检证据，不声称安装完成、四插件安装发现完成、服务可运行或科学闭环通过；无需为此引入新的后端、迁移器、UI、哈希体系、监控或治理实体。
