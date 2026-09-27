# R3 验收记录：隔离安装、512MB 与真实短 TCAD

## 当前结论

2026-09-25，用户允许受限安装、构建和短 TCAD，并在上轮 OOM 后明确将大文件测试改为 **512,000,000 字节**、该项严禁并发。此次验收全程只有一位执行者，所有步骤串行；未运行全套测试，未改变现有服务。

**本轮约定范围的验收已完成：源码、runner 边界、隔离安装、512MB 本地流式文件，以及真实 SSH 下的短 SProcess / SDevice 均取得通过证据。** 原连接阻断在用户提供可达地址后解除。完整外部 LLM 科研流程、512MB 网络传输和 2GB 实测未执行，不在该结论内。 用户指定部署目标是当前目录下测试后删除的临时目录，因此本次安装是临时候选验证，不是持久部署。已有短 TCAD 授权仍有效，不需要重新申请相同权限。

| 项目 | 结果与边界 |
| --- | --- |
| 已有源码验收 | [20 选择项、29 案例](FOUR_MODULE_R3_SOURCE_ACCEPTANCE_20260925.zh-CN.md)已有分批通过证据，本次未重跑。 |
| 已有 runner 验收 | [6 选择项、15 案例](evidence/four-module-r3-20260925/runner-acceptance-first-run/result.json)已通过，包含真实受控子进程、小额度停止、预算重启和模拟未知提交查询；不是实际 TCAD solver。 |
| 候选构建 | 核心、curve-score、figure、TCAD 四个 wheel，以及一个已有 blind-CSV 协议测试插件，依次构建成功。只暂存实际包声明的源码和资源，没有复制 docs/evidence 或全安装矩阵。 |
| 隔离安装 | 不继承系统 site-packages 的 venv；pip 安装四个候选 wheel，`pip check` 通过。14 个第三方运行依赖按现有发行包 RECORD 精确离线复用，共 33,746,122 字节；**不是重新下载、解析全部依赖的 pip 干净安装证明**。版本清单见[依赖清单](evidence/four-module-r3-20260925/final-512/offline-dependency-inventory.json)。 |
| 已安装 catalog / 资源 | 真实 installed 路径编译 ABI19、48 个 Operation、8 份 scheduler guide；版本、catalog 摘要和 wheel SHA256 见[安装身份](evidence/four-module-r3-20260925/final-512/installed-catalog.json)。 |
| 已安装 figure 工具 | 已打包图像依赖成功生成、检查只读源图，真实工具活动记录符合合同；完整科学图证据闭环仍使用前述源码证据。 |
| 已安装 Worker 协议 | 安装已有 blind-CSV 插件后完成真实临时 Run/Artifact 与 Hardened Worker 文件提交；不是调用外部 LLM 作者的科研闭环。 |
| 512MB 流式文件 | CAS 注册/原件读取、本地子进程 remote helper 上传/下载四阶段通过，SHA256 一致，实体文件已删除。**不是网络 SSH 传输，不证明 2GB 实测通过。** |
| 真实远端 TCAD | 用户提供可达地址后，临时当前 runner 执行 R-2020.09 SProcess / SDevice 成功，原生 TDR/PLX/PLT 与日志经真实 SSH 下载校验；仅工程短任务，不是科研资格或持久部署。详见下方续验。 |

## 512MB 的实际证据

[四阶段记录](evidence/four-module-r3-20260925/final-512/transfer-512-stages.json)、[监督器结果](evidence/four-module-r3-20260925/final-512/16-transfer-512.json)、[持续内存采样](evidence/four-module-r3-20260925/final-512/16-transfer-512.metrics.jsonl)：

- 文件字节数 `512000000`，SHA256 `6d56271d2d71cb8552d4291610000eb6a3d1b84705321012aab07e929fe9a4e0`。
- 分块 `262144` 字节；禁大文件 `Path.read_bytes` 和整份 CAS 读取。保留源+CAS、CAS+上传、上传+下载中的至多两份，换阶段删除上一份，结束删除所有大载荷。
- 共 7.408 秒，进程树 RSS 观测峰值 **72,208,384 字节（68.9MiB）**，无残留活动进程。
- 117 条持续落盘指标，Dirty+Writeback 观测峰值 73,818,112 字节，MemAvailable 观测最低 14,380,752,896 字节；系统 Cached 峰值 1,865,744,384 字节。Cached 是全系统观测，不能等同本测试独占内存。
- 监督器针对临时载荷的 `fdatasync` / `POSIX_FADV_DONTNEED` 各成功 44 次，失败 0；生成源文件时各成功 62 次。缓存释放建议不保证页缓存严格低于某个上限。

## 资源控制与失败保留

实际配置见[limits.json](evidence/four-module-r3-20260925/final-512/limits.json)。测试阈值不更改生产配置中的 2GB / 1 小时自主执行额度。

- 串行锁；数值线程 1；单步骤 300 秒超时，传输单次 120 秒。
- 每进程 `RLIMIT_AS` 768MiB，进程树 RSS 观测超过 384MiB 停止；目标采样间隔 50ms，采样及 IO 有实际延迟。
- MemAvailable 小于 8GiB、相对步骤开始下降超过 1GiB、或 Dirty+Writeback 超过 128MiB，均终止并回收被测进程树。指标持续写入、flush、fsync，结束记录残留进程。
- **没有聚合硬隔离**：cgroup 挂载只读、user bus 不存在、systemd scope 需认证。上述 RSS/系统内存是采样止损，WSL MemAvailable 也不是 Windows 宿主可用内存保证。没有声称已经能绝对防止 OOM。
- 32MiB 子进程分配控制在 24MiB 测试阈值下真实触发停止，父子均退出；8MiB 控制先证明传输，再降低该控制的缓存处理窗口至 1MiB，实际确认监督器缓存处理成功。
- 初次缓存控制发现封存只读文件不能 `O_RDWR` 打开，错误保留于[04-cache-control-error.json](evidence/four-module-r3-20260925/final-512/04-cache-control-error.json)。仅修验收监督器为 `O_RDONLY|O_NOFOLLOW`，不改生产封存权限。人为权限错误控制另验证异常时先杀全树、再持久化失败结果，避免 finally 覆盖原错。
- 首次安装复制了三份 Python 解释器约 94MB，叠加依赖写入触发 **128MiB 脏页止损**，不是 OOM。保留[12-install.json](evidence/four-module-r3-20260925/final-512/12-install.json)。删除本次部分 venv，改为解释器 symlink、精确依赖逐文件同步/缓存释放后通过，未提高阈值。
- 上轮 2GB 中断的[事故原记录](evidence/four-module-r3-20260925/interrupted-large-file-incident/incident.json)保留，不因本次 512MB 通过改写 OOM 因果或抹去失败。

## 原远端连接阻断（后续已解除）

1. [IP 查询](evidence/four-module-r3-20260925/final-512/remote-reachability.json)：`resolver exit 1: <3>WSL (9) ERROR: UtilBindVsockAnyPort:287: socket failed 1`。仅运行配置的 VMware `getGuestIPAddress -wait` 查询，没有启动 VM。Windows 查询进程不受 Linux 地址空间限制，此项单独记载。
2. [显式目标 fallback](evidence/four-module-r3-20260925/final-512/remote-fallback.json)：Linux SSH `BatchMode=yes`、严格已有 known_hosts、连接超时 5 秒、整体超时 10 秒；5.327 秒退出 255，`Connection timed out during banner exchange`。未扫描或猜测地址，未重试循环。
3. 用户随后确认 VM 运行并提供可达地址，仅在本次临时连接配置覆盖地址，沿用既有端口/凭据与严格 known_hosts。此阻断已解除，旧失败证据保留；后续真实结果如下。

## 真实 TCAD 续验

[汇总](evidence/four-module-r3-20260925/real-tcad/summary.json)、[两条通过链](evidence/four-module-r3-20260925/real-tcad/solver-stages.json)、[远端监督结果](evidence/four-module-r3-20260925/real-tcad/remote-monitor-result.json)。

- 真实 SSH 确认远端 Python3.6.2、约 8GB 内存及配置工具可用；只在远端临时目录放置当前源码 helper、配置与监控器，未修改服务或原 helper。
- 先发现精确生产策略/能力，再由实际 `ExecutionPolicySnapshot.admission` 生成 policy 凭证。runner 确认缺失凭证请求被拒、有效凭证通过，随后执行 job wire4。**这证明策略接口到真实 runner 的合同，不是新的一条 Root 科学资格审批端到端流程**；Root、审查、预算身份由已列源码/runner 证据覆盖。
- SProcess 成功生成小型二维硅网格、短扩散、原生 [TDR](evidence/four-module-r3-20260925/real-tcad/artifacts/device_fps.tdr)（317,880 字节）及 PLX（312 字节）；预算收据墙钟 16 秒、逻辑存储 357,296 字节。
- SDevice 使用该 TDR 完成平衡与 0.01V 短扫，返回 exit0，PLT 2,339 字节；预算收据墙钟 12 秒、逻辑存储 703,554 字节。每份输出均通过当前 SSH 流式下载接口核对大小和 SHA256。这是小文件网络实测，与先前 512MB 本地 helper 项分别记载。
- 本轮本地树 RSS 观测峰值 69,984,256 字节，远端观测峰值 174,059,520 字节（约166MiB）；无内存/存储阈值触发。SProcess 的 AdvancedCalibration 提示保留，未靠改物理模型消除告警，也未据玩具算例作科学结论。

### 失败、修复及内存设置

1. 首轮验收脚本把 StrictModel 直接传 SchemaModel 的 canonical 函数；仅改为显式 `model_dump(mode="json")` 后序列化，未启动 solver、未改生产代码。
2. 768MiB 地址空间使原生 SProcess 在加载阶段失败；[strace](evidence/four-module-r3-20260925/real-tcad/loader-diagnostic.json)明确 `execve ... ENOMEM`，[ELF](evidence/four-module-r3-20260925/real-tcad/elf-inspection.json)显示仅 LOAD 段已需 1,116,633,892 字节。经调度确认，仅远端 solver 的 **虚拟地址空间**改为 2GiB；本地仍768MiB，远端树RSS止损384MiB、可用内存底线3GiB、可用下降1GiB、脏页128MiB、单线程、60秒和16MiB任务存储均保留。2GiB AS 不是允许占用2GiB实际RAM，也不是生产2GB存储策略的改动。
3. 5秒版本探测已打印 R-2020.09，但在许可证启动等待时触及该诊断超时并被终止；进入原已授权60秒真实任务后，SProcess正常完成。没有扩大60秒上限。
4. 首个 SDevice solver 本身已 exit0，但测试声明 `device_output.log`，原生实际输出 `device_output.log_des.log`，runner 正确报告缺输出/exit97。只修输出声明，复用已成功SProcess的原件并续跑SDevice新job；未重跑SProcess、未改solver物理内容。
5. [attempt3](evidence/four-module-r3-20260925/real-tcad/attempt3/result.json)监控记录中 AS 描述字段仍是旧768MiB；实际执行限额以当次 [job声明](evidence/four-module-r3-20260925/real-tcad/attempt3/process-submission.json)的2GiB为准。该记录原样保留，续跑监控描述已纠正，其余止损字段未变。没有cgroup聚合硬隔离，采样仍有漏采/超调限制。

本轮只改验收脚本和声明；248个生产文件逐项匹配前次安装候选，没有生产修复需要重新扩展运行验证。原生下载哈希对应脱敏前原件，归档文本日志做环境信息脱敏，另以manifest记录实际归档字节身份。

## 候选与清理

本次没有修改生产实现或业务断言，只增加受限验收脚本、记录并更新当前文档状态。源码候选身份和全部本次证据哈希见 `final-512/candidate.json`、`final-512/manifest.json`；不是 Git HEAD 已提交或已部署声明。

唯一临时目录由用户要求创建于当前目录，路径见[temporary-root.txt](evidence/four-module-r3-20260925/final-512/temporary-root.txt)。结束删除所有 wheel、venv、临时工作区、大文件及临时复制的 SSH key/known_hosts；归档不包含凭据或许可证值。实际删除及进程检查见[cleanup.json](evidence/four-module-r3-20260925/final-512/cleanup.json)。此前512MB阶段未创建远端目录。随后真实TCAD阶段新建的远端与本地临时目录已分别清除，见[远端清理](evidence/four-module-r3-20260925/real-tcad/cleanup-remote.json)和[本地清理](evidence/four-module-r3-20260925/real-tcad/cleanup-local.json)；无残留runner/solver，临时凭据一并删除。[真实TCAD证据清单](evidence/four-module-r3-20260925/real-tcad/manifest.json)独立归档，不改写final-512既有manifest。
