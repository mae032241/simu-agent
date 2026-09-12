# 输入、准入与实现一致性：R2 实施记录

2026-09-10。工程实现及本地验收完成，最终独立审查 PASS。正式服务尚未安装本候选，原记录的线上打包、执行审批及求解器运行仍待完成。

## 计划与独立审查

R1 独立审查 REVISE，删除全 Schema 生产者启动硬门禁、资源兼容混同、最大容量推断及无必要业务接口重构。R2 独立复审 PASS 后冻结为 PLAN_R2_APPROVED.zh-CN.md，按 P0—P4 实施本地可执行部分。

实现初审要求修复通配背景端口可承载精确审查证明的诊断误报；补齐后独立生产审查 PASS。最终审查核对生产增量、测试代码和日志，确认 R2 本地验收 PASS，无剩余源码阻断。独立角色为 consistency_plan_review，无父对话继承、只读、未跑测试。独立测试执行者 consistency_integration_tests 只修改授权测试文件，测试统一串行安排。

## 改动及范围

相对本轮前工作树，而非整个 HEAD 差异：

- operation_transforms.py：打包仅增加可选 experiment_review 输入，保留对导入计划的兼容；生成计划仍须提供精确通过审查。
- mcp_root_operation_routes.py：将背景、直接修订、对应 reviewer 入口的结构分支委托给共用纯函数，精确身份、历史合同、verdict、未消费 signal 拒绝逻辑不变。
- 新增 operations/review_admission.py：上述共享分类，以及非阻断目录诊断。候选接收能力不代表实际资格，不扩大编译拒绝范围，不新增 MCP 或状态机。
- 原包装器已隔离业务输入，未修改 transform_adapter Mapping 接口。新增证明由控制验证并保留父记录，仍只向打包业务传递四项输入。
- 测试增量：test_l4_local_tcad.py、新增 test_review_admission.py 与 test_review_admission_integration.py。

完整本轮增量见 implementation-increment.patch。前序未提交修改全部保留；未提交 git commit，未运行全量测试。

## 实际证据与同类清点

live-failure.json 保存旧部署中精确打包预检的 input_independent_review_missing。catalog-before/after.json 表明仅 tcad.reviewed-deck-package.v2 摘要改变。existing-artifact-compatibility.json 核对原 plan_3、experiment_review_6、author_4、deck_review_5 四项生产者摘要均与候选匹配；这不是线上完整调用成功证明。

review-receivers.json 保留正式目录诊断。打包的 materialize/revise 两个潜在来源缺口已消除；其余 12 个组合是四类：通用 intake 审查消费 TCAD 来源（1）、control-equivalence 消费计划（2）、deck compare 两输入消费三类作者输出（6）、TCAD 参数审查消费通用 intake 来源（3）。它们是候选来源组合，不等于十二次实际生产故障。本轮未批量修复，也未将其变成启动阻断。

## 验证与资源

- 目录诊断：3 passed，含缺口反例、背景/修订/审查分类和通配证明接收。
- 真实 producer/reviewer Root 链：3 passed，保留导入计划路径，生产计划通过 invoke/受控提交生成，覆盖缺失审查、错计划、非通过、错误 reviewer、删除端口、四项业务投影和包父记录；共享审查的完整/部分/跨 Run 身份验证。
- 历史、直接修订、blocked 审查、审批等代表回归：41 passed in 7.29s。
- 核心/TCAD wheel 安装态同组核心测试：6 passed in 3.26s，断言两个包来自临时安装目录。
- 进一步全新安装核心及三个领域插件，通过未经 monkeypatch 的真实 compile_installed_catalog 入口发现，所有候选 Operation 摘要匹配。第三方 Python 依赖仍复用宿主，不称全新依赖环境。
- git diff --check 通过。

测试串行、BLAS/OMP/MKL 单线程、地址空间上限 3 GiB、每批超时 120 秒。最高测试 RSS 107232 KiB（约 105 MiB）。没有运行真实求解器。

失败日志全部保留：首次诊断测试误用 dataclasses.replace，改为现有 Pydantic model_copy；集成夹具修复端口、语义合同/规则资源、有效计划差异和 Agent instruction 后通过。没有为夹具失败放宽任何生产校验。各批测试重叠，不把执行次数累计为独立测试数。

## 安装命令与待验证项

已按当前 systemd 服务核对 workspace、Python、安装/state/config 根及三插件选择。以下命令从任何目录运行，使用当前用户 da，并由 wrapper 调用 sudo：

```bash
SCID_WORKSPACE=/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/workspace/ingaas_inalas_photodetector \
SCID_CODEX_LAUNCH_ROOT=/home/da/project/ai4s/tcad/git_release/scidiscovery-agent \
SCID_PYTHON=/home/da/miniconda3/bin/python \
SCID_INSTALL_ROOT=/opt/scidiscovery-m7 \
SCID_STATE_ROOT=/var/lib/scidiscovery-m7 \
SCID_CONFIG_ROOT=/etc/scidiscovery-m7 \
SCID_BACKUP_ROOT=/var/backups/scidiscovery-m7 \
SCID_PLUGINS=tcad_artifact,curve_score,curve_figure_evidence \
SCID_TCAD_COMMAND_CONFIG=/etc/scidiscovery/command-adapter.json \
/home/da/project/ai4s/tcad/git_release/scidiscovery-agent/123/scidiscovery-e5.2/deploy/reinstall.sh reinstall
```

安装脚本的 --dry-run 存在一个独立环境问题：preview 从源码导入、从当前 Python 查 entry-point 元数据，导致 tcad_artifact/curve_score 缺依赖（日志保存）。源码、基础依赖及 figure 依赖检查已过；此预演不能记录为通过。正式 install_packages 会先将全部所选插件安装到同一新目录，与 preview 不同；对应临时 wheel 实际发现验证已通过。未为此扩改部署代码。

本会话不能写入正式 /opt、/etc、/var/lib 路径，且无法提权，因此未执行正式安装。用户完成安装重启后：核对实例与目录，使用新打包名称显式绑定原 experiment_review_6，preflight 通过才 invoke；创建执行审批 URL，UI 批准后开始六案例执行。不得把聊天确认当作执行审批。
