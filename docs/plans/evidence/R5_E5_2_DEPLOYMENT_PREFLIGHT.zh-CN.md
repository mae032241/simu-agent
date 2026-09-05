# R5 E5.2：部署前发行探针

日期：2026-09-05

状态：发行构建与安装器 dry-run 通过；[GPT-6 独立审查](../reviews/R5_E5_2_DEPLOYMENT_PREFLIGHT_GPT6_REVIEW.zh-CN.md) PASS，阻断项 0，两项非阻断证据措辞已在本文闭合。本文不表示已经安装、重启服务或完成真实科学闭环。

## 1. 输入边界

- 唯一开发仓库：`123/scidiscovery-e5.2`；分支 `refactor/m7-pre-e5.2`。
- 被验证提交：`3bb23f8`，工作树在构建前无未提交修改。
- 发行构建器：既有 `scripts/build_git_release.py`。
- Worker 后端：`local`。
- 插件选择：`curve_score,curve_figure_evidence,tcad_artifact,ingaas_fig4`。
- 工作区、安装根、状态根、TCAD 状态根、配置根与备份根均使用本次 `/tmp` 隔离探针目录；没有读取或修改生产状态库。

临时目录 `/tmp/scid-e52-release.IL4IEC` 只保存可删除的发行探针，不是第二个开发仓库，也不作为冻结科学数据位置。

## 2. 结果

```text
tracked source files: 240
git initialized: no
source imports: pass
base Python dependency check: pass
Rendered services:
  scidiscovery-approval-ui.service
  scidiscovery-control.service
  tcad-control.service
deployment preview: pass
No package, state, service, or platform configuration was changed.
最大常驻内存：48,140 KiB
```

构建归档含 239 个受控 payload 文件及 `MANIFEST.sha256` 自身，共 240 个普通文件；MANIFEST 校验通过。归档不含 `.git`、链接或字节码缓存：

```text
release.tar.gz
a8208575c6badc0400fb6c1132df762e29c700fa92b7902ac28d0eddc8c1a2b3
MANIFEST.sha256
10915cd5fe533259f92d1f831eabf2caa5b5575f9047ddfd25a71f19666a4582
```

dry-run 从解开的发行源码导入模块，因此运行后的临时目录另有未列入 MANIFEST 的 `__pycache__` 字节码缓存；它们不在构建归档中，也不表示生产包或状态发生变化。

`systemd-analyze verify` 同时打印了宿主 `netplan-ovs-cleanup.service` 权限告警和宿主 `snapd.service` 不认识 `RestartMode` 的告警；本次生成的三个服务模板仍通过，安装器以 0 退出。这两条宿主单元告警不作为 SciDiscovery 服务已实际启动的证据。

## 3. 放行边界

本探针只证明当前提交可以经既有发行构建器生成干净归档，并完成四插件声明依赖检查、发行源码导入、服务模板渲染和基础平台 dry-run。当前基础 Python 没有已安装的 `scidiscovery.plugins` entry point，预览目录为空，因此本探针不证明四插件已经被安装发现或其完整 Operation 配置已经生成；这些由真实安装分支的包构建与 installed-package probe 验证。它没有执行：

- `sudo` 安装或生产路径写入；
- 旧服务停止、新服务启动或开机自启切换；
- 生产状态迁移或安装事务回退；
- Codex 重启、ResearchInstance 重新绑定；
- 真实 Fig.4 Agent、人工审批、TCAD 外部执行或科学资格判断；
- Codex 整棵进程树和 WSL 相对基线的系统级内存测量。

独立审查只需判断发行物是否确实来自 `3bb23f8`、四插件选择和 dry-run 是否走正式入口、是否存在会阻断安装的 E5.2 新问题。不得借此引入强化后端、迁移器、UI、哈希体系、监控产品或新的治理实体。
