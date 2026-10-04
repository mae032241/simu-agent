# Covshift 本机环境准备记录

状态（2026-10-04）：**独立 Python 环境与一次真实公开 exp CLI 工程 smoke 独立审查通过（环境与公开 CLI 工程 smoke）；launch_ready=false。** 当前首 pilot 选 covshift；原 N-body 24 粒子工程 smoke 和所有旧 candidate 保留。选题／科学资格由[主计划](plans/SCIENTIFIC_PROGRESS_AND_CORRECTION_PLAN.zh-CN.md#真实效果题与机制回归分工)拥有；本文只交接本机环境，不是模型驱动或正式 trial。

当前接手状态／原预算及零模型补验入口见 [2026-10-04 工作交接](plans/DEV_HANDOFF_20261004.zh-CN.md)；该交接／002诊断已独立审查通过，002尚未宿主执行；交接是审计记录，不替代本文运行规则。

## 已准备

- Task 固定 LHTB `d78f5eb52ad754c5ee9154741af73130a85a65b8` 的 `tabular-data-feature-covshift`，原题／checkout 不修改。公开包 `/tmp/scid-covshift-local-20261004-prepared-001/public` 仅 8 文件：task.toml、instruction.md、environment/Dockerfile，以及 harness 的 exp_cli.py、runner.py、train.csv、val.csv、净化 meta.json。trusted 准备代码复刻 Dockerfile：删除 meta 的 a_perturbation／estimated_A_score／noise_sigma；只记录原件与净化结果 hash，不输出敏感值、不导出／运行 generator，不读 hidden tests／verifier／reference。
- 独立 env `/tmp/scid-covshift-local-20261004-env`；11 个精确 CPython 3.12／Linux x86_64 binary wheels 总 75169712 B，低于本轮 150 MB 下载上限。公开 PyPI 元数据、wheel size／SHA 均核对后离线 no-index／no-deps 安装，原 miniconda／已有 env 不改。可重建版本与 wheel SHA 的权威输入为 [requirements.lock](../scripts/acceptance/fixtures/covshift_local/requirements.lock)，不是只保存在 /tmp 的配置。
- [任务专用薄入口](../scripts/prepare_covshift_local.py) 复用已有 N-body namespace／regular-file helpers 和 run_tests 默认监督。只读挂 public、必要 base runtime 与新 venv 的 interpreter／pyvenv.cfg／lib；保留 venv/bin/python 身份，sys.executable／sys.prefix 和所有 11 版本在真实 task namespace 中核过。任务执行前关闭其继承的监督锁 FD，父监督仍持锁；清环境、独立禁网、host-private canary 与 native 子进程边界通过。实际 Root／Worker／helper 的模型 API／task 隔离尚未接线，不扩大该工程子进程证据。
- 原 train.csv／val.csv 未裁小，合法 zero/DummyRegressor 工程基线只做一次 `exp run --script` → results → `submit --run-id 1` → status；60 s run／45 s audit／0.10 阈值不改。run 与公开 audit 都实际完成，validation／audit score 均 0、leakage_flag=false；这是管线验收，不是有效科学改进／隐藏分数，也不满足原至少 25 次不同实验与最后 8 次停滞条件。25 internal exp 不等于 25 Root task 或轮换／记忆覆盖。
- regular `submitted.json` 304 B 与 `submitted_model.pkl` 3877 B 已交接到 submission；trusted host 只做 bounded regular／hash／复制，不反序列化。32 MiB 是本工程 smoke 的读取上限，不是原题正式模型提交限制；没有继承 N-body 的 2 MB 上限。7 个聚焦净化／篡改／白名单／symlink／handoff 检查通过。

## 重建入口与监督

从本仓库根目录使用 Python 3.12／Linux x86_64。下面是调用**既有** serial_lock／run_one 的最小环境重建方式，新目录须尚不存在；所有命令不主动限制虚拟地址空间，保留 RSS 止损1500000000 B／300 s／8 MiB log，数值线程为 1。联网步骤仅 binary PyPI wheels，随后离线安装；本轮不是系统安装或新资源授权。

```python
import json, os, sys
from pathlib import Path
from scripts import run_tests as guard
root = Path('/tmp/scid-covshift-rebuild-new'); root.mkdir()
cov_env, wheels = root / 'env', root / 'wheels'
lockfile = Path('scripts/acceptance/fixtures/covshift_local/requirements.lock').resolve()
commands = [
    [sys.executable, '-m', 'venv', '--without-pip', str(cov_env)],
    [sys.executable, '-m', 'pip', 'download', '--index-url', 'https://pypi.org/simple',
     '--only-binary=:all:', '--no-deps', '--require-hashes', '--no-cache-dir',
     '--retries', '1', '--timeout', '20', '--dest', str(wheels), '-r', str(lockfile)],
    [sys.executable, '-m', 'pip', '--python', str(cov_env / 'bin/python'), 'install',
     '--no-index', '--find-links', str(wheels), '--no-deps', '--require-hashes',
     '--no-compile', '-r', str(lockfile)],
]
env = {k:v for k,v in os.environ.items() if not k.startswith('PIP_')}
env.pop('PYTHONPATH', None); env['PIP_CONFIG_FILE'] = '/dev/null'
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
            'NUMEXPR_NUM_THREADS', 'TOKIO_WORKER_THREADS', 'RAYON_NUM_THREADS'):
    env[key] = '1'
limits = json.loads(guard.DEFAULT_CONFIG.read_text())['limits']
with guard.serial_lock() as lease:
    for i, command in enumerate(commands):
        output = root / str(i); output.mkdir()
        result = guard.run_one(command, env, limits, output, lease.fileno())
        (output / 'resource.json').write_text(json.dumps(result))
        if result['returncode'] or result['stop_reason'] != 'exited':
            raise RuntimeError('environment preparation stopped; inspect exact logs')
```

Public 准备沿同一 guard 包装运行 `python scripts/prepare_covshift_local.py prepare --output <新目录> --task-root <固定题目录>`；它不执行任务代码。然后 `python scripts/prepare_covshift_local.py smoke --prepared <该目录> --python <新env>/bin/python` 自带监督锁，**不要外套第二锁**。只接受 exact task revision／净化白名单；未来另建目录，不盲重放不确定输出。本轮精确 commands/resources、11 wheel 选择记录、prepared/hash、CLI outputs、artifact handoff 都保留在 `/tmp/scid-covshift-local-20261004-evidence`、`/tmp/scid-covshift-local-20261004-prepared-001`，不是重建的唯一入口。

## 下一环节仍未激活

### Named permission profile 接线（独立审查通过，限定源码边界）

最新普通宿主读回已通过：`/tmp/scid-covshift-role-normalization-20261004-host-preflight-001/result.json`，真实 fresh Root start、paused Goal set/get/clear、同线程新连接 resume、standalone 父子合成读／禁网 canary 全真（1.749 s／RSS552837120 B）；0 turn、active Goal、科研实例。该安装 source 为 `af1e4f9`。这证明 RootPermissions 与 standalone 命令路径，不证明 Worker／helper native spawn 继承、完整 Factory/catalog 资格或模型 API／账户可用性。以下保留先前各源码节点当时的验证边界，当前宿主协议状态以上述最新读回为准。

增量修正（独立审查通过，限定 config 握手）：正常宿主 profile 预检在 `config/read` 精确比较处拒绝，尚未创建 thread；实际 0.159.2 回复将未声明的 description／extends／workspace_roots、filesystem.glob_scan_max_depth 和 network 的可选项序列化为 `null`。当前只将已实测的这些空缺省项视作未声明，冻结定义／digest 不变；未知字段（包括 null）、非空 extends／roots／网络变化仍拒绝。28 个源码 owning 检查通过，并在默认监督下仅 initialize／config/read 使用当前 production verifier 实测通过（显式 source protocol，不冒充 installed）。另一次诊断证明 thread/start 加载 AGENTS 也会调用 fs sandbox helper，被当前外层 socket mask 阻断，故实际 active／legacy 投影、resume／paused Goal 仍需普通宿主核验，不继续本地重试。预检现保存失败 RPC 阶段及仅该合成 profile 的权限诊断，排除 auth／provider／代理正文；静态 Python 不再白名单放行无须加载的 `.a` 库。旧 30871c7 candidate 保留且不含此增量，审查／提交／新安装后再使用宿主入口。

[RootPermissions](../src/scidiscovery/platforms/codex_root_host.py) 可由宿主注入一个自包含的 named profile 与冻结定义，fresh `thread/start`、exact `thread/resume` 和 `turn/start` 使用正式 `permissions` 参数，不同时发送旧 sandbox 覆盖项；`config/read` 的确切定义、返回 active profile 和旧权限投影不一致即拒绝。[Factory](../src/scidiscovery/platforms/codex_progression.py) 注入必须匹配 goal 已冻结的 approval／sandbox／network，仍执行 catalog 能力检查，不新增 AgentSettings／配置 ABI，也不改 Worker／helper 原身份或权限。16 个源码模拟协议／准备边界检查与 1 个原有 Factory 轮换邻接通过；这不是实际平台角色继承证据。

正常宿主独立 `command/exec` 的合成 public／private／同 CODEX_HOME auth-history／禁网／native child canary 已通过（`/tmp/scid-covshift-live-20261004-host-repro-002/result.json`）；其范围不是 Root／Worker／helper。可复用的下一预检为 [probe_covshift_permissions.py](../scripts/probe_covshift_permissions.py)：经现有默认 serial_lock／run_one，fresh 无认证 CODEX_HOME，只挂合成 public 与精确 arg0／native binary／Python runtime；真实 Root 启动、paused Goal set/get/clear、重连 resume 后再次检查原生命令，任何失败返回非 0，不发 turn、不设 active Goal、不绑定实例。调用形式为 `<已审新candidate的python> scripts/probe_covshift_permissions.py --installed-candidate <新candidate目录> --output /tmp/scid-covshift-<新目录> --codex-native <确切native二进制> --native-sha256 <冻结SHA256>`；入口拒绝 prefix／两模块 origin 不属于该安装的情况，记录 candidate source commit、metadata／模块 SHA。当前旧 b150983 installed candidate **不含本轮两模块改动**，须独立审查、提交及新候选字节读回后才能使用，当前不是可执行 installed 资格。源码测试模拟 turn 参数；真实 turn／Worker／helper 未调用，profile runtime 与 paused Goal 预检尚未运行。

### 启动时统一任务禁网 debug 策略（独立审查通过，限定源码拥有路径）

全局 AgentSettings 可显式设置 `{"debug_disable_task_network":true}`，默认 false；安装生成、daemon 和 Factory 使用同一 `SCID_AGENT_SETTINGS_FILE`。先停止所有相关 host／Worker／helper，再重跑现有 `scid init codex` 并重启；on→off 也须同样重新生成，现有 ownership 规则只替换 managed block／role 文件、保留用户 unmanaged 配置，冲突明确拒绝，仅重启不能取得匹配安装资格。不是热开关，不撤销既有 native 子进程或已提交外部请求。实例不可覆写该部署字段。新 loop effective／Run recovery policy 冻结该值，旧记录缺字段视 false；不同策略的旧 loop／Run 不可启动、attach、恢复或继续 helper 工具访问，原件读取／停止结算保留。pilot 使用 fresh host／实例，不重置旧数据。

开启时，安装 Root 根配置的 native network_access=false／web_search=disabled，Worker／helper 共用生成角色 web_search=disabled；Factory 对实际 config/read 核 disabled，并保留 named filesystem profile 的精确定义／digest、start/resume/turn 校验。仅与 named network=false 重复的精确 legacy false 单项不作为 thread override；安装文件、启动配置及 config/read 校验仍保留。danger-full-access 或其它不能兑现该限制的组合拒绝，既有文件权限不扩大；已有 TOML 根／table 冲突会要求明确修正后重新初始化。Root／owner／helper 指令公开有效限制；声明允许网络的 Operation 仍可处理 sealed/local 输入，不改 catalog/digest，不将其整体禁用。声明 network_access 的宿主工具与 reserve_network_request 给 typed `task_network_disabled`，当前部署 deny 也保护旧 Run 回调，拒绝发生在 HTTP／配额记录前。模型 API 的 host 通道及模型配置不改。

本轮 source 检查与一次真实 initialize/config/read 证明 named profile 与 legacy network=false 可共存、有效 web_search=disabled；未在当前外层环境创建 thread 或执行 native。`launch_ready=false`：旧 installed candidate 不含该新 flag；真实 Worker／helper 的 native 子代理继承仍未验证。此应用策略只强制框架拥有的启动／声明网络工具路径，不能禁止用户自行 CLI 覆写、任意外部 MCP／第三方 plugin 自开 socket；正式 pilot 必须只加载已审 surface 并另钉部署读／出网边界。文件隔离、全角色计量与停止、账户模型可用性、双驱动及 trusted host-only 评分交接继续待完成，不声称 Agent 已不能看到答案。

用户已确认 **Native Goal 与 SciDiscovery 各一次、每模式全角色共用 1800 s wall deadline 和 200000 tokens，任一先到即停止** 的 custom 链路 smoke；不是每个角色各获额度，也不是原题 4 h 同条件成绩。额度覆盖 Root／Worker／helper／全部 native child；用量未知须保守停。实际计量／停止、两模式 driver、有效 profile／反馈、任务与模型 API 的网络边界、全角色真实读隔离与 trusted host-only 隐藏评分仍待接线验证；200k 不换算成固定金额保证，不沿用 P6s 4M。原全角色6.1-sol/high提案未激活，alias仍未 runtime核实，progression mode未选；不把开发6.1/xhigh当场次条件。本轮未启动 model／Goal／app-server／科研实例／评分，不授权新科研费用；launch_ready=false。


### 双模式公开输入交接（独立审查通过，限定输入与 MCP 路径边界）

[prepare_covshift_pilot.py](../scripts/prepare_covshift_pilot.py) 消费上述净化工程包与 exact installed candidate identity，通过既有默认 serial_lock／run_one 生成两臂独立输入。当前增量输入 `/tmp/scid-covshift-driver-20261004-v2-inputs-001/launch.json` 绑定 candidate `e77c61f`（旧 paired-001 保留）；每臂科学输入只含原 instruction 与 exp_cli.py／runner.py／train.csv／val.csv／净化 meta.json，并附原镜像语义的 `exp` wrapper。不复制 task.toml／Dockerfile／开发源码或计划，workspace／runs／submission 全空，不带旧训练文件／模型／实验日志。launch 与 settings proposal 留在 host，不能作为模型正文或 project 输入；两臂均冻结候选6.1-sol/high，默认 helper 与 lightweight 候选一致，Scid progression 尚未激活。

实际驱动必须消费 launch 中的精确只读／可写绑定：harness→`/opt/exp`（read）、每臂私有只读 `project/bin/exp` 通过该臂 PATH 使用，workspace→`/workspace`、runs→`/opt/exp/runs`、submission→`/submission`（write）。两臂使用相同 PATH／EXP_*，保留原60 s run、45 s audit、0.10阈值；原题绝对路径不靠修改题面迁就本机。当前只生成绑定输入，`bindings_enforced=false`、`launch_ready=false`；chmod 与路径移动不是 OS 隔离证明。

5 项 source 检查核两臂完整公开集合／空输出、篡改与错误 candidate 拒绝，以及真实三工具 MCP→artifact_ingest_file：公开原件可封存，绝对／..／直接和父目录 symlink 越界均拒绝且无新 Artifact 绑定。该范围不能推出任意 plugin／外部 MCP 已隔离。后续真实 Goal／Sci driver、native Worker/helper canary 和全角色 hard-stop 仍需宿主证据；实例与 loop 必须由既有管理 UI 选择／授权，不能脚本暗建。评分须让不可信 pickle 只在无隐藏 labels／metric／results 权限的推断边界加载，把 features→predictions 交回可信原 grader；尚未证明原 grader 的实际加载入口可被该边界替代，不自造分数或读取评分器／答案源码。


### 任务专用双驱动（独立审查通过，限定源码接线；尚未实际激活）

[run_covshift_pilot.py](../scripts/run_covshift_pilot.py) 提供同一 `prepare → preflight → run` 入口，消费上述 exact launch。无模型实物已生成于 `/tmp/scid-covshift-driver-20261004-v2-prepared-004/pilot.json`：两臂新 project、相同七个公开输入、只读绝对路径别名、三个独立可写输出目录及受控 Worker workspace；控制／认证／历史只在 app-server 宿主边界，native named profile 不可读。外层白名单 bwrap 自有 PID namespace、die-with-parent；模型 API 保留宿主网络，任务命令禁网。仅加载 scid 自有 MCP，原题／评分资产／开发仓库不挂载。该安装 source `e77c61f` **不含新 daemon Factory 注入**；因此 preflight/run 拒绝旧安装，必须先审查、提交、构建并读回新候选，不能将本次 prepare 当 installed driver 资格。

准备命令为 `python scripts/run_covshift_pilot.py prepare --launch <冻结launch.json> --output <全新目录> --native <冻结native二进制>`；入口自带原 serial_lock/run_one，勿外套锁。可选 `--auth-file`／`--provider-config` 只向 fresh host-only CODEX_HOME 复制认证和 provider transport 配置，不复制个人 MCP／AGENTS／skills／会话。普通宿主使用新候选的 Python 对每臂 `--spec <pilot.json返回的spec路径>` 执行 `preflight`，然后同入口 `run`；没有自动重放或进程重启恢复。两臂的实际 aliases、fresh Root／模型配置和有效权限投影不符即拒绝。当前未提供真实账户配置，不运行此环境已知受 socket mask 阻断的 native/thread 路径。

`run` 先核 account/model/list，按 frozen 6.1-sol/high 拒绝静默换模型；在同一 200k／1800s 内执行仅合成输入的付费 role canary。放行须有真实 commandExecution item、实际 thread/session 与无权限覆写的 resume 投影；Sci 还核本场 exact Worker/helper attach。模型自报、standalone canary 和源码模拟均不能取得角色资格。canary 通过后科学 Root 为 fresh thread，不继承开发或 canary 对话；Native 使用 persisted Goal paused→首 turn→active 自动续行，Goal tokenBudget 扣除 canary 已观测成本，Sci 使用既有管理页面选新实例、授权 exact loop 并真实 background Factory。UI 冻结原件／loop／完整 effective profile 不匹配即拒绝；脚本不创建／绑定实例，不增加额度。

两臂共用单 CPU affinity、数值线程1，不主动设置 RLIMIT_AS，保留监督树 RSS1500000000 B／每 app-server 树 RSS1000000000 B／日志8MiB。开发和 preflight 仍默认300s；付费入口的独立监督窗口为 startup≤300s 加全角色 trial≤1800s，首付费 canary 激活后 deadline 不重置。计量复用 native usage high-water 和现有 loop records 去重；未知／回退或完成后无用量保守停，200k 为已观测异步停止阈值，in-flight 通知延迟可能超额，结果记录实测 overrun，不承诺零超额或固定美元上限。Native Goal aggregate 与 per-thread 用量不相加。此资源是 custom 条件，不冒充原题4h／4GiB或正式排名。

监督完成并清理拥有的进程后，宿主只检查 exp 的 regular `runs/submitted_model.pkl`／`submitted.json`、size 和 SHA，**不反序列化**；512MiB 是本入口工程检查边界，不重定义原题合法提交上限。可信原 grader 的隔离推断适配尚未完成，scoring=not_run。源码检查验证参数、幂等拒绝、计量／角色门禁及默认 daemon 兼容，实际账户／角色继承／两臂付费运行未验证；当前 `launch_ready=false`，不得将无模型 prepare 或 synthetic mock 计为科学通过。


本节点 v2 挂载增量已独立审查通过，首用量语义以后续 v3 为准：取消只读 `/usr` 下新建系统 exp alias；实际每臂 PATH 指向该臂私有只读 bin。`/opt/exp/runs` 在新 harness 中预留空只读挂载点，再覆盖既定可写 runs 目录；解释器仅补完整、有界 symlink 链的精确 runtime 文件，不新增用户 home 白名单。两臂的完整 outer mounts 已在默认 guard 下实际执行 `/usr/bin/true` 和 `exp --help`，核 wrapper 来源／SHA／只读、公开 instruction SHA 与三输出目录写入，均通过；未执行任务训练／AppServer／模型。

Sci interactive canary 所产生的同 loop `unmeasured_frontend_root` 保持不变，控制侧仍 partial；launcher 使用既有有界 accounting projection 与本实例／loop 的真实 accepted Worker/helper attach，逐一核 role／session／owner／loop，再与已取得真实 canary command receipts 的前台线程计量合并、按线程去重。缺 participant、覆盖遗漏、counter gap／回退或 scope 冲突仍停止，不能只因控制 partial 就抹掉已观测的前台用量，也不把 pending／unknown 当零。真实 control interactive→background＋attached Worker 回归通过，未清账／重授权／改变期限；全角色宿主实时通知和计量完整性仍须运行时资格，已核 identity 的原生执行中线程可显式 pending 等首 usage；尚无原生事实的 attach 只等5秒，终态后5秒仍缺用量、实际缺字段／回退或身份冲突停止，pending 不能解释为已知零或全 observed。旧 v1 与失败 mount 证据保留，launch_ready=false／scoring=not_run 不变。


v3 独立增量审查通过（源码边界；真实角色／双臂运行／评分仍未验证）：上述 pending 依据原 `pending_observation`／`native_turn`／`native_terminal`（Root 复用同控制行的 host/phase/turn），不只看 Run.running。原 native producer 先记录合法首 turn、尚无计量时，结果显式 `pending_native_usage`、pending_threads 与 known_tokens_lower_bound，原1800s期限仍运行；首 usage 正常归并。真实 Worker 与 helper 公开 attach／control 原生观测序列已覆盖首 pending、执行中等待、终态缺失拒绝及迟到首 usage，不新增 core 机制／账本，不重跑已通过的实际 mounts，不授 live 角色或科学资格。

2026-10-04 宿主双臂预检已实际触达 thread/start，均在 Root 权限握手拒绝，0 turn／0 tokens。原件的 named profile、approval=never、network=false 正确，legacy writableRoots 为冻结定义中八个精确可写目录；旧适配误套“只允许 cwd”规则。本次最小修复独立审查通过（限定源码握手投影）：named 投影按冻结的绝对 write grants 精确比对，仅已授写 cwd 可沿既有平台行为省略，不做路径归一化、不接受额外或缺失根；完整 config/profile/digest 校验与普通 legacy 行为保留。此为源码修复，须新安装及宿主重验，live 角色／科学运行／可信评分仍 pending、launch_ready=false。

随后新 candidate `249046610c0850ba22c594818f140abb4b76c922` 的已认证实物 `/tmp/scid-covshift-write-projection-20261004-auth-prepared-001` 已在正常宿主通过两臂 preflight：Native Goal 6.414s、SciDiscovery 12.574s，均 return0/exited、command_exit=0、十二项检查全部 true，0 turn／0 tokens、trial_started=false、无 active Goal。独立验收 `/tmp/scid-covshift-write-projection-20261004-host-preflight-review.md` 确认 fresh Root 权限握手与实际独立 native 命令／其子进程的公开读、私密/auth/history 拒读、写目录和禁网边界通过；这不证明模型内 Worker/helper 继承、全角色计量、账户模型可用性或评分。允许用同一已认证 spec 进入既有每臂200k／1800s内的付费 role canary 与 custom 工程 run，canary 计额且不重置；当前仍 launch_ready=false、scoring=not_run，不报科学分数。Sci run 必须使用本次新进程打印的当前管理链接，页面选新鲜实例、暂停后授权 `covshift.pilot.isolation` 的完整冻结 loop；不复用预检链接或手动抢先启动，launcher 自行继续。安装仍2490466，此次仅记录已审事实，不重建候选。

2026-10-04 Native 付费合成 canary 已失败，未进入 Covshift 科学阶段：真实 Root 与 fresh helper 共两个 turn、六次 usage 更新，逐线程高水位为 51814＋35579＝87393 tokens（缓存计数不再相加）。helper 确实已创建，但采用 gpt-6-astra/high，违反冻结的 gpt-6.1-sol/high；原外层只挂 native 主程序，缺精确 `codex-code-mode-host`，工具调用报文件缺失，没有成功 commandExecution 原件，不能取得角色隔离资格。旧结果的 turns_requested=0 仅漏记付费 canary 请求，不代表没有付费执行。原件／成本保留，Native 剩余额度112607，当前入口不支持跨进程续用该余额，禁止盲重跑或另开200k；Sci 尚未启动。

本次最小修复待独立审查：launcher 识别平台 `subAgentActivity` 的 exact parent／agentThreadId，冻结并只读挂载 sidecar 单文件及 SHA；prompt 明确 helper 的确切模型，先核实际线程配置、最终核 fresh host 有界日志中 canary 线程的每个 completed turn_context 模型／effort，而不把 Thread.model 当 per-turn telemetry。该门禁只覆盖 role canary，不能保证第一次错误模型调用零成本，也未逐 turn 强制后续科学阶段的 helper／Goal 续行模型。仍要求真实 exact commandExecution、session 和无权限覆写的 inherited profile；新增直接 Root turn/start 请求数、科学请求数及全角色 distinct(thread,turn) 数，usage 更新不是 turn 数。旧 installed／spec 不含该修复，不能因此获得运行资格。

无模型真实 runtime 检查已形成另一明确阻断：按本机0.159.2官方 framed 协议，connection/ready 和 session/open 成功；在原默认 AS2000000000 B 下执行最小 `text(2+2)`，V8 因无法预留 sandbox 虚拟地址空间退出（SIGTRAP），未执行 JavaScript。证据 `/tmp/scid-covshift-native-canary-20261004-runtime-probe-003/result.json`；这不是 RSS 超限，也不据此擅自提高 test 或 trial 资源。sidecar 挂载修复、standalone Python canary 与 --help 均不能替代 code-mode 执行资格；实际 runtime 资源条件、余额处置、真实 helper 权限／全角色计量和 trusted scoring 仍待定，launch_ready=false、scoring=not_run，当前不授权任何 paid/native retry。


用户明确取消开发检查及 pilot 监督的虚拟地址空间限制。本轮唯一无模型 sidecar 诊断已通过：官方0.159.2 framed `text(2+2)` 返回4、exit0、0模型，监督0.049s；exact sidecar 的 VmPeak1487235182592B、RSS/HWM22110208B，说明稀疏 VA 预留不能当实际内存消耗。原AS2GB失败／付费原件保持。该源码增量已独立审查并提交 `a019231`：共享 run_one 不再主动设置 RLIMIT_AS；RSS／可用内存／CPU线程／超时／日志／UID串行锁保留，旧资源配置的 address_space_bytes 警告后忽略，不突破外部父进程已施加的OS硬限。只更新开发／验证和pilot监督，不改变科学执行／展示助手自身已冻结的资源契约；旧spec／安装资格不被追认。新资源策略与V8零模型通过不授权付费重试／额度重置，Native已耗87393、余112607且跨进程余额续用仍未支持；实际角色与评分继续pending、launch_ready=false。

本次更低上限准备源码已独立审查通过（限定参数接线）：launcher 的 `prepare` 接受 `--native-goal-tokens`／`--native-goal-wall-seconds` 及对应 `--scidiscovery-tokens`／`--scidiscovery-wall-seconds`，默认仍每臂200000／1800，只接受不超过默认的正整数。各臂 spec 的 `limits` 是实际新尝试上限；paired `arm_limits` 列出两臂值，顶层 `limits` 保留原授权天花板。AgentSettings、Meter、Goal、UI授权比对和整场监督沿同一臂值；旧spec缺此字段时沿原默认，不承接旧loop／Goal／计数。针对已有Native原件87393 tokens、监督38.238s（phase33.948s），保守扣39s后拟新Native上限112607／1761，Sci仍200000／1800；旧耗用不退款、不重置，不把此余额改成未来默认。startup仍有独立300s窗口，paid deadline自本次首canary激活计时；异步计量可能超额并须记录。`run` 自带fresh Root与原生命令预检，通过后才进入计额role canary，无需另跑一次preflight。科学题面追加全角色6.1-sol/high要求，提示不能保证实际模型；现有turn_context门禁仅核canary，科学阶段真实profile覆盖仍unknown。新安装／认证spec尚未生成，本轮无paid或科学执行，trusted评分未实现，launch_ready=false。

2026-10-04 更低上限 Native 尝试仍在付费合成 role canary 阶段退出，未设置 active Goal、未进入 Covshift 科学阶段／评分：本次79871 tokens、监督43.826s（phase39.866s），与旧87393累计167264，原200000余额32736；费用与时间原件保留，禁止自动重试、退款或重置。两条真实线程的 turn_context 均为 gpt-6.1-sol/high，真实 CommandExecution 均 exit0、十二项 OS 检查全真。0.159.2 将命令 argv 按 shell 格式投影为 `/usr/bin/bash -lc <exact canary command>`，旧裸字符串比较误拒。当前最小源码修复待独立审查：仅接受原裸命令或严格三项 `/usr/bin/bash`、`-lc`、exact expected command；status／exit／thread／turn／usage／继承权限原门禁保持。五项定向源码检查及受控离线原件回放通过，仅确证本次命令回执事实，不重建完整运行资格、不跨进程复用 proof／跳过 canary；科学阶段真实模型、完整角色资格及 trusted scoring 仍 pending、launch_ready=false。本节点未发送任何新模型请求。


2026-10-04 零模型权限诊断002的宿主结果为失败，尚未补齐权限资格。`thread/read` 冷读返回 notLoaded／空 turns；独立核查确认原线程使用分页历史，诊断遗漏 `thread_history_1.sqlite`（原 turns/items/projection=2/12/2，副本=0/0/0）。本次0.653s、RSS130678784B，无内存止损、无新模型回合，原pins保持。003已补齐一致性历史副本并保持严格终态／身份／权限检查，37项本地检查与独立审查通过，宿主尚未执行；不放宽空历史判定，不重跑付费canary。当前Native累计167264 tokens、余额32736，science=0、scoring=not_run、launch_ready=false。细节及下一入口以[当前交接](plans/DEV_HANDOFF_20261004.zh-CN.md)为准。
