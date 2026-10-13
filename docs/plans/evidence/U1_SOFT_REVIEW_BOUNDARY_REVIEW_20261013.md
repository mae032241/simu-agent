# U1 通用软复核边界独立审查

状态：**PASS（U1通用受管执行软复核边界，无模型）**。production03/source03独立语义审查与最终安装、namespace证据已绑定，三个实际阻断均已修复。独审者仅参与边界设计，没有编写U1生产或测试代码；只修改本审查报告，没有运行测试、build、Git或模型。

## 最低实际依赖与所有权

复用U0r已审通用`Records`与注册生命周期，不增加cov专属门控或平行执行/预算账本。共用接受原件仍由`experiments.py`拥有；solver由注册实现执行，科学结论属于Worker。

- `budget.py` / `native.py`：从原settings、job、native-intent的node/search冻结限额与累计anchor、clock、known native usage及共享收口预留派生复核事实，复用初始与5秒/usage-event发布，不创建新的monitor进程。
- common `Records.accept`：与host publisher共用短锁，锁内读取/核对exact事实并提交accepted原件；准备与长asset扫描、模型、外部执行均在锁外。实施首版将node.lock收短到接受提交，接受后通过原件状态阻止新的并发调用；publisher只取得独立accept.lock，不等待solver。
- launcher只读目录挂载与feedback小投影：host-runtime中的稳定stage-jobDigest目录以原绝对路径只读映射到Worker namespace，其中facts原子替换可见，readonly fd可flock同一accept.lock inode。不挂hostroot；原`budget-status.json`继续advice，不能授权。

## 本步冻结合同

新prepare与job冻结`managed_admission_version=1`，实验config携带该准入合同及host控制目录。旧不匹配managed写入口先拒绝；查询、lookup、收集原身份保持本来的冻结config/scope，不经过新实验gate。

本步不清理科学schema或升science14。全实例模型、控制ledger、交付、封存等旧写入口的统一退役与单当前科学协议由U3独立覆盖，不能把本步实验准入拒旧误称成旧U0p全面写退役已完成。

事实绑定exact job/current attempt与original stage budget anchor；机械hash用于内部校验，不进模型表单/公开feedback。BOOTTIME deadline由受管调用本地重算，避免5秒旧快照继续接受。观测token仅lower bound，in-flightunknown保限制，不表示零消耗或新增授予；不能承诺零token超额。

同stage pending由原预算/科学授权累计重建，投影丢失或新attempt不reset。没有mechanism投入限额时仍以共享reserve/hard可用事实决定，不自动强开H/A科学配额。后续U2新fragment必须显式沿original stage，U1不会仅凭同job预算continuation宣称新fragment接续已资格。

接受线性化点为短锁内accepted原件提交，host请求发布与它同锁排序。此前接受作业完成/查询/收集，后续run拒绝；普通软边界不kill进程，总授权hard cutoff与安全停止沿现规则。拒绝不得在正式calls目录留下貌似accepted的phantom记录，源码预备放在calls外或明确清理。

host无新Worker调用时仍由现publisher看到pending；W无合格实时通道时只在下一次工具回包/query获知，并保留通知延迟。任意未受管shell保持覆盖未知，不宣称强隔离。

## 审查范围

独审仅检查上述实际生产边界与必要无模型负控，绑定父级source、installed及真实namespace证据；U2/U3或TCAD远端能力不在本步资格内。

## 最终生产绑定与阻断闭合

基线`fc11485`，`/tmp/scid-u1-production-03.json`八项与`/tmp/scid-u1-source-03.json`十四项SHA逐一全部匹配。生产03仅在02基础上修正configure验证/写入顺序；其他七项生产字节不变。

| 文件 | SHA256 |
| --- | --- |
| `src/scidiscovery/research_loop/experiments.py` | `81247f72d34c29a05a17948283b3482925fe07f81835d79f35af9d1325219bce` |
| `src/scidiscovery/research_loop/budget.py` | `75be3418127048644808f06f28dafdd70028a247174e1938cac46bf44cc50a30` |
| `src/scidiscovery/research_loop/native.py` | `fc8cac183524db0d74741bcdc6ce20514afb7d6a000dc8cee7b83a9e462023b6` |
| `src/scidiscovery/research_loop/controller.py` | `681cc34f5146cec1146dbdae0c5ef5a1861d2148db30866a885c4c61f1d2d25e` |
| `src/scidiscovery/research_loop/contracts.py` | `73a22c5652c1c8a376119eb7abf6604f52f980c03d250bd7a93602f132fc168f` |
| `src/scidiscovery/research_loop/feedback.py` | `8f42ae333c113e5144d4190f478547a2f10725a8bb2aedabb4143a47f19ab1c0` |
| `src/scidiscovery/research_loop/cov_lineage.py` | `860c9aa93316f70e7bccfb5c2ceb3312a85d60c4317cba94ac8d059dffc8332b` |
| `scripts/acceptance/rootless_cov_launcher.py` | `b0dbf3183ee5fa6f45d5ce9fca009a14efaa73531579b918036fb86aa49f8701` |

独审发现并复核修复的三个真实路径：

1. 默认`mode=unavailable`不再错误授予新接受：仅冻结hard明确免软门控，soft检查host事实，其他mode拒绝。已知原身份query/collect保留事实结果并附unavailable反馈。
2. 两个真实publisher（native初始/5秒/usage-event与configure）采样与发布同短`accept.lock`排序。锁内重取clock、以同stamp计算snapshot、读取current original intent/usage，再派生与原子发布，不采信旧传参的limits/meter。无solver、LLM或source/model资产扫描；不读取旧pending作为授予或粘滞状态。shared_usage_unknown在原meter恢复后有出口，实际阈值仍由原件保持。原token计量只能下界；current inflight未知明确保留限制。
3. 同attempt重configure变更参数时，旧实现先改current pointer再因immutable config冲突拒绝。production03先核所有scope/immutable冲突，之后才写配置。新增负控同attempt改max_seconds被拒，pointer exact bytes与原attempt配置不变。没有增加跨进程配置事务合同。

父级先前指出的两项同样已闭合：projection不沿old.pending当权威；review_feedback失效不会覆盖已知query/collect成功。新接受仍直接走fail-closed review_status。

current stage owner以初始job digest固定，native_attempt另绑定，各attempt保留自己的config，namespace当前指针不能改stage scope。accepted在calls外prepare，锁内检查最新call列表/host facts并提交，拒绝清理prepare，正式calls不留phantom。请求回包没有私有hash/host绑定；只读目录atomic replace可见，不暴露hostroot。

## 无模型证据与适用限制

- production02 freshwheel已安装七文件回归：`162 passed, 1 skipped in 77.37s`，日志outer `.trial/macro-role-installed-20261012/artifacts-u1-02-20261013/u1-installed.log`，安装模块路径/SHA在同目录`u1-installed-result.json`；其中experiments为02字节，其他本步模块匹配03。此证据覆盖未改职责，不能替代03差量门禁。
- 同目录`result/result.json`为build_check PASS，fake native H/A/W/A、恢复不重放、model_requests=0。fake native不授科学遵循或效果资格。
- 同目录`u1-namespace-01-result.json`读取确认真实launcher只读目录：first registered covfixture成功、原usage达到共享reserve后next run拒绝、original call query成功、Worker写review.json得到EROFS；model_requests=0。production03已重复入口绑定通过。
- production03 source：outer `.trial/u1-source-03-20261013/batch-001/pytest.log`，`36 passed, 1 skipped in 24.15s`。新增边界测试由managed fixture参数化local/cov；覆盖发布先于接受、在途跨边界仍完成、原身份lookup/query/collect、缺合同拒绝、反馈坏而成功不丢、same-stage累计与cache丢失重建、unknown恢复出口/旧样本不覆盖原件、同attempt配置拒绝无pointer写副作用。restart仅工程原件重建，不宣称真实native resume。

source前轮unknown恢复夹具在读取未封存H历史时失败，修为先合法封存H→W后进入目标断言；未放宽生产校验。cov不适用项保持skip。soft边界不kill普通片段；任意未受管shell、恶意绕行、真实模型token实时精确截止、科学结果与真实TCAD执行均未取得本报告资格。U2 fragment与U3协议一次启用另验。

最终03证据已逐项读取：

- outer `.trial/macro-role-installed-20261012/artifacts-u1-03-20261013/result/result.json`：build_check PASS、fake H/A/W/A、恢复no_replay、model_requests=0。实际wheel SHA256：`139090104436613a4bf101ee2e5591ea576a54c033494d24555849bd4b61e9a6`，独审直接读取wheel字节hash匹配。
- 同目录`u1-added-installed.log`：`20 passed in 11.99s`（新增review_admission及covdelivery）。`u1-added-installed-result.json`确认site-packages加载与model_requests=0；独审直接核七个本步安装模块SHA均与production03匹配，launcher repo字节也匹配冻结清单。
- 同目录`u1-namespace-01-result.json`/`.log`：实际launcher.prepare_home + outer bwrap + registered covfixture执行通过。真实usage.json触发reserve，host atomic派生发布后下一accept拒绝且calls仍1；原call query成功，Worker写事实EROFS，model_requests=0。探针`u1_namespace.py`及`run_u1_namespace.py`已只读核对，未调用模型。

03变化仅configure验证顺序；02的七文件回归162PASS覆盖未改职责，03新增安装20PASS与source36PASS覆盖新配置负控及边界/交付。没有再次扩大验证或将fixture结果当作科学资格。本次独审未编写生产/测试、未运行tests/build/Git/model。
