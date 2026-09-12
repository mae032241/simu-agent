# 安装与继续 Fig.4

以下参数已通过原部署脚本 --dry-run；请以 da 用户执行，脚本按原机制调用 sudo。
本会话不能写 /opt、/etc 或重启系统服务，因此尚未实际安装。
本轮不用同步 VM runner。安装后重启 Codex 会话，按 UI 绑定原 M7-test0 后继续；不新建研究实例。

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

继续时先核对五个生产模块的安装摘要、Root 的 max_attempts 参数与最新编译角色。
见 IMPLEMENTATION.zh-CN.md 的具体 Fig.4 接手要求；原科学闭环尚未完成。
