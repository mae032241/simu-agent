# 历史测试生成物清理（2026-10-12）

用户授权：删除当前路径内无用历史测试文件，然后持续推进 T2–T5。清理前独立核查，父代理持共享测试串行锁执行；未删除 Git 跟踪文件、科学原始结果或唯一审查证据。

## 已删除

- 39个未跟踪的 `__pycache__`、`.pytest_cache` 和顶层 `build` 目录：23,879,503逻辑字节。
- 150个历史测试副本：20,949,876逻辑字节；逐一核对 SHA 和固定 Git blob 完全一致，恢复位置及 blob 已记录。固定提交 `5a4713e318e9a973f2891f5033711b627ad2a622`。
- 9个已结束安装测试的虚拟环境：估算分配空间212,488,192字节（202.64MiB）。保留 wheel、日志、module-bindings、脚本及 pyvenv 配置，可重新安装后复核，不能再称原环境仍在。

9个环境位于外层 `.trial/` 的 `n6a-installed-20261012`、`n6b-installed-20261012`、`n6b-installed-final-20261012`、`n6c-installed-20261012`、`n6c-installed-02-20261012`、`n6c-installed-final-20261012` 的 `venv`，以及 `t1-installed-20261012/{artifacts,artifacts-02,artifacts-03}/venv`。最新 `artifacts-04` 保留。

## 保留范围

e11任务依赖、原公开任务环境、N5/live02原实例、真实场引用的运行环境、独有原生轨迹/独立审查/撤回收益记录均保留。约15GB的试跑区不整体删除。三个大 `temporary-instance-copy` 含差异证据，尚未逐字去重，故没有按名称删除。Git的其他工作树、用户实例、密钥配置和socket不在本次清理范围。

独立盘点者 `/root/n0_baseline`；缓存及重复字节复核者 `/root/n1_runtime`。进程检查只是当时可见范围内的快照；同时使用共享测试锁，保留实际场启动依赖。本次是文件清理，不执行产品测试或科研模型，也不改写历史验收结论。

## 明细

原件位于仓库外层 `.trial/cleanup-20261012/`。重复文件清单含每个原路径、Git恢复提交/路径/blob/SHA；环境清单含原pyvenv配置及保留wheel的SHA。

| 文件 | SHA256 |
| --- | --- |
| `repo-cleanup-result.json` | `752606a91544624fe2bd4ecb2e7c50b1f9dc3ec707fb83fe2c42008df393abd8` |
| `venv-cleanup-result.json` | `c1a3e36db20ea3144714833767c6c0936e8e795731b81b3a2a548ca71b80b79c` |
| `scid-history-cleanup-20261012.json` | `a108ee688c62c4098e1aa5810991a4455917a1f8fdd85a48e534e8b18d488259` |
| `scid-generated-cleanup-review-20261012.json` | `cd6f4c25d7248ca08a7fd87573e12bb6e3a343380d4b699ad97cba4f39b4e0ce` |
| `venv-deletion-frozen.json` | `c52fea57404b56a83a13e8723b5c86d2dad7d88a89ad045bb9ce31f531e29626` |
