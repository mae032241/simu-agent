# T5 driver 独立只读审查

结论：PASS，范围只限 driver；最终输入清单另审。作者未参与此 driver，不修改、不运行测试或模型。

- Subject：`.trial/rootless-t5-cov-20261012/run_case.py`，SHA256 `5ac8b493aac9cb7630ff1a32257c6858a995735be98f6ca0dd329b9ae978011a`。
- fresh jobs 检查、exclusive started.json、共享串行锁；唯一一次 installed CLI run。
- 启动前全 manifest hashes 核对；冻结6M tokens/3600 active seconds、6.1-sol high/default、无 worker-resume。
- 只记录事实可见与60秒心跳，不把 marker 当科学成功。无错误重试、amend、ack或新收口命令。
- controller退出即记录status/returncode；无法解析或冻结漂移非0，未知执行不重放。已接受runner仍由原core负责，不由driver盲杀或重启。
- end-of-turn token观察与overrun明确另记，不称严格零超额；driver elapsed不是active消费第二权威。

最终 manifest 及资格核对结果见 `/tmp/scid-t5-freeze-review-20261012.md`。
