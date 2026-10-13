# U3 单当前协议与科学意图独立审查

状态：**PASS（U3 current14机械合同与科学意图解析，无模型）**。production05/source08最终冻结、独立语义审查和最终安装差量门禁已绑定，无剩余生产阻断。 基线U2提交`285cc35`。当前权威为`/tmp/scid-u3-production-05.json`二十五项生产（其中未改local/cov实现也列于冻结清单）；已实际核对全部SHA。source08三十三项已逐字节全部MATCH；最后controller mock fixture仅两处补当前中性control_outcome，不改生产。独审者没有编写U3生产/测试，仅修改本报告，未运行tests/build/Git/model。

## 当前合同与可用性

- current14是唯一科学写合同。settings/job/execution scope必须匹配冻结当前标记；标记仅说明兼容，不授预算、运行权限或科学资格。新prepare只建fresh目录，无旧instance在线迁移。
- 默认new prepare/CLI启用search.DEFAULT_POLICY；即使没有portfolio policy，原件fold仍拥有unfinished plan/allocation/seen W。null沿计划，显式exact ref优先/唯一label+route_reason可选择已授权分支，不要求作者写priority/exploration_order。未授权/歧义/waived/空计划只形成有界科学诊断；内部机械故障仍为host error。
- 同一prospective解析供semantic、decision key和portfolio；control_outcome保存resolved focus/allocation，fold重算匹配且全部valid后才commit。原最终W seal身份绑定原allocation，合格A消费一次；mechanism repair沿exact repair_root原机会去重，native/output repair仍同科学stage，不另制造cycle/ledger。
- 片段、decision、portfolio、audit、H/A配额仍各按显式policy，不强开所有feature。W job冻结context配置；science-task明确configured/unavailable/context及原终态、cleanup、usage、session、shared授权资格。configured不表示真实LLM恢复已资格。
- 未配置时W continue不默默重启：科学raw保留，control_outcome记continuation_unavailable，A收到固定短question判断原贡献和限制，不产生author correction。第八科学route负控已补实际A job→frozen science-task.question。

## 生产所有权与拒旧边界

复用原host writer/control budget ledger、科学job/seal、native attempt链与注册受管原件owner。owning guards在锁、mkdir/复制、预算/发布、native/runner、实验configure/Records accept/publish、seal、归档/页面、correction、audit和delivery作用之前拒旧。namespace只核host冻结scope，不读hostroot；standalone cov leaf加载host冻结pure protocol核scope，不引回MCP/重服务。

旧status/受管preserved progress只读既有原件与页，专用archive不调用当前schema、科学fold、observer或缓存重建；列截断有omission/partial usage，原件coverage不是在途消耗最终精确总量。旧closeout --export-only原实现会写ledger，因此typed拒绝，不追加export入口，不能称旧export已资格。

旧在途的采集/cleanup责任保留原冻结owner/运行环境；archive不终止、不重提、不将unknown当完成。新包旧scope load/lookup/collect/cancel拒写，不承接旧在线迁移，也未取得真实旧inflight跨包collect资格。切换不能靠修改协议标记重新授权旧stage，须由原owner完成/收集并保限制；本步不新增旧执行兼容路径。

## 发现、修复与历史失败证据

以下为已闭合历史阶段，不表示当前未审：

1. pure01 archive bounded列表未标遗漏，父指出后pure03补omitted nodes/native records、partial usage/coverage；旧未读不当完整0。
2. 独审指出scientific mechanism repair会在原portfolio owner多计cycle；pure03复用原repair_root seal identity、same-item repair不完成cycle、最终合格非repair A只完成原机会一次，不增第二counter。
3. actual01 checkpoint.end_stage缺current owner guard，旧unverified checkpoint可避开science_payload而写stage-end；production03同capture在任何读取/写入前核current exact job，新增owner负控。
4. 父installed basic失败；独审定位contracts.validate旧elif清理后无条件raise，正确receipt也失败。production03改为仅缺receipt的else，不强开search掩盖。
5. 父source03 fragment七失败来自fragment_review漏handoff_protocol。production04以protocol.stage_scope一个host函数供configure/publisher/fragment_review/cov wrapper四点，固定initial owner，exact校验不放宽。
6. scientific_routes首轮五通过、两夹具失败：六元_route直接传七元effective。修为真实_route→correction.effective_route→semantic.effective_route；不是生产故障或PASS证据。
7. 最终production05安装第一轮135PASS/3FAIL/1SKIP，科学八项全PASS。三controller mock seal缺当前control_outcome，作者只补现合同夹具，不松生产；最后controller安装补跑46PASS已闭合；最终按差量去重合并138PASS/1SKIP，非单次全量重跑。失败证据保留在父门禁日志。

## 最终证据绑定

独审已实际读取以下父级日志/结果，未自行运行门禁：

- outer `.trial/u3-source-04-20261013/batch-001/pytest.log`：工程五文件130PASS/1SKIP，36.78s。
- outer `.trial/u3-source-06-20261013/batch-001/pytest.log`：最终生产05三文件66PASS，24.33s（scientific_routes8、workerfragments20、currentprotocol38）。随后source07只补A实际task断言、source08只补两处controller mock中性receipt；生产05不变。
- outer `.trial/macro-role-installed-20261012/artifacts-u3-05-20261013/u3-installed.log`：六文件首轮135PASS/3FAIL/1SKIP，35.61s；科学八项（含实际A task断言）全PASS，三项仅mock seal缺control_outcome，不是生产放宽。
- 同目录`u3-controller.log`：修复最后mock后controller全部46PASS，2.84s。与首轮已通过职责按用例去重合并为**138PASS/1SKIP**，不是声称单次全量全绿；失败日志保留。
- 同目录`u3-controller-result.json`：returncode0、model_requests0，22模块实际site-packages导入；首轮`u3-installed-result.json`returncode1如实保留。独审直接读取24个production安装模块字节，全部与production05匹配；launcher repo字节也匹配冻结清单。
- 同目录`result/result.json`：freshwheel build_check PASS，实际已安装CLI fake H→A→W→A、restart/no replay、route context保持、29模块source绑定，model_requests0。wheel字节实际SHA：`f71d793a28fc942d41432c3e8c45eeed190790fdc74524c5ce0cbe67547eeab9`，独审读取实际wheel匹配。

最终production05二十五项/source08三十三项SHA均实际MATCH。manifest文件字节SHA：production05 `9f87e048392352b38bc35f59c2e84441ece7ff4ae7424eca9e19c444d54c3748`；source08 `8c76aa187b00fa67c962cf4ffb05a8a6d0e98a5ebcc457c4697e4567e5cc3922`。

## 资格限制

通过范围仅为当前协议机械生命周期、科学意图解析、原件绑定与无模型拒旧写。八科学route用真实current jobs/raw/seals，部分经实际controller路由链，最终决策/研究效果由科学Worker负责；fake native只测真实本地transport，不代表真实LLM行为或科学正确性。

没有真实LLM同session/fresh恢复、平台压缩、成本收益、TCAD、目标域科学效果或旧inflight在线迁移资格。token仍观测下界，不能承诺零超额；任意未受管shell沿原权限与覆盖限制。U4未授权。

## 历史纯预审记录

pure03五模块/tmp已审、协议owner/CLI全tree负控草稿已审；它们是提前发现缺口的历史证据，不替代当前repo接线和最终安装资格。上述历史预审不保留当前待办；最终生产manifest文件SHA256：`9f87e048392352b38bc35f59c2e84441ece7ff4ae7424eca9e19c444d54c3748`。
