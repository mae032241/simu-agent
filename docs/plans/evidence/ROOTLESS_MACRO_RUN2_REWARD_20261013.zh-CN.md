# 宏观角色修订场 run-2 外部隐藏评分

用户显式要求计算已结束场的run-2 reward。只评价实际提交的已冻结模型，不重新训练、不启动科研模型、不向科研角色回灌评分。

- 来源：外层 `.trial/rootless-macro-role-cov-20261012/instance/runs/submitted_model.pkl`，候选 `run-2`；与控制层最后确认的SHA一致：`42152036fa94907c5edbb0125c62f81879c4c8d3c2683c1f139d115f4fa4d393`。
- 公开val=0.9093，原提交审计score=0.9308、leakage_flag=false。
- 官方隐藏recovery：**0.3563262353962097**；官方verifier reward：**0.0370**；integrity_guard=false。条件reward同为0.0370。
- 评分运行2.264秒，返回0、cleanup_complete=true；没有训练或LLM请求。源提交评分前后哈希未变。
- 独立评分目录：`.trial/official-score-macro-role-run2-20261013/`，保存快照、manifest、原官方verifier结果及资源记录。复用已验证的隔离评分入口，bwrap无网络，隐藏材料与候选模型只读，输出位于评分专属目录；公开/隐藏评估条件已核对。

这说明本候选公开val不能代表目标条件表现；不能据此宣称A职责修订已提高科研质量。分数没有发给本轮实现者、独立角色合同审查者或科研角色；本轮指导修订依据公开轨迹中的重复诊断及探索分配缺口，不按隐藏分选择具体算法。

原场源码冻结检查失败仍保留：当时运行固定安装包期间仓库4个源文件被编辑，驱动返回3；控制器交付确认返回0。此次评分绑定具体提交模型，不把评分成功追认为原场整体门禁通过。

评分manifest SHA256：`cc37ba8423d08ac0283f13f357f4d34c2e58af0ce65fb476e8a44d4297954afe`。
