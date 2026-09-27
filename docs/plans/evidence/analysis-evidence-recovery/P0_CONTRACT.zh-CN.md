# R1 P0 合同冻结

输入计划 SHA256 cf54d6f0fca8a06ffcae09897d43265e986e8b9a32f480b9633bcafd2dc182ce；基线见 baseline.json/baseline.tar.gz。仅本轮增量归本任务。

- 工具 worker_tcad_inspect_outputs：可选 execution_result 输入别名、候选相对路径。默认列举；选定文件则取得不可变副本和只读内容路径。不得提供外部执行 ID。
- 工具 worker_tcad_accept_output：已检查证据别名、原项目 output_name、理由、证据别名列表。生成映射后的新证据别名，原检查记录不改写。
- RPC tcad_inspect_outputs：受信任服务解析 run_id；终态执行内返回有界文件清单或单文件描述符。socket/command/SSH 同语义，旧 helper unsupported；不修改旧清单。
- 新工具 optional_services 与旧 required_services 分离；只给声明工具注入，缺失只影响工具调用。
- 两个附属集合 tool_evidence（最多32文件/256MiB）与 recovery_manifest_output（1项/1MiB；输入端口仍为 recovery_manifest，遵守目录输入/输出名称不可重复规则），由受信任工具生成。WorkerToolDefinition 显式声明 evidence_ports。LocalTrustedBackend 与 RunService.schedule 同源检查允许这些集合；禁止任意 Agent 文件集合。
- primary result.json 保持原 schema 和128KiB限制；附属文件由 RunService 索引/CAS保存，模型不能通过输出目录上传。提交指纹包含证据索引快照；accepted 后拒绝新证据。completed 原子绑定主结果和附属语义名。
- 工具证据用 tool_evidence_NNN 命名；原启动输入不变。统一来源解析器和描述符供工具、可见schema、输出重放使用。
- 恢复清单冻结旧别名→精确 ArtifactRef、原执行/项目引用与映射，后轮只对显式绑定且已准入的同一 Artifact 提供受限重放别名；与本轮新工具别名冲突时拒绝歧义，不改旧计算记录。
- 恢复父链是工具成果父链，不伪装成旧 execution output。parentage guard 保持直接产物分支，恢复分支核对已完成生产 Run、清单与原执行/项目；原audit只覆盖原outputs，不要求它覆盖之后取得的文件，也不清除其失败。
- 接收检查归工具边界，后轮输入检查归preflight，提交只读本地受控副本及回执，不联网、不重新检查输入准入。
- 新manifest可选 solver_exit_code（旧缺失为None）、collection_errors；aggregate终态保留。明确solver失败不被恢复抹除；旧97不自动猜成功。
- 测试：缺失前项仍保留后项；无服务普通分析；真实Root创建→Worker检查接收→评分提交；新Run重放原记录；同字节异执行/伪造/预算/重启/CAS迟到负例；安装态目录与工具投影。

独立审查N1/N2/N3分别落实到集合准入、恢复父链/audit分支及别名重放，属于原R1范围。实施不新增公开Operation或服务。

- 恢复次数细化：新TCAD分析合同 max_attempts=2（本轮加一次显式受控接手），不自动重试；旧Run冻结的1次上限不被新合同提高。原默认1次不能完成计划要求的失败交接，因此在本Operation内显式声明。
