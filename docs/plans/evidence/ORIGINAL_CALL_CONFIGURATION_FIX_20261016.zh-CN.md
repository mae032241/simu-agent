# 原 call 的原 attempt 配置绑定修复

状态：实现与定向源码检查已冻结；等待独立审查及两场零模型完整链检查。真实模型调用为 0。

## 根因与修复

continuation 的配置包含新的 native_attempt、配置摘要及 host review 事实，旧 call 的 accepted 和共同 observation 则绑定原配置。CLI 曾使用当前 adapter 读取旧 call，因而拒绝合法旧终态。

`experiments.configure` 将原本已交给该 W 的 experiment-config 原样发布到现有 host 只读 control 目录的 `interfaces/<attempt>.json`。没有发布 native intent、session、home、凭据、原生输出或科学草稿。旧 call 的 query、lookup、collect、cancel、reconcile 和 dispatch/progress 的旧 call 扫描，先核 accepted 与当前 scope，再按精确 accepted.native_attempt 解析唯一原配置；校验原 scope、record_dir、attempt、interface 后重验冻结代码与配置。没有按最新文件或 executor 猜测的回退。新 submit 使用当前配置。

current/origin capability gate 是调用选中接口的兼容约束，不宣称撤销 native Python/backend 权限。旧配置本来已交 W，可被保存。soft admission 仍由同 stage 当前 review 绑定 native_attempt；旧配置与当前 review 不一致会拒绝新接受，投影不生成新 grant。hard admission 的既有 scope、breadth 与调用上限不变。只读 sealed history 不加载插件、不改写旧 seal。

## 精确验证

- `/tmp/scid-original-call-config-20261016/source-r1/`：18 passed、1 failed；失败是新测试误写不存在的 cov binding，未改生产规避。该轮包含现有 local/cov lifecycle、lookup 和 unknown 不重放 6 项通过。
- `/tmp/scid-original-call-config-20261016/source-r2/`：13 passed，pytest 14.03 秒；监督 14.342 秒、cleanup_complete=true。
- 正控：local/cov/remote 原终态跨 continuation 执行真实 CLI query/lookup/collect/reconcile/lineage-status；原已有文件字节保持；remote 新 call 使用当前 native_attempt。
- async 正控：原 call running 阻止第二提交，原成功/失败按原配置 reconcile；collect=false 不收集，重复 reconcile 保持 observation 字节。
- 负控：投影缺失，scope/record/attempt/interface/implementation 与 accepted attempt 篡改，以及当前 collect capability 缺失。

## 冻结文件

- `src/scidiscovery/research_loop/experiments.py` SHA256 `15f3ad6c6bb9baf92b872dbb0ee37d26145be96f77526e1a8b8772b77ecff5c3`
- `tests/research_loop/test_original_call_configuration.py` SHA256 `06a68482a6f96af85ebc80410ebc205d19ca9b42b41cc5bd6be9c2f601eca84a`

既有缺少原投影且已跨 attempt 的场景保守拒绝；没有迁移/猜测旧 host 私有文件。本次准备的新两场将从修复后的 installed runtime 重新冻结。
