# 本轮部署

本轮修改六个既有生产文件，无 VM runner 修改。源码与隔离安装验证完成后，使用下列命令更新服务，再重启 Codex 并通过管理页继续绑定 M7-test0。旧 Run 和原始收据保持不变。

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

本轮线上真实恢复曾在打开时失败，已保存 live-recovery-open-failed.json；修正后需使用新 Run 验证，不重开该失败 Run。此前只读核对和隔离 wheel 安装不等于已修改 /opt 下的线上安装。
