# Covshift 本机环境准备记录

状态（2026-10-04）：**独立 Python 环境与一次真实公开 exp CLI 工程 smoke 独立审查通过（环境与公开 CLI 工程 smoke）；launch_ready=false。** 当前首 pilot 选 covshift；原 N-body 24 粒子工程 smoke 和所有旧 candidate 保留。选题／科学资格由[主计划](plans/SCIENTIFIC_PROGRESS_AND_CORRECTION_PLAN.zh-CN.md#真实效果题与机制回归分工)拥有；本文只交接本机环境，不是模型驱动或正式 trial。

## 已准备

- Task 固定 LHTB `d78f5eb52ad754c5ee9154741af73130a85a65b8` 的 `tabular-data-feature-covshift`，原题／checkout 不修改。公开包 `/tmp/scid-covshift-local-20261004-prepared-001/public` 仅 8 文件：task.toml、instruction.md、environment/Dockerfile，以及 harness 的 exp_cli.py、runner.py、train.csv、val.csv、净化 meta.json。trusted 准备代码复刻 Dockerfile：删除 meta 的 a_perturbation／estimated_A_score／noise_sigma；只记录原件与净化结果 hash，不输出敏感值、不导出／运行 generator，不读 hidden tests／verifier／reference。
- 独立 env `/tmp/scid-covshift-local-20261004-env`；11 个精确 CPython 3.12／Linux x86_64 binary wheels 总 75169712 B，低于本轮 150 MB 下载上限。公开 PyPI 元数据、wheel size／SHA 均核对后离线 no-index／no-deps 安装，原 miniconda／已有 env 不改。可重建版本与 wheel SHA 的权威输入为 [requirements.lock](../scripts/acceptance/fixtures/covshift_local/requirements.lock)，不是只保存在 /tmp 的配置。
- [任务专用薄入口](../scripts/prepare_covshift_local.py) 复用已有 N-body namespace／regular-file helpers 和 run_tests 默认监督。只读挂 public、必要 base runtime 与新 venv 的 interpreter／pyvenv.cfg／lib；保留 venv/bin/python 身份，sys.executable／sys.prefix 和所有 11 版本在真实 task namespace 中核过。任务执行前关闭其继承的监督锁 FD，父监督仍持锁；清环境、独立禁网、host-private canary 与 native 子进程边界通过。实际 Root／Worker／helper 的模型 API／task 隔离尚未接线，不扩大该工程子进程证据。
- 原 train.csv／val.csv 未裁小，合法 zero/DummyRegressor 工程基线只做一次 `exp run --script` → results → `submit --run-id 1` → status；60 s run／45 s audit／0.10 阈值不改。run 与公开 audit 都实际完成，validation／audit score 均 0、leakage_flag=false；这是管线验收，不是有效科学改进／隐藏分数，也不满足原至少 25 次不同实验与最后 8 次停滞条件。25 internal exp 不等于 25 Root task 或轮换／记忆覆盖。
- regular `submitted.json` 304 B 与 `submitted_model.pkl` 3877 B 已交接到 submission；trusted host 只做 bounded regular／hash／复制，不反序列化。32 MiB 是本工程 smoke 的读取上限，不是原题正式模型提交限制；没有继承 N-body 的 2 MB 上限。7 个聚焦净化／篡改／白名单／symlink／handoff 检查通过。

## 重建入口与监督

从本仓库根目录使用 Python 3.12／Linux x86_64。下面是调用**既有** serial_lock／run_one 的最小环境重建方式，新目录须尚不存在；所有命令默认 AS2000000000 B／RSS 止损1500000000 B／300 s／8 MiB log，数值线程为 1。联网步骤仅 binary PyPI wheels，随后离线安装；本轮不是系统安装或新资源授权。

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

用户已确认 **Native Goal 与 SciDiscovery 各一次、每模式全角色共用 1800 s wall deadline** 的 custom 链路 smoke；不是每个角色各获 30 分钟，也不是原题 4 h 同条件成绩。两模式实际 driver、有效 profile／反馈、任务与模型 API 的网络边界、Root／Worker／helper 的真实读隔离、trusted host-only 隐藏评分、全角色 token／费用上限与停止仍待冻结；不沿用 P6s 4M。原全角色6.1-sol/high提案未激活，alias仍未 runtime核实，progression mode未选；不把开发6.1/xhigh当场次条件。本轮未启动 model／Goal／app-server／科研实例／评分，不授权新科研费用；launch_ready=false。
