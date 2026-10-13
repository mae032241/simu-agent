# U0r：可注册的科学执行接口

状态：修后源码、安装与实际 namespace 接线验收通过，最终独立审查通过。只授权开发及无模型测试。

## 职责

CLI直接发现被选中的`scidiscovery.execution_interfaces`注册项，复用RuntimePluginFactory与RuntimePluginContribution合同，不启动MCP、不编译全量操作目录，不增加旧daemon的必填插件配置。公共ExecutionAdapter合同从旧Bridge抽出并重导出；薄链所需扩展以ManagedExecutionInterface明确声明，第三方无需猜测运行时方法。

控制层拥有调用身份和唯一的接受/执行原件；具体实现负责本地命令或外部作业执行、状态映射及可选的领域指标。控制调用ID与外部作业ID不得混淆。已有cov回执复用，不引入第二份SQLite或预算账本。元数据预览不代表最终资产资格。

本轮实现cov及普通本地命令，第三方注册与不同外部ID的契约用无模型夹具验证。TCAD仅复用合同，不宣称真实远端接入通过。无模型平台启动、科学搜索、U1软边界、U2分片或U3路由资格。

## 验收过程

第一冻结版本源码门禁：82通过、8失败，43.85秒；日志`.trial/u0r-source-01-20261013/batch-001/pytest.log`。失败集中在通用化后process/accepted畸形或半写状态退化、cov未知completion原件集合与旧校验不一致。

独立审查另外指出：公共准入误以传输成功覆盖领域未知；本地执行原始可变文件却封存快照；控制ID和外部作业ID混淆。以上均作为阻断修复，不能以基线失败放行。最终结果待追加。

## 固定验收范围

- 两种真实CLI实现共用成功、失败、运行中查询、重复查询、收集与原件校验；缺指标保持未知，不要求cov台账。
- 同原件查询/恢复不重提；不确定执行阻止继续新接受；冻结输入与实际执行一致。
- 外部ID不等于控制调用ID时仍通过同一核心入口。
- 新插件发现不加载MCP/全目录或给旧daemon增加必填配置；安装后使用真实发布入口，不以源码fixture冒充安装资格。
- host在节点未封存时可以读取普通本地执行进度；实际cov启动入口接注册分派。namespace与其他未验证项单独列明。

## 修后证据

生产11文件冻结见 `/tmp/scid-u0r-production-02.json`；测试最后补充源码注册fixture，16文件冻结见 `/tmp/scid-u0r-source-03.json`。外层 `.trial/` 为本次操作者原始证据目录。

- 源码：95通过、1不适用跳过，47.00秒，`.trial/u0r-source-02-20261013/batch-001/pytest.log`。跳过为仅适用于local的快照执行测试在cov参数上的分支，不是安装资格跳过。
- fresh wheel：实际安装入口和模块绑定通过；94通过、1同项不适用跳过，40.40秒，`.trial/macro-role-installed-20261012/artifacts-u0r-20261013/u0r-installed.log`。8个模块来自site-packages且哈希与生产冻结一致；实际新entrypoint发现，不使用源码伪造metadata。
- 同wheel：已有封存到交付链8项通过，3.84秒，`u0r-delivery-check.log`。
- 实际`prepare_home`/`outer`/bwrap → `exp`包装器 → 注册CLI → 合成cov后端，再查询，均退出0，计数1，`u0r-namespace-02-result.json`/`u0r-namespace-02.log`。没有启动native模型。第一次父探针错误地让合成后端默认输出`/opt/exp/runs`而非实际入口`EXP_RUN_DIR`，被资格校验拒绝；只修探针默认路径后通过，生产未改。
- wheel SHA256：`687342ce4b07c7d11dcc3696053d122c6e3badc0926fcd8311a25cf3817da32f`。

## 使用与限制

发布CLI为`scid-experiment --config <控制层冻结配置> run --script <输入>`，中性文件输入可用`--payload`；查询、收集、lookup均使用返回的原调用ID。实现注册key为`local_execution:command`、`cov_execution:experiment`，通过`scidiscovery.execution_interfaces`入口加载。第三方声明ExecutionInterfaceRegistration与RuntimePluginFactory，其contribution暴露ManagedExecutionInterface；扩展方法在纯合同中逐项列出，缺能力显式不可用，不自动退回shell。

每次显式`run`表示新意图，原ID内查询/恢复不重提；未解决unknown阻止后续新接受。lookup丢绑定测试采用删除submission回执模拟，只证明原身份补绑定，不代表真实远端网络故障资格。非本地different-ID插件为真实CLI合同夹具，不是已部署TCAD执行器。

local运行控制归档的单输入字节，因此`__file__`指向归档位置，cwd可显式配置；imports、环境及其他文件依赖未冻结，不宣称完整实验环境可复现。cov维持领域要求的路径/原件检查。进程成功不证明候选合格，指标缺失不推断科学停滞。U1软边界、U2分片、U3路由、真实远端取消与原生同session恢复未由本节点验收。

独立源码交付回归8项通过，3.33秒，`.trial/u0r-delivery-source-20261013/batch-001/pytest.log`；新测试fixture导入不改变已安装生产字节。
