# U4 cov audit unknown 只读诊断

状态：当前真实场继续运行，本记录仅定位 A003 audit unknown，**未改生产、冻结场次、预算或状态，未 retry audit、运行测试或调用模型**。未把 unknown 授为 audit 成功。

## 现场事实

[A003 outcome](../../../../../.trial/rootless-u4-cov-20261014/instance/native-evidence/003/candidate-audit/outcome.json) 为 accepted=true、candidate_id=run-2、status=unknown、note=`delivery_resolver_unavailable`、cleanup_confirmed=true；binding_sha256 与 process_sha256 为 null。该目录仅保留 intent/outcome/adapter-result，说明失败发生在 source resolver 阶段、未取得可供实际 audit 调用的 binding。outcome SHA256=`c66b9e6a1fe8bbcd16cfc59cadf3baa14816916d00811f45827804f2bc43761b`。

settings 的 delivery adapter inputs 确实只有五个 harness 输入和 runtime-python，但**这不是缺少手工配置 protocol 输入的证据**。`delivery._adapter` 明确禁止 caller 使用保留 label `scid-current-protocol`，并自动追加当前 protocol.py 的路径/SHA/字节数；`freeze_sources` 将该追加原件复制到 stage/inputs 并传入 request。隔离 launcher 只读挂载整个 inputs 到 `/inputs`。因此当前设计已负责传递该原件，不能通过热改 settings 或 caller 手加该 label 修复。

## 最小生产根因与证据边界

实际安装 `cov_delivery._current_guard` 中：

```python
data = _exact(source, 256_000)
if source != host:
    ... hashlib.sha256(data) ... len(data) ...
```

`_exact` 返回 `Path`，未读取文件字节。host 调用时旁侧 protocol.py 存在，跳过这段 proof 校验；隔离 leaf 以 `/delivery.py` 执行，没有旁侧 `/protocol.py`，转向 `/inputs/scid-current-protocol`。其 proof 由框架追加，随后把 Path 传给 hashlib.sha256，必触发 TypeError；len(Path) 同样无效。这是 current-protocol guard 的隔离集成遗漏，不是模型科学判断或场次未手填输入。

独审读取实际安装与源码，三模块 SHA 一致：cov_delivery=`ecffb90c90a5b34ccacb6bc02ecaea496779f6ed53cc2bd732e4e7b0da4f7b0a`；delivery=`a6626df9e8f63a77f603da23312b57d4d4baf1159cc3c2cfd7e60ac96bd5c501`；protocol=`8b999d55e323f46f761fc2def3c2e97e3e44650e8d9449f55ad5805788c22030`。

现场没有保存 leaf traceback：`delivery._call` 消费但不保存 stderr，并对非零 exit 返回 None；freeze_sources 将 None 归一为 `delivery_resolver_unavailable`。因此 TypeError 是依据实际冻结代码和隔离路径的确定缺陷、对本次失败的强根因推断，不能声称已从现场 traceback 直接观察。其他提前 namespace 故障未由这条泛化 note 排除。

## 对最终 delivery 的影响与后续最小修法

- candidate audit 和最终 delivery source preparation 均调用同一 `freeze_sources` resolver。leaf 在处理 phase 前先调用 guard；resolve/audit/promote/confirm 都受相同缺陷影响。若其他条件允许本场进入最终 delivery，该路径仍不能获得成功资格，不能将当前 audit unknown 当作仅一次候选偶发失败。
- 后续授权修复的最小方向是保留 exact/bounded 路径验证后读取文件字节，再以这些字节校验 SHA 和长度，继续对冻结 proof 和 scope 执行原 current guard；不删除 guard、不恢复旧协议兼容、不添加第二 ledger。
- 必要验证应走实际 installed `--isolate`→bwrap `/delivery.py --leaf`，覆盖 framework 自动注入的 protocol 输入、真实 resolve→audit→promote/confirm；同时缺失/改变 protocol 原件必须拒绝。直接 host leaf 调用旁侧 protocol.py 不覆盖 fallback proof 校验。既有真实 native H/W/A namespace 门禁没有调用该 delivery leaf，不能据此授 audit/delivery 资格。
- 本次按用户要求先运行定位，不热修现场、不重签 settings、不重新提交候选，也不恢复任何不确定外部动作。现有失败 receipt 与当前科学运行责任继续沿原 owner 保存。
