# 本轮安装

2026-09-12 用户已完成线上安装和重启，七个生产文件核对一致，原 M7-test0 已绑定；有界诊断已完成，结果和验收边界见 [LIVE_DIAGNOSIS.zh-CN.md](LIVE_DIAGNOSIS.zh-CN.md)。以下保留已使用的部署命令，当前无需再次安装。沿用已核验的部署目录与 command adapter 参数。
本轮没有 VM runner 改动，无需同步 runner。以 da 用户复制执行以下命令，部署脚本按既有机制提权：

```bash
env \
  SCID_WORKSPACE=/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/workspace/ingaas_inalas_photodetector \
  SCID_CODEX_LAUNCH_ROOT=/home/da/project/ai4s/tcad/git_release/scidiscovery-agent \
  SCID_PYTHON=/home/da/miniconda3/bin/python \
  SCID_PLUGINS=curve_score,tcad_artifact,curve_figure_evidence \
  SCID_TCAD_COMMAND_CONFIG=/etc/scidiscovery/command-adapter.json \
  SCID_INSTALL_ROOT=/opt/scidiscovery-m7 \
  SCID_STATE_ROOT=/var/lib/scidiscovery-m7 \
  SCID_CONFIG_ROOT=/etc/scidiscovery-m7 \
  SCID_BACKUP_ROOT=/var/backups/scidiscovery-m7 \
  /home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2/deploy/reinstall.sh
```

安装后重启 Codex 会话，通过管理页继续绑定原 M7-test0。先核对 changed-files.json 的七个生产文件、编译角色和新工具返回，再选择有科学意义的有界续接。
新 Agent 应先读 analysis-start.json，按需追查原目标/方法/结果和选定工具的完整合同，直接使用新 scratch 的可编辑副本。
旧 Run 与原恢复目录不套新合同、不改写；原 Fig.4 已完成 60/60 单元及有限形貌结论，不为验证入口而重算。

上线后另行记录真实 Agent 首项有效动作、重复读取/截断、权限返工、无效重算、提交拒绝和定位信息。
隔离工程验证已经证明机械流程；本次现场诊断证明新 Agent 能续接并封存有限结论，但未测得可比较的阅读量或总耗时改善，也未实际触发失败草稿恢复和曲线案例映射工具路径。
